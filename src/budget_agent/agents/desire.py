"""D：购买价值与主观收益。

职责边界（写在这里，避免后人改坏）：
1. 只谈需求、偏好与使用价值，不谈"划不划算"。预算结论由 B 的工具与最终校验给出；
   欲望角色一旦开始算钱，四角色就退化成四份语气不同的作文，对照实验也失去意义。
   `build_payload` 以白名单构造需求、已有物品和非金额商品事实，同时裁剪嵌套证据。
   不发送预算、报价或预算输入；不改变原始 RoleContext。
2. 引用原样保留，非法引用交由最终 policy 检查，不能在校验前删除违规依据。
"""

from budget_agent.agents.base import PROMPT_DIR
from budget_agent.errors import AgentError
from budget_agent.model_client import ModelClient
from budget_agent.schemas import Argument, RoleContext


def known_evidence_ids(context: RoleContext) -> set[str]:
    return {item.id for item in context.evidence}


def filter_evidence_ids(ids: list[str], known: set[str]) -> tuple[list[str], list[str]]:
    """返回 (保留的 ID, 被剔除的 ID)，同时去重并保持原顺序。"""
    kept: list[str] = []
    dropped: list[str] = []
    for raw in ids:
        if raw in kept or raw in dropped:
            continue
        (kept if raw in known else dropped).append(raw)
    return kept, dropped


def build_payload(context: RoleContext) -> dict:
    """初次发言与交叉回应共用的非预算视图；证据事实也来自同一白名单。

    保留用户的自由文本，不宣称能识别自由文本中所有隐含金额；程序字段和工具证据
    中的现金、预算、报价和运费不会通过其他路径重新进入这个视图。
    """
    case = context.case
    request = case.request.model_dump(mode="json", exclude={"shipping_cents"})
    profile = {"owned_similar_items": list(case.profile.owned_similar_items)}
    products = [p.model_dump(mode="json", exclude={"price_cents"}) for p in context.products]
    facts = {
        "input:request": request,
        "input:profile": profile,
        **{f"product:{product['id']}": product for product in products},
    }
    evidence = [
        {**item.model_dump(mode="json"), "facts": facts[item.id]}
        for item in context.evidence
        if item.id in facts and item.kind in {"input", "product"}
    ]
    return {
        "case": {
            "case_id": case.case_id,
            "title": case.title,
            "profile": profile,
            "request": request,
        },
        "products": products,
        "evidence": evidence,
    }


def run(context: RoleContext, model: ModelClient) -> Argument:
    prompt = (PROMPT_DIR / "desire.md").read_text(encoding="utf-8")
    payload = build_payload(context)
    argument = model.generate_json("desire", prompt, payload, Argument)
    if argument.role != "desire":
        raise AgentError("欲望角色返回了不匹配的 role")

    visible = {item["id"] for item in payload["evidence"]}
    _, dropped = filter_evidence_ids(argument.evidence_ids, visible)
    unknowns = list(argument.unknowns)
    if dropped:
        unknowns.append("引用了本角色上下文中不存在的证据：" + "、".join(dropped))
    return argument.model_copy(update={"unknowns": unknowns})
