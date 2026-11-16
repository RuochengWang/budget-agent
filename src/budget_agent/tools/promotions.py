"""C：活动快照加载和有效期过滤。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from budget_agent.schemas import Product, PromotionRule


def _load_products(data_dir: Path) -> dict[str, Product]:
    path = data_dir / "catalog" / "products.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    products = [Product.model_validate(row) for row in rows]
    return {product.id: product for product in products}


def _load_rules(data_dir: Path) -> list[PromotionRule]:
    path = data_dir / "catalog" / "promotions.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [PromotionRule.model_validate(row) for row in rows]


def get_promotion_rules(
    product_ids: list[str], as_of: datetime, *, data_dir: Path
) -> list[PromotionRule]:
    """按商品和时点筛选；有效时间为 [valid_from, valid_to)。"""
    catalog = _load_products(data_dir)
    wanted = set(product_ids)
    selected: list[PromotionRule] = []

    for rule in _load_rules(data_dir):
        if not (rule.valid_from <= as_of < rule.valid_to):
            continue

        overlap = wanted & set(rule.eligible_product_ids)
        if not overlap:
            continue

        overlap_merchants = {
            catalog[pid].merchant for pid in overlap if pid in catalog
        }
        if overlap_merchants and (
            len(overlap_merchants) > 1 or rule.merchant not in overlap_merchants
        ):
            continue

        selected.append(rule)

    return selected