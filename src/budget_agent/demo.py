"""专用离线替身。B/C/D 的正式模块不导入本文件。

预算为演示参考公式，商品读取演示快照，优惠从手工复算的 fixture 选取。
此处没有通用优惠求解器，没有真实模型，也不供正式评测使用。
"""

import json
from datetime import datetime
from pathlib import Path

from budget_agent.errors import AgentError
from budget_agent.model_client import ModelClient
from budget_agent.schemas import (
    Argument,
    BudgetResult,
    DealResult,
    DecisionProposal,
    Evidence,
    OfferResult,
    OptimizationInput,
    Product,
    PromotionRule,
    RoleContext,
    UserProfile,
)
from budget_agent.tools.registry import ToolRegistry


def calculate_demo_budget(profile: UserProfile, payable_cents: int | None = None) -> BudgetResult:
    fields = (
        "cash_cents",
        "days_remaining",
        "daily_essential_cents",
        "fixed_expenses_cents",
        "reserve_cents",
    )
    missing = [field for field in fields if getattr(profile, field) is None]
    if missing:
        return BudgetResult(missing_fields=missing)
    essential = (
        profile.days_remaining * profile.daily_essential_cents + profile.fixed_expenses_cents
    )
    discretionary = profile.cash_cents - essential - profile.reserve_cents
    return BudgetResult(
        essential_total_cents=essential,
        discretionary_cents=discretionary,
        remaining_cash_cents=None if payable_cents is None else profile.cash_cents - payable_cents,
        within_budget=None if payable_cents is None else payable_cents <= discretionary,
    )


class DemoCatalog:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir

    def get_products(self, product_ids: list[str]) -> list[Product]:
        rows = json.loads((self.data_dir / "catalog/products.json").read_text(encoding="utf-8"))
        products = {p.id: p for p in map(Product.model_validate, rows)}
        if not set(product_ids) <= products.keys():
            raise AgentError("演示快照中不存在指定商品 ID")
        return [products[pid] for pid in product_ids]

    def search_products(self, query: str, limit: int = 5) -> list[Product]:
        rows = json.loads((self.data_dir / "catalog/products.json").read_text(encoding="utf-8"))
        return [p for p in map(Product.model_validate, rows) if query in p.name or query == p.id][
            :limit
        ]

    def get_promotion_rules(self, product_ids: list[str], as_of: datetime) -> list[PromotionRule]:
        rows = json.loads((self.data_dir / "catalog/promotions.json").read_text(encoding="utf-8"))
        return [
            r
            for r in map(PromotionRule.model_validate, rows)
            if set(product_ids) & set(r.eligible_product_ids) and r.valid_from <= as_of < r.valid_to
        ]

    def optimize_basket(self, request: OptimizationInput) -> OfferResult:
        rows = json.loads((self.data_dir / "demo_offers.json").read_text(encoding="utf-8"))
        available = {request.target_product_id, *request.candidate_ids}
        matching = [
            OfferResult.model_validate(row)
            for row in rows
            if row["basket_ids"][0] == request.target_product_id
            and set(row["basket_ids"]) <= available
            and set(row["rule_ids"]) <= {r.id for r in request.rules}
        ]
        if not matching:
            return OfferResult(
                basket_ids=[request.target_product_id],
                is_demo=True,
                unknowns=["没有匹配的演示 fixture；请使用内置案例"],
            )
        offer = min(matching, key=lambda r: r.payable_cents)
        if request.shipping_cents is None:
            return offer.model_copy(
                update={
                    "shipping_cents": None,
                    "payable_cents": None,
                    "baseline_payable_cents": None,
                    "verified": False,
                    "unknowns": ["运费未知"],
                }
            )
        # fixture 为零运费；显式修改运费时，同步修改单买基准与总付款。
        return offer.model_copy(
            update={
                "shipping_cents": request.shipping_cents,
                "payable_cents": offer.payable_cents + request.shipping_cents,
                "baseline_payable_cents": offer.baseline_payable_cents + request.shipping_cents,
            }
        )


def scripted_response(role: str, payload: dict) -> dict:
    context = RoleContext.model_validate(payload)
    if role == "judge":
        if context.budget.missing_fields or context.offer.payable_cents is None:
            action, reason = "need_info", "演示：需要补充预算信息或运费。"
        elif context.budget.within_budget:
            action, reason = "buy", "演示：付款额在预算内；这是脚本建议，尚未评估个人偏好。"
        else:
            action, reason = "wait", "演示：优惠后的总付款仍超过可支配预算。"
        return DecisionProposal(
            action=action,
            reason_summary=reason,
            counterargument="演示：即使预算足够，也应确认必要性与替代选择。",
            evidence_ids=["input:request", "budget:final", "offer:chosen"],
            next_steps=["由 B/C/D 完成正式计算与角色策略后，重新评估"],
        ).model_dump()
    claims = {
        "desire": "演示：购买价值应结合用户填写的需求理由讨论。",
        "rational": "演示：先保护基本生活支出与预留金，再考虑购买。",
        "deal": "演示：展示手工复算的优惠方案；没有运行通用求解器。",
    }
    return Argument(
        role=role,
        stance="neutral",
        claims=[claims[role]],
        evidence_ids=["offer:chosen"] if role == "deal" else ["input:request", "budget:initial"],
    ).model_dump()


def run_demo_role(role: str, context: RoleContext, model: ModelClient) -> Argument:
    return model.generate_json(role, "脚本化演示", context.model_dump(mode="json"), Argument)


def run_demo_judge(context: RoleContext, model: ModelClient) -> DecisionProposal:
    return model.generate_json(
        "judge", "脚本化演示", context.model_dump(mode="json"), DecisionProposal
    )


def run_demo_deal(context: RoleContext, model: ModelClient, tools: ToolRegistry) -> DealResult:
    request = context.case.request
    rules = tools.call(
        "get_promotion_rules",
        {
            "product_ids": [p.id for p in context.products],
            "as_of": request.as_of.isoformat(),
        },
    )
    optimization = OptimizationInput(
        target_product_id=request.target_product_id,
        candidate_ids=request.needed_addon_ids,
        products=context.products,
        rules=rules,
        shipping_cents=request.shipping_cents,
        as_of=request.as_of,
    )
    offer = tools.call("optimize_basket", {"request": optimization.model_dump(mode="json")})
    evidence = [
        Evidence(
            id=f"promotion:{r.id}",
            kind="promotion",
            description="演示优惠规则",
            facts=r.model_dump(mode="json"),
            is_demo=r.is_demo,
        )
        for r in rules
    ]
    evidence.append(
        Evidence(
            id="offer:chosen",
            kind="offer",
            description="手工复算的演示方案",
            facts=offer.model_dump(mode="json"),
            is_demo=True,
        )
    )
    with_offer = context.model_copy(
        update={"offer": offer, "evidence": context.evidence + evidence}
    )
    return DealResult(
        argument=run_demo_role("deal", with_offer, model), offer=offer, evidence=evidence
    )
