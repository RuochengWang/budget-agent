"""C 优惠求解器的补充回归测试；金额均为整数分。

两个问题：叠加优惠不得超过参与商品剩余金额；满减余数按排名逐分分配。
固定输入与预期结果经人工复算，不使用求解器生成标准答案。
修复前这些用例会失败；修复后应全部通过，不使用 xfail 跳过。
"""

from datetime import datetime

import pytest

from budget_agent.schemas import OptimizationInput, Product, PromotionRule
from budget_agent.tools.optimizer import _allocate_discount, optimize_basket

AS_OF = datetime.fromisoformat("2026-11-16T12:00:00+08:00")
VALID_FROM = datetime.fromisoformat("2026-11-01T00:00:00+08:00")
VALID_TO = datetime.fromisoformat("2026-12-01T00:00:00+08:00")


def _product(product_id: str, price_cents: int) -> Product:
    return Product(
        id=product_id,
        name=product_id,
        price_cents=price_cents,
        merchant="review-shop",
        source_url=None,
        observed_at=AS_OF,
        is_demo=True,
    )


def _rule(rule_id, kind, eligible_ids, threshold, discount, basis="original_eligible"):
    return PromotionRule(
        id=rule_id,
        kind=kind,
        merchant="review-shop",
        eligible_product_ids=eligible_ids,
        threshold_cents=threshold,
        discount_cents=discount,
        stackable=True,
        threshold_basis=basis,
        valid_from=VALID_FROM,
        valid_to=VALID_TO,
        source_url=None,
        is_demo=True,
    )


def test_stacked_coupon_cannot_discount_unrelated_target():
    """100 元目标 + 100 元凑单品；仅凑单品享受两次减 90 元，最优仍付 100 元。"""
    request = OptimizationInput(
        target_product_id="target",
        candidate_ids=["addon"],
        products=[_product("target", 10000), _product("addon", 10000)],
        rules=[
            _rule("reduction", "reduction", ["addon"], 10000, 9000),
            _rule("coupon", "coupon", ["addon"], 10000, 9000),
        ],
        shipping_cents=0,
        as_of=AS_OF,
    )

    result = optimize_basket(request)

    assert result.verified
    assert result.baseline_payable_cents == 10000
    assert result.payable_cents == 10000
    assert result.basket_ids == ["target"]


def test_allocation_tied_remainders_use_id_order_one_cent_each():
    """203 / 3 各取 67 分，余下 2 分应依次给 a、b，各 1 分。"""
    prices = {"c": 100, "b": 100, "a": 100}

    allocated = _allocate_discount(prices, 203)

    assert allocated == {"a": 68, "b": 68, "c": 67}


@pytest.mark.parametrize(
    "coupon_threshold,expected_payable,expected_basket",
    [
        pytest.param(32, 65, ["a", "b", "c"], id="threshold-exactly-met"),
        pytest.param(33, 67, ["b"], id="threshold-short-by-one-cent"),
    ],
)
def test_after_reduction_coupon_threshold_boundary(
    coupon_threshold, expected_payable, expected_basket
):
    """满减分摊后 b 剩 32 分：门槛 32 可用，门槛 33 不可用。"""
    request = OptimizationInput(
        target_product_id="b",
        candidate_ids=["a", "c"],
        products=[_product("a", 100), _product("b", 100), _product("c", 100)],
        rules=[
            _rule("reduction", "reduction", ["a", "b", "c"], 300, 203),
            _rule(
                "coupon",
                "coupon",
                ["b"],
                coupon_threshold,
                33,
                basis="after_reduction_eligible",
            ),
        ],
        shipping_cents=0,
        as_of=AS_OF,
    )

    result = optimize_basket(request)

    assert result.verified
    assert result.baseline_payable_cents == 67
    assert result.payable_cents == expected_payable
    assert sorted(result.basket_ids) == expected_basket