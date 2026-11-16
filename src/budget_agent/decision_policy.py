"""D 负责扩展的最终约束校验。

结构：骨架提供的最低保护（引用存在性、购物篮范围、算术、未知条件、预算门槛）全部保留，
D 在此基础上补三类检查（均标注 `[D]`）：

1. **论点与证据内容一致性**：不只检查 ID 存在，还检查论点里出现的金额能否在证据里找到出处。
   这是"内容"层面的检查，也是裁判最容易出错的地方 —— 编一个"到手 500 元"就能翻转结论。
   为避免误报，允许的金额集合同时包含证据中的数值与 offer 各项金额的两两差值
   （"比单买少付 25 元"这种差值必须算合法）。
2. **必要性策略**：低紧急度 + 已有同类物品时给出提醒并追加下一步，但**不否决** ——
   必要性是偏好问题，程序不该替用户判定"该不该想要"；能程序化判定的是钱和算术。
3. **失败与留痕**：没有任何角色观点时不放行；否决时**保留模型原始理由**，不静默覆盖
   （骨架原实现会整段替换 reason_summary，原文只在 RunRecord 里，用户看不到）。

降级规则分两层，区别在"这条问题是否真的影响这个结论"：
- **否决级**：证据引用不存在这类问题，任何结论都不成立 → 一律降为 `need_info`；
- **相关级**：优惠方案未验证 / 运费未知 / 明细不一致，只有 `buy` 才依赖它。
  模型已经说 `skip`（需求不成立）或 `wait`（现在不行）时，方案验证与否不改变结论，
  此时只记录进 `policy_violations`，**不强行把结论改成 need_info**（否则用户会被要求
  去补一个与结论无关的运费信息）。

这里不验证优惠最优性，也不代替 C 的求解器测试。
"""

import re
from typing import Any

from budget_agent.schemas import Decision, DecisionProposal, RoleContext

AMOUNT_PATTERNS = (
    # ¥500 / ￥500
    re.compile(r"(?:¥|￥)\s*(\d[\d,]*(?:\.\d{1,2})?)"),
    # 500 元 / 500 块 / 500 块钱
    re.compile(r"(\d[\d,]*(?:\.\d{1,2})?)\s*(?:元|块钱|块)"),
)
FACTUAL_EVIDENCE_KINDS = {"budget", "product", "promotion", "offer"}
LOW_URGENCY = "low"


def _collect_numbers(value: Any, sink: set[int], key: str | None = None) -> None:
    """只收集 `*_cents` 字段的整数。

    不能"看到整数就当金额"：`days_remaining=20` 会被读成 20 分（0.2 元），
    让一个毫无依据的"0.2 元"变成合法金额，也让允许集合里混进一堆无意义的值。
    金额字段一律以 `_cents` 结尾（见 schemas.py 的 Money 约定），据此过滤。
    """
    if isinstance(value, dict):
        for name, item in value.items():
            _collect_numbers(item, sink, key=name)
    elif isinstance(value, list):
        for item in value:
            _collect_numbers(item, sink, key=key if key and key.endswith("_cents") else None)
    elif isinstance(value, int) and not isinstance(value, bool):
        if key is not None and key.endswith("_cents"):
            sink.add(value)


def evidence_amounts(context: RoleContext) -> set[int]:
    """证据里出现过的全部整数金额（分）。"""
    amounts: set[int] = set()
    for item in context.evidence:
        _collect_numbers(item.facts, amounts)
    return amounts


def offer_differences(context: RoleContext) -> set[int]:
    """方案证据里各金额的两两差值。

    "比单买少付 25 元" 这类结论只存在于差值里，不放开这条会把正确的解释判成编造。
    只在 offer 证据内部做差值，范围可控，也不会把任意两个数凑成合法金额。
    """
    offer_numbers: set[int] = set()
    for item in context.evidence:
        if item.kind == "offer":
            _collect_numbers(item.facts, offer_numbers)
    values = sorted(offer_numbers)
    return {abs(a - b) for i, a in enumerate(values) for b in values[i + 1 :]}


def claim_amounts(texts: list[str]) -> set[int]:
    """从自然语言里抽出金额，换算成分。

    覆盖「500 元 / 500 块 / ¥500」三种常见写法；**不解析"两百""三百五"这类中文数字**
    —— 中文数词解析的边界太多（"一百二"是 120 还是 102），错解析比不解析更危险。
    提示词已要求金额只指向证据 ID、不自行换算，这一条漏口靠提示词与真实模型复测兜住。
    """
    amounts: set[int] = set()
    for text in texts:
        for pattern in AMOUNT_PATTERNS:
            for match in pattern.finditer(text):
                raw = match.group(1).replace(",", "")
                cents = round(float(raw) * 100)
                if cents > 0:
                    amounts.add(cents)
    return amounts


def unsupported_amounts(texts: list[str], context: RoleContext) -> list[int]:
    """找出论点里没有任何证据出处的金额，返回分值（升序）。"""
    allowed = evidence_amounts(context) | offer_differences(context)
    return sorted(claim_amounts(texts) - allowed)


def advisory_steps(action: str, context: RoleContext) -> list[str]:
    """不改变结论、只补充下一步的提醒。

    参数是**校验后**的动作：结论已被降级时，不该再追加"买之前先想想"这类提醒。
    """
    advisories: list[str] = []
    request = context.case.request
    owned = [item for item in context.case.profile.owned_similar_items if item.strip()]
    if action == "buy" and request.urgency == LOW_URGENCY and owned:
        advisories.append(
            "紧急度低且已有同类物品（" + "、".join(owned) + "），先确认能否替代再下单"
        )
    offer = context.offer
    if (
        action == "buy"
        and offer is not None
        and offer.payable_cents is not None
        and offer.baseline_payable_cents is not None
        and len(offer.basket_ids) > 1
        and offer.payable_cents >= offer.baseline_payable_cents
    ):
        advisories.append("凑单后总付款没有低于单买，凑单部分不构成省钱")
    return advisories


def apply_decision_policy(
    proposal: DecisionProposal, context: RoleContext
) -> tuple[Decision, list[str]]:
    """返回 (最终决定, 全部问题清单)。问题清单进 RunRecord.policy_violations。

    `issues` 每项带一个 `blocks` 标记：是否足以推翻当前结论。分开记的目的是让
    "记了多少违规"和"因此改了什么结论"成为两个可独立统计的数 —— 报告里要用。
    """
    issues: list[tuple[str, bool]] = []

    def add(message: str, *, blocks: bool) -> None:
        issues.append((message, blocks))

    action = proposal.action
    # 只有 buy 依赖优惠方案：skip/wait 现在不花钱，方案验证与否不改变这个结论。
    offer_required = action == "buy"

    evidence_ids = {item.id for item in context.evidence}
    if len(evidence_ids) != len(context.evidence):
        add("证据 ID 重复", blocks=True)
    if not set(proposal.evidence_ids) <= evidence_ids:
        add("裁判引用了不存在的证据", blocks=True)
    for argument in context.arguments:
        if not set(argument.evidence_ids) <= evidence_ids:
            add(f"{argument.role} 引用了不存在的证据", blocks=True)

    offer = context.offer
    if context.budget.missing_fields:
        add("预算必填字段缺失", blocks=True)
    if offer is None or not offer.verified or offer.unknowns:
        add("优惠方案尚未确认或存在未知条件", blocks=offer_required)
    elif offer.payable_cents is None or offer.shipping_cents is None:
        add("最终付款额或运费未知", blocks=offer_required)
    else:
        products = {p.id: p for p in context.products}
        allowed = {context.case.request.target_product_id, *context.case.request.needed_addon_ids}
        basket = offer.basket_ids
        if (
            not set(basket) <= allowed
            or not set(basket) <= products.keys()
            or context.case.request.target_product_id not in basket
            or len(set(basket)) != len(basket)
        ):
            add("购物篮包含未知、重复或未经确认需要的商品", blocks=offer_required)
        else:
            subtotal = sum(products[pid].price_cents for pid in basket)
            if (
                offer.subtotal_cents != subtotal
                or offer.discount_cents is None
                or offer.discount_cents > subtotal
                or offer.payable_cents != subtotal - offer.discount_cents + offer.shipping_cents
            ):
                add("购物篮付款明细不一致", blocks=offer_required)
        known_rules = {
            e.id.removeprefix("promotion:") for e in context.evidence if e.kind == "promotion"
        }
        if not set(offer.rule_ids) <= known_rules:
            add("方案引用了未知优惠规则", blocks=offer_required)
        if offer.verification_method == "unverified":
            add("优惠方案没有验证方式", blocks=offer_required)
        if offer.verification_method == "demo_fixture" and not offer.is_demo:
            add("演示方案未标记为演示数据", blocks=offer_required)

    # ---- [D] 扩展：购买建议必须落在事实类证据上，不能只引用用户自述
    if action == "buy":
        # ---- [D] 扩展：没有任何观点就给出购买结论，等于凭空的裁判
        # 只对 buy 成立：skip/wait/need_info 是保守方向，不花钱，不需要论证支撑；
        # 而"预算字段缺失"会在工作流里提前退出，此时 arguments 天然为空，
        # 若一并记为违规，报告里的归因就会被这条噪音带偏。
        if not context.arguments:
            add("没有任何角色观点可供裁判权衡", blocks=True)

        proposal_ids = set(proposal.evidence_ids)
        factual = [
            item.id
            for item in context.evidence
            if item.kind in FACTUAL_EVIDENCE_KINDS and item.id in proposal_ids
        ]
        if not factual:
            add("购买建议缺少事实类证据（预算/商品/优惠/方案之一）", blocks=True)

        # ---- [D] 扩展：论点里的金额必须能在证据中找到出处
        # 只检查"支撑结论"的文本。`counterargument` 按设计要写"反方最有力的说法及其
        # 成立条件"，天生含假设数字（"如果月底还压着 600 元支出就该等"），把它也纳入
        # 会系统性地误杀正确结论 —— 而它并不为结论提供依据，编造也无从获益。
        texts = [proposal.reason_summary]
        for argument in context.arguments:
            texts.extend(argument.claims)
        missing = unsupported_amounts(texts, context)
        if missing:
            shown = "、".join(f"{cents / 100:.2f} 元" for cents in missing[:3])
            add(f"论点中的金额没有对应证据：{shown}", blocks=True)

    problems = [message for message, _ in issues]
    blocking = [message for message, blocks in issues if blocks]

    if blocking:
        action = "need_info"
    elif action == "buy" and context.budget.within_budget is not True:
        message = "购买建议未通过最终付款额的预算检查"
        problems.append(message)
        blocking.append(message)
        action = "wait"

    result = proposal.model_dump()
    result["action"] = action
    if blocking:
        result["reason_summary"] = (
            "程序校验调整建议：" + "；".join(blocking) + f"。原始建议理由：{proposal.reason_summary}"
        )
        # 把"要修什么"直接写成下一步，避免只给一句"补充信息后重跑"的空话。
        result["next_steps"] = [
            *(f"待处理：{item}" for item in blocking),
            *proposal.next_steps,
        ]
    if problems:
        # 被剔除的引用可能正是原结论的依据，一律清掉再交付。
        result["evidence_ids"] = [i for i in proposal.evidence_ids if i in evidence_ids]
    merged = list(result["next_steps"])
    merged.extend(item for item in advisory_steps(action, context) if item not in merged)
    result["next_steps"] = merged
    return Decision(**result, budget_result=context.budget, offer_result=offer), problems
