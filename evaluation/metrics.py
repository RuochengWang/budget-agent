"""E：指标须与人工复核标签比较；未实现时不返回 0 或 100%。"""

from budget_agent.errors import ModuleNotReady
from budget_agent.schemas import RunRecord


def compute_metrics(records: list[RunRecord], labels: list[dict]) -> dict:
    """TODO(E)：报告各指标有效样本数与分母；缺失标签不能计为正确。"""
    raise ModuleNotReady("TODO(E): 评测指标尚未实现")
