"""C：活动快照加载和有效期过滤。"""

from datetime import datetime
from pathlib import Path

from budget_agent.errors import ModuleNotReady
from budget_agent.schemas import PromotionRule


def get_promotion_rules(
    product_ids: list[str], as_of: datetime, *, data_dir: Path
) -> list[PromotionRule]:
    """TODO(C)：按商品和时点筛选；有效时间为 [valid_from, valid_to)。"""
    raise ModuleNotReady("TODO(C): tools.promotions.get_promotion_rules 尚未实现")
