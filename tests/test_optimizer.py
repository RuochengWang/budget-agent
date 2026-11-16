"""C 的手工预期验收；不调用 demo 或用被测求解器生成答案。"""

from datetime import datetime

import pytest

from budget_agent.schemas import OptimizationInput, PromotionRule
from budget_agent.tools.optimizer import optimize_basket


@pytest.mark.parametrize(
    "addons,basket,payable",
    [
        ([], ["daily_goods"], 28000),
        (["tissue"], ["daily_goods", "tissue"], 25500),
        (["large_addon"], ["daily_goods"], 28000),
    ],
)
def test_total_spending_not_coupon_face_value(cases, products, rules, addons, basket, payable):
    result = optimize_basket(
        OptimizationInput(
            target_product_id="daily_goods",
            candidate_ids=addons,
            products=products,
            rules=rules,
            shipping_cents=0,
            as_of=cases["tissue_buy"].request.as_of,
        )
    )
    assert sorted(result.basket_ids) == sorted(basket)
    assert result.payable_cents == payable
    assert result.baseline_payable_cents == 28000
    assert result.verified
    assert result.verification_method == "solver"


def test_unknown_shipping_is_not_zero(cases, products, rules):
    result = optimize_basket(
        OptimizationInput(
            target_product_id="daily_goods",
            candidate_ids=["tissue"],
            products=products,
            rules=rules,
            shipping_cents=None,
            as_of=cases["tissue_buy"].request.as_of,
        )
    )
    assert not result.verified
    assert result.payable_cents is None
    assert result.unknowns

def test_expired_rules_are_ignored(cases, products, rules):
    """活动恰好到期后不能再用；允许原价单买。"""
    result = optimize_basket(
        OptimizationInput(
            target_product_id="daily_goods",
            candidate_ids=["tissue"],
            products=products,
            rules=rules,
            shipping_cents=0,
            as_of=datetime.fromisoformat("2026-12-01T00:00:00+08:00"),
        )
    )
    assert result.verified
    assert result.rule_ids == []
    assert result.payable_cents == 28000
    assert result.basket_ids == ["daily_goods"]


def test_non_stackable_rules_are_not_combined(cases, products):
    """两条都不可叠加时，只能选其中更优的一条，不能同时用。"""
    as_of = cases["tissue_buy"].request.as_of
    local_rules = [
        PromotionRule(
            id="daily-50",
            kind="reduction",
            merchant="demo-shop",
            eligible_product_ids=["daily_goods", "tissue"],
            threshold_cents=30000,
            discount_cents=5000,
            stackable=False,
            threshold_basis="original_eligible",
            valid_from=datetime.fromisoformat("2026-11-01T00:00:00+08:00"),
            valid_to=datetime.fromisoformat("2026-12-01T00:00:00+08:00"),
            source_url=None,
            is_demo=True,
        ),
        PromotionRule(
            id="daily-coupon-20",
            kind="coupon",
            merchant="demo-shop",
            eligible_product_ids=["daily_goods", "tissue"],
            threshold_cents=20000,
            discount_cents=2000,
            stackable=False,
            threshold_basis="original_eligible",
            valid_from=datetime.fromisoformat("2026-11-01T00:00:00+08:00"),
            valid_to=datetime.fromisoformat("2026-12-01T00:00:00+08:00"),
            source_url=None,
            is_demo=True,
        ),
    ]
    result = optimize_basket(
        OptimizationInput(
            target_product_id="daily_goods",
            candidate_ids=["tissue"],
            products=products,
            rules=local_rules,
            shipping_cents=0,
            as_of=as_of,
        )
    )
    assert result.verified
    assert result.payable_cents == 25500
    assert result.rule_ids == ["daily-50"]
    assert "daily-coupon-20" not in result.rule_ids

def test_stackable_rules_can_combine(cases, products):
    """两条都可叠加时，满减和券可以一起用。"""
    as_of = cases["tissue_buy"].request.as_of
    local_rules = [
        PromotionRule(
            id="daily-50",
            kind="reduction",
            merchant="demo-shop",
            eligible_product_ids=["daily_goods", "tissue"],
            threshold_cents=30000,
            discount_cents=5000,
            stackable=True,
            threshold_basis="original_eligible",
            valid_from=datetime.fromisoformat("2026-11-01T00:00:00+08:00"),
            valid_to=datetime.fromisoformat("2026-12-01T00:00:00+08:00"),
            source_url=None,
            is_demo=True,
        ),
        PromotionRule(
            id="daily-coupon-20",
            kind="coupon",
            merchant="demo-shop",
            eligible_product_ids=["daily_goods", "tissue"],
            threshold_cents=20000,
            discount_cents=2000,
            stackable=True,
            threshold_basis="original_eligible",
            valid_from=datetime.fromisoformat("2026-11-01T00:00:00+08:00"),
            valid_to=datetime.fromisoformat("2026-12-01T00:00:00+08:00"),
            source_url=None,
            is_demo=True,
        ),
    ]
    result = optimize_basket(
        OptimizationInput(
            target_product_id="daily_goods",
            candidate_ids=["tissue"],
            products=products,
            rules=local_rules,
            shipping_cents=0,
            as_of=as_of,
        )
    )
    assert result.verified
    assert result.payable_cents == 23500  # 30500 - 5000 - 2000
    assert sorted(result.rule_ids) == ["daily-50", "daily-coupon-20"]
