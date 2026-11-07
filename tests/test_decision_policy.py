import pytest

from budget_agent.decision_policy import apply_decision_policy
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
