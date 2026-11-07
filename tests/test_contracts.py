import pytest
from pydantic import ValidationError

from budget_agent.schemas import CaseInput, UserProfile


@pytest.mark.parametrize("cash", [1.5, True, "100", -1])
def test_money_rejects_ambiguous_or_negative_input(cash):
    with pytest.raises(ValidationError):
        UserProfile(cash_cents=cash)


def test_missing_and_zero_remain_distinct():
    assert UserProfile().reserve_cents is None
    assert UserProfile(reserve_cents=0).reserve_cents == 0


def test_unknown_fields_rejected():
    with pytest.raises(ValidationError):
        UserProfile(balance=100)


def test_request_requires_timezone(cases):
    raw = cases["sneakers_wait"].model_dump(mode="json")
    raw["request"]["as_of"] = "2026-11-07T16:00:00"
    with pytest.raises(ValidationError):
        CaseInput.model_validate(raw)


@pytest.mark.parametrize("ids", [["tissue", "tissue"], ["sneakers"], [str(i) for i in range(9)]])
def test_addon_boundaries(cases, ids):
    raw = cases["sneakers_wait"].model_dump(mode="json")
    raw["request"]["needed_addon_ids"] = ids
    with pytest.raises(ValidationError):
        CaseInput.model_validate(raw)
