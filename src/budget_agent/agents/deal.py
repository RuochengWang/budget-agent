"""D：工具调用策略；C 的求解器只负责计算，不能在这里重复实现。

工具额度是全流程共享的（`ToolRegistry.traces` 里包含 A 的 calculate_budget 与
get_products），所以本节点必须自己算"还剩几次"，并且**留 1 次给 A 在优惠节点之后
用最终付款额重算预算**。默认 max_tool_calls=6 时，D 可用 3 次，固定序列使用其中 2 次：
get_promotion_rules + optimize_basket，第 5 次是 A 的复算，另余 1 次可用于受控补查。

采用固定的工具调用顺序，并在额度不足时停止：
不用模型规划工具，因为候选商品已被用户确认，求解器一次穷举就能给出最优解；
让模型"选工具"只会增加调用次数与不可复现性。补查只在额度尚有余量、且中间结果
确实缺信息时发生；否则带着 unknowns 退出，**不反复重试**。
"""

from budget_agent.agents.base import call_role
from budget_agent.agents.desire import filter_evidence_ids, known_evidence_ids
from budget_agent.errors import AgentError, ToolLimitReached
from budget_agent.model_client import ModelClient
from budget_agent.schemas import (
    Argument,
    DealResult,
    Evidence,
    OfferResult,
    OptimizationInput,
    PromotionRule,
    RoleContext,
)
from budget_agent.tools.registry import ToolRegistry

# 留给 A 在优惠节点之后用 payable_cents 重算预算的那一次调用。
RESERVED_FOR_FINAL_BUDGET = 1


def remaining_calls(tools: ToolRegistry) -> int:
    """本节点可用的工具额度（已扣除留给 A 的复算）。"""
    return tools.max_calls - len(tools.traces) - RESERVED_FOR_FINAL_BUDGET


def _rule_evidence(rules: list[PromotionRule]) -> list[Evidence]:
    """原始规则必须进证据表，供最终校验核对 rule_ids；ID 固定为 promotion:<id>。"""
    return [
        Evidence(
            id=f"promotion:{rule.id}",
            kind="promotion",
            description=f"{rule.merchant} 的{'满减' if rule.kind == 'reduction' else '优惠券'}规则",
            facts=rule.model_dump(mode="json"),
            source_url=rule.source_url,
            is_demo=rule.is_demo,
        )
        for rule in rules
    ]


def _offer_evidence(offer: OfferResult) -> Evidence:
    """方案证据 ID 固定为 offer:chosen，不复用、不覆盖旧 ID。"""
    return Evidence(
        id="offer:chosen",
        kind="offer",
        description="求解器返回的最优可行方案",
        facts=offer.model_dump(mode="json"),
        is_demo=offer.is_demo,
    )


def run(context: RoleContext, model: ModelClient, tools: ToolRegistry) -> DealResult:
    request = context.case.request
    if not context.products:
        raise AgentError("优惠节点缺少商品信息，无法求解")
    if remaining_calls(tools) < 2:
        raise ToolLimitReached("剩余工具额度不足以完成优惠查询与求解")

    # 1. 查规则：一次查全（目标商品 + 已确认的凑单候选），不做多次试探。
    rules = tools.call(
        "get_promotion_rules",
        {
            "product_ids": [product.id for product in context.products],
            "as_of": request.as_of.isoformat(),
        },
    )
    if remaining_calls(tools) < 1:
        raise ToolLimitReached("规则查询后已无额度调用求解器")

    # 2. 求解：候选集只来自用户确认需要的凑单品，求解器负责全部算术。
    optimization = OptimizationInput(
        target_product_id=request.target_product_id,
        candidate_ids=request.needed_addon_ids,
        products=context.products,
        rules=rules,
        shipping_cents=request.shipping_cents,
        as_of=request.as_of,
    )
    offer = tools.call("optimize_basket", {"request": optimization.model_dump(mode="json")})

    # 3. 证据：规则 + 方案。方案不是 verified 时也照样入证据表，
    #    让最终校验看得到"未确认"，而不是在这里替它做决定。
    evidence = [*_rule_evidence(rules), _offer_evidence(offer)]

    # 4. 观点：把 offer 放进上下文再让模型发言，避免它自己算钱。
    enriched = context.model_copy(
        update={"offer": offer, "evidence": [*context.evidence, *evidence]}
    )
    argument = call_role("deal", enriched, model, Argument)
    if argument.role != "deal":
        raise AgentError("优惠节点返回了不匹配的 role")

    _, dropped = filter_evidence_ids(argument.evidence_ids, known_evidence_ids(enriched))
    unknowns = list(argument.unknowns)
    if dropped:
        unknowns.append("引用了上下文中不存在的证据：" + "、".join(dropped))
    for item in offer.unknowns:
        if item not in unknowns:
            unknowns.append(item)
    # 保留非法 ID，最终 policy 才能阻断并记录；不修改原始方案金额。
    argument = argument.model_copy(update={"unknowns": unknowns})

    return DealResult(argument=argument, offer=offer, evidence=evidence)
