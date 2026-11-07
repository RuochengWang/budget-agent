"""D 负责扩展的最终约束校验；以下为骨架提供的最低保护。

这里不验证每种优惠的最优性，也不代替 C 的规则求解测试。
保留模型原始建议；若否决，另记原因并生成最终建议。
"""

from budget_agent.schemas import Decision, DecisionProposal, RoleContext


def apply_decision_policy(
    proposal: DecisionProposal, context: RoleContext
) -> tuple[Decision, list[str]]:
    problems: list[str] = []
    action = proposal.action
    evidence_ids = {item.id for item in context.evidence}
    if len(evidence_ids) != len(context.evidence):
        problems.append("证据 ID 重复")
    if not set(proposal.evidence_ids) <= evidence_ids:
        problems.append("裁判引用了不存在的证据")
    for argument in context.arguments:
        if not set(argument.evidence_ids) <= evidence_ids:
            problems.append(f"{argument.role} 引用了不存在的证据")
    offer = context.offer
    if context.budget.missing_fields:
        problems.append("预算必填字段缺失")
    if offer is None or not offer.verified or offer.unknowns:
        problems.append("优惠方案尚未确认或存在未知条件")
    elif offer.payable_cents is None or offer.shipping_cents is None:
        problems.append("最终付款额或运费未知")
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
            problems.append("购物篮包含未知、重复或未经确认需要的商品")
        else:
            subtotal = sum(products[pid].price_cents for pid in basket)
            if (
                offer.subtotal_cents != subtotal
                or offer.discount_cents is None
                or offer.discount_cents > subtotal
                or offer.payable_cents != subtotal - offer.discount_cents + offer.shipping_cents
            ):
                problems.append("购物篮付款明细不一致")
        known_rules = {
            e.id.removeprefix("promotion:") for e in context.evidence if e.kind == "promotion"
        }
        if not set(offer.rule_ids) <= known_rules:
            problems.append("方案引用了未知优惠规则")
        if offer.verification_method == "unverified":
            problems.append("优惠方案没有验证方式")
        if offer.verification_method == "demo_fixture" and not offer.is_demo:
            problems.append("演示方案未标记为演示数据")
    if problems:
        action = "need_info"
    elif action == "buy" and context.budget.within_budget is not True:
        problems.append("购买建议未通过最终付款额的预算检查")
        action = "wait"
    result = proposal.model_dump()
    result["action"] = action
    if problems:
        result["reason_summary"] = "程序校验调整建议：" + "；".join(problems)
        result["next_steps"] = ["补充缺失信息或修复校验问题后重新运行", *proposal.next_steps]
        result["evidence_ids"] = [i for i in proposal.evidence_ids if i in evidence_ids]
    # TODO(D)：补充证据内容与论点的一致性检查、必要性策略及更多失败情形。
    return Decision(**result, budget_result=context.budget, offer_result=offer), problems
