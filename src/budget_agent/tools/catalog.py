"""C 负责商品查询。接口中的 data_dir 由 A 注入，不接受模型传入路径。"""

from pathlib import Path

from budget_agent.errors import ModuleNotReady
from budget_agent.schemas import Product


def search_products(query: str, limit: int = 5, *, data_dir: Path) -> list[Product]:
    """TODO(C)：从本地快照查商品；联网适配仍返回同一结构。"""
    raise ModuleNotReady("TODO(C): tools.catalog.search_products 尚未实现")


def get_products(product_ids: list[str], *, data_dir: Path) -> list[Product]:
    """TODO(C)：按 ID 精确取商品；未知 ID 应报错，不用模糊搜索悄悄替代。"""
    raise ModuleNotReady("TODO(C): tools.catalog.get_products 尚未实现")
