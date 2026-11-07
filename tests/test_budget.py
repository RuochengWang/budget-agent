"""B 的独立验收起点。实现后移除严格 xfail，而不是将其留作成功标记。"""

import pytest

from budget_agent.errors import ModuleNotReady
from budget_agent.tools.budget import calculate_budget

pytestmark = pytest.mark.xfail(
    raises=ModuleNotReady, strict=True, reason="B 的正式预算待实现；完成后移除此标记"
)


def test_initial_budget_does_not_claim_payment_pass(cases):
    result = calculate_budget(cases["sneakers_wait"].profile)
    assert result.essential_total_cents == 80000
    assert result.discretionary_cents == 30000
    assert result.within_budget is None
    assert result.remaining_cash_cents is None


@pytest.mark.parametrize("payable,remaining,within", [(65000, 55000, False), (30000, 90000, True)])
def test_final_payment_boundary(cases, payable, remaining, within):
    result = calculate_budget(cases["sneakers_wait"].profile, payable)
    assert result.remaining_cash_cents == remaining
    assert result.within_budget is within


def test_negative_discretionary_is_preserved(cases):
    profile = cases["sneakers_wait"].profile.model_copy(update={"cash_cents": 50000})
    assert calculate_budget(profile).discretionary_cents == -40000


def test_fixed_expense_changes_available_budget(cases):
    profile = cases["sneakers_wait"].profile.model_copy(update={"fixed_expenses_cents": 5000})
    result = calculate_budget(profile)
    assert result.essential_total_cents == 85000
    assert result.discretionary_cents == 25000


def test_missing_reserve_is_not_zero(cases):
    result = calculate_budget(cases["missing_profile"].profile, 100)
    assert "reserve_cents" in result.missing_fields
    assert result.within_budget is None


def test_zero_reserve_and_zero_days_are_valid(cases):
    profile = cases["sneakers_wait"].profile.model_copy(
        update={"reserve_cents": 0, "days_remaining": 0}
    )
    result = calculate_budget(profile, 120000)
    assert result.discretionary_cents == 120000
    assert result.within_budget is True
