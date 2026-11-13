"""C：最多八个候选、每件最多一件的有限穷举优惠求解。"""

from __future__ import annotations

from datetime import datetime
from itertools import combinations
from typing import Any

from budget_agent.errors import AgentError
from budget_agent.schemas import OfferResult, OptimizationInput, Product, PromotionRule


def optimize_basket(request: OptimizationInput) -> OfferResult:
    """比较目标单买基准与所有合法购物篮，返回明细。"""
    catalog = {p.id: p for p in request.products}
    target_id = request.target_product_id

    if target_id not in catalog:
        raise AgentError(f"目标商品不存在：{target_id}")

    missing = [pid for pid in request.candidate_ids if pid not in catalog]
    if missing:
        raise AgentError(f"凑单候选不存在：{', '.join(missing)}")

    is_demo = all(p.is_demo for p in request.products) and all(
        r.is_demo for r in request.rules
    )

    if request.shipping_cents is None:
        return OfferResult(
            basket_ids=[target_id],
            verified=False,
            verification_method="unverified",
            is_demo=is_demo,
            unknowns=["运费未知，无法确认到手价"],
        )

    shipping = request.shipping_cents
    baseline = _best_offer_for_basket(
        [target_id], catalog, request.rules, shipping, request.as_of
    )
    if baseline is None:
        raise AgentError("无法计算单买基准方案")

    best = baseline
    excluded_reasons: list[str] = []

    for size in range(len(request.candidate_ids) + 1):
        for addon in combinations(request.candidate_ids, size):
            basket_ids = [target_id, *addon]
            offer = _best_offer_for_basket(
                list(basket_ids), catalog, request.rules, shipping, request.as_of
            )
            if offer is None:
                excluded_reasons.append(f"购物篮无可行方案：{list(basket_ids)}")
                continue
            if _is_better(offer, best):
                best = offer

    return OfferResult(
        basket_ids=best["basket_ids"],
        subtotal_cents=best["subtotal_cents"],
        discount_cents=best["discount_cents"],
        shipping_cents=shipping,
        payable_cents=best["payable_cents"],
        baseline_payable_cents=baseline["payable_cents"],
        rule_ids=best["rule_ids"],
        verified=True,
        verification_method="solver",
        is_demo=is_demo,
        unknowns=[],
        excluded_reasons=excluded_reasons,
    )


def _is_better(candidate: dict[str, Any], current: dict[str, Any]) -> bool:
    """并列时：付款更低 → 凑单更少 → basket_ids 字典序 → rule_ids 字典序。"""
    cand_key = (
        candidate["payable_cents"],
        len(candidate["basket_ids"]) - 1,
        tuple(sorted(candidate["basket_ids"])),
        tuple(sorted(candidate["rule_ids"])),
    )
    cur_key = (
        current["payable_cents"],
        len(current["basket_ids"]) - 1,
        tuple(sorted(current["basket_ids"])),
        tuple(sorted(current["rule_ids"])),
    )
    return cand_key < cur_key


def _best_offer_for_basket(
    basket_ids: list[str],
    catalog: dict[str, Product],
    rules: list[PromotionRule],
    shipping_cents: int,
    as_of: datetime,
) -> dict[str, Any] | None:
    merchants = {catalog[pid].merchant for pid in basket_ids}
    if len(merchants) != 1:
        return None
    merchant = next(iter(merchants))

    subtotal = sum(catalog[pid].price_cents for pid in basket_ids)
    usable_rules = [
        rule
        for rule in rules
        if rule.merchant == merchant
        and rule.valid_from <= as_of < rule.valid_to
        and set(basket_ids) & set(rule.eligible_product_ids)
    ]
    reductions = [r for r in usable_rules if r.kind == "reduction"]
    coupons = [r for r in usable_rules if r.kind == "coupon"]

    plans: list[tuple[list[PromotionRule], int]] = [([], 0)]

    for reduction in reductions:
        discount = _reduction_discount(reduction, basket_ids, catalog)
        if discount > 0:
            plans.append(([reduction], discount))

    for coupon in coupons:
        discount = _coupon_discount(coupon, basket_ids, catalog, reduction=None)
        if discount > 0:
            plans.append(([coupon], discount))

    for reduction in reductions:
        for coupon in coupons:
            if not (reduction.stackable and coupon.stackable):
                continue
            red_discount = _reduction_discount(reduction, basket_ids, catalog)
            if red_discount <= 0:
                continue
            coup_discount = _coupon_discount(
                coupon, basket_ids, catalog, reduction=reduction
            )
            total_discount = red_discount + coup_discount
            if total_discount > 0:
                plans.append(([reduction, coupon], total_discount))

    best: dict[str, Any] | None = None
    for applied_rules, discount in plans:
        discount = min(discount, subtotal)
        payable = subtotal - discount + shipping_cents
        offer = {
            "basket_ids": list(basket_ids),
            "subtotal_cents": subtotal,
            "discount_cents": discount,
            "payable_cents": payable,
            "rule_ids": [rule.id for rule in applied_rules],
        }
        if best is None or _is_better(offer, best):
            best = offer
    return best


def _eligible_amount(
    rule: PromotionRule, basket_ids: list[str], catalog: dict[str, Product]
) -> int:
    return sum(
        catalog[pid].price_cents
        for pid in basket_ids
        if pid in rule.eligible_product_ids
    )


def _reduction_discount(
    rule: PromotionRule, basket_ids: list[str], catalog: dict[str, Product]
) -> int:
    eligible = _eligible_amount(rule, basket_ids, catalog)
    if eligible < rule.threshold_cents:
        return 0
    return min(rule.discount_cents, eligible)


def _coupon_discount(
    rule: PromotionRule,
    basket_ids: list[str],
    catalog: dict[str, Product],
    reduction: PromotionRule | None,
) -> int:
    if rule.threshold_basis == "original_eligible":
        eligible = _eligible_amount(rule, basket_ids, catalog)
        if eligible < rule.threshold_cents:
            return 0
        return min(rule.discount_cents, eligible)

    # after_reduction_eligible：先按比例分摊满减，再检查券门槛
    prices = {
        pid: catalog[pid].price_cents
        for pid in basket_ids
        if pid in (reduction.eligible_product_ids if reduction else [])
    }
    red_discount = (
        _reduction_discount(reduction, basket_ids, catalog) if reduction else 0
    )
    allocated = _allocate_discount(prices, red_discount) if reduction else {}

    remaining_eligible = 0
    for pid in basket_ids:
        if pid not in rule.eligible_product_ids:
            continue
        remaining_eligible += catalog[pid].price_cents - allocated.get(pid, 0)

    if remaining_eligible < rule.threshold_cents:
        return 0
    return min(rule.discount_cents, remaining_eligible)


def _allocate_discount(prices: dict[str, int], discount: int) -> dict[str, int]:
    """按价格比例把满减分摊到整数分；剩余分按余数降序、ID 升序分配。"""
    if not prices or discount <= 0:
        return {pid: 0 for pid in prices}

    total_price = sum(prices.values())
    discount = min(discount, total_price)
    floors = {pid: (discount * price) // total_price for pid, price in prices.items()}
    remain = discount - sum(floors.values())

    order = sorted(
        prices.keys(),
        key=lambda pid: (-(discount * prices[pid] % total_price), pid),
    )
    result = dict(floors)
    for pid in order:
        if remain <= 0:
            break
        room = prices[pid] - result[pid]
        if room <= 0:
            continue
        take = min(room, remain)
        result[pid] += take
        remain -= take
    return result