"""C 的手工预期验收；不调用 demo 或用被测求解器生成答案。"""

import pytest

from budget_agent.errors import ModuleNotReady
from budget_agent.schemas import OptimizationInput
from budget_agent.tools.optimizer import optimize_basket

pytestmark = pytest.mark.xfail(
    raises=ModuleNotReady, strict=True, reason="C 的正式求解器待实现；完成后移除此标记"
)


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
