"""C 负责商品查询。接口中的 data_dir 由 A 注入，不接受模型传入路径。"""

from __future__ import annotations

import json
from pathlib import Path

from budget_agent.errors import AgentError
from budget_agent.schemas import Product


def _load_products(data_dir: Path) -> dict[str, Product]:
    path = data_dir / "catalog" / "products.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    products = [Product.model_validate(row) for row in rows]
    return {product.id: product for product in products}


def search_products(query: str, limit: int = 5, *, data_dir: Path) -> list[Product]:
    """从本地快照查商品；联网适配仍返回同一结构。"""
    products = _load_products(data_dir).values()
    matched = [
        product
        for product in products
        if query in product.name or query == product.id
    ]
    return matched[:limit]


def get_products(product_ids: list[str], *, data_dir: Path) -> list[Product]:
    """按 ID 精确取商品；未知 ID 应报错，不用模糊搜索悄悄替代。"""
    catalog = _load_products(data_dir)
    missing = [pid for pid in product_ids if pid not in catalog]
    if missing:
        raise AgentError(f"商品快照中不存在指定 ID：{', '.join(missing)}")
    return [catalog[pid] for pid in product_ids]