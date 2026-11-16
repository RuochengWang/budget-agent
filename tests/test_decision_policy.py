import pytest

from budget_agent.decision_policy import (
    apply_decision_policy,
    claim_amounts,
    unsupported_amounts,
)
from budget_agent.schemas import DecisionProposal, RoleContext
from budget_agent.workflow import run_case


def context_from_record(record, products):
    return RoleContext(
        case=record.input,
        products=products,
        budget=record.final_decision.budget_result,
        offer=record.final_decision.offer_result,
        evidence=record.evidence,
        arguments=record.arguments,
    )


def test_forged_reference_blocks_buy(cases, config, products):
    record = run_case(cases["tissue_buy"], config)
    proposal = DecisionProposal(
        action="buy", reason_summary="买", evidence_ids=["made-up"], next_steps=[]
    )
    decision, issues = apply_decision_policy(proposal, context_from_record(record, products))
    assert decision.action == "need_info"
    assert issues


@pytest.mark.parametrize(
    "change",
    [
        {"payable_cents": 1},
        {"basket_ids": ["daily_goods", "large_addon"]},
        {"basket_ids": ["daily_goods", "tissue", "tissue"]},
        {"rule_ids": ["made-up"]},
        {"verified": False},
    ],
)
def test_invalid_offer_blocks_buy(cases, config, products, change):
    record = run_case(cases["tissue_buy"], config)
    context = context_from_record(record, products)
    context.offer = context.offer.model_copy(update=change)
    decision, issues = apply_decision_policy(record.proposed_decision, context)
    assert decision.action == "need_info"
    assert issues


# ---------------------------------------------------------------- D 新增的检查
def test_supported_buy_is_kept(cases, config, products):
    """正常路径不能被扩展检查误伤：有事实证据、金额有出处、预算通过 → 结论保留。"""
    record = run_case(cases["tissue_buy"], config)
    proposal = DecisionProposal(
        action="buy",
        reason_summary="纸巾本来就要买，凑单后少付 25 元",
        counterargument="如果抽纸还有存货，凑单就变成多买",
        evidence_ids=["budget:final", "offer:chosen"],
        next_steps=["确认同店同单可用"],
    )
    decision, issues = apply_decision_policy(proposal, context_from_record(record, products))
    assert issues == []
    assert decision.action == "buy"


def test_amount_without_evidence_blocks_buy(cases, config, products):
    """裁判编一个"只需 500 元"就能翻转结论 —— 金额必须能在证据里找到出处。"""
    record = run_case(cases["tissue_buy"], config)
    context = context_from_record(record, products)
    proposal = DecisionProposal(
        action="buy",
        reason_summary="叠加平台券后只需 500 元，很划算",
        evidence_ids=["budget:final", "offer:chosen"],
        next_steps=[],
    )
    decision, issues = apply_decision_policy(proposal, context)
    assert decision.action == "need_info"
    assert any("金额没有对应证据" in issue for issue in issues)


def test_bundle_difference_is_a_legitimate_amount(cases, config, products):
    """「少付 25 元」是差值，必须被认作合法金额，否则正确解释会被判成编造。"""
    record = run_case(cases["tissue_buy"], config)
    context = context_from_record(record, products)
    assert unsupported_amounts(["凑单后少付 25 元"], context) == []


def test_buy_without_factual_evidence_blocks(cases, config, products):
    """只引用用户自述（input:*）不足以支撑购买建议。"""
    record = run_case(cases["tissue_buy"], config)
    proposal = DecisionProposal(
        action="buy", reason_summary="用户说需要，那就买", evidence_ids=["input:request"], next_steps=[]
    )
    decision, issues = apply_decision_policy(proposal, context_from_record(record, products))
    assert decision.action == "need_info"
    assert any("事实类证据" in issue for issue in issues)


def test_no_arguments_blocks_buy(cases, config, products):
    record = run_case(cases["tissue_buy"], config)
    context = context_from_record(record, products)
    context.arguments = []
    proposal = DecisionProposal(
        action="buy",
        reason_summary="买",
        evidence_ids=["budget:final", "offer:chosen"],
        next_steps=[],
    )
    decision, issues = apply_decision_policy(proposal, context)
    assert decision.action == "need_info"
    assert any("没有任何角色观点" in issue for issue in issues)


def test_original_reason_is_preserved(cases, config, products):
    """否决时不能静默覆盖模型原话：用户必须看得到它原本想说什么。"""
    record = run_case(cases["sneakers_wait"], config)
    context = context_from_record(record, products)
    proposal = DecisionProposal(
        action="buy",
        reason_summary="省了 150 元，不买就亏了",
        evidence_ids=["budget:final", "offer:chosen"],
        next_steps=[],
    )
    decision, issues = apply_decision_policy(proposal, context)
    assert decision.action == "wait"
    assert "省了 150 元，不买就亏了" in decision.reason_summary
    assert "程序校验调整建议" in decision.reason_summary
    assert record.proposed_decision is not None  # 原始建议仍在 RunRecord 里


def test_low_urgency_advisory_does_not_change_action(cases, config, products):
    """必要性提醒只追加下一步，不替用户判定"该不该想要"。"""
    record = run_case(cases["sneakers_wait"], config)
    context = context_from_record(record, products)
    context.budget = context.budget.model_copy(update={"within_budget": True})
    proposal = DecisionProposal(
        action="buy",
        reason_summary="首场比赛要用，先买",
        evidence_ids=["budget:final", "offer:chosen"],
        next_steps=[],
    )
    decision, issues = apply_decision_policy(proposal, context)
    assert issues == []
    assert decision.action == "buy"
    assert any("替代" in step for step in decision.next_steps)


def test_unverified_offer_does_not_block_skip(cases, config, products):
    """方案未验证不是拒绝购买的理由：结论是 skip 时不该被改成 need_info。

    否则用户会被要求去补一个与"这次不该买"完全无关的运费信息。
    """
    record = run_case(cases["unknown_shipping"], config)
    context = context_from_record(record, products)
    assert context.offer is not None and context.offer.verified is False
    proposal = DecisionProposal(
        action="skip",
        reason_summary="已有两双同类鞋，这次需求不成立",
        evidence_ids=["input:profile"],
        next_steps=[],
    )
    decision, issues = apply_decision_policy(proposal, context)
    assert decision.action == "skip"
    assert decision.reason_summary == "已有两双同类鞋，这次需求不成立"
    # 仍然记账：记录违规 ≠ 必须改变结论，两个数分开统计。
    assert any("优惠方案尚未确认" in issue for issue in issues)


def test_claim_amounts_parsing():
    assert claim_amounts(["只需 500 元", "少付 25.5 元", "1,200 元的余额"]) == {50000, 2550, 120000}
    assert claim_amounts(["500块", "¥600", "￥700"]) == {50000, 60000, 70000}
    assert claim_amounts(["没有金额的句子"]) == set()


def test_hypothetical_amount_in_counterargument_does_not_block(cases, config, products):
    """counterargument 必须写反方的成立条件，含假设数字属正常，不能据此否决。"""
    record = run_case(cases["tissue_buy"], config)
    proposal = DecisionProposal(
        action="buy",
        reason_summary="纸巾本来就要买，凑单后少付 25 元",
        counterargument="如果月底还压着 1234 元的固定支出，这单就该往后推",
        evidence_ids=["budget:final", "offer:chosen"],
        next_steps=[],
    )
    decision, issues = apply_decision_policy(proposal, context_from_record(record, products))
    assert issues == []
    assert decision.action == "buy"


def test_non_money_integers_are_not_treated_as_amounts(cases, config, products):
    """days_remaining=20 不是金额；把它读成 0.2 元会让假金额蒙混过关。"""
    from budget_agent.decision_policy import evidence_amounts

    record = run_case(cases["tissue_buy"], config)
    amounts = evidence_amounts(context_from_record(record, products))
    assert 20 not in amounts
    assert 25500 in amounts
