"""E 组织，A/B/C/D 配合。不得用演示替身冒充任何基线。"""

from budget_agent.errors import ModuleNotReady
from budget_agent.schemas import CaseInput, RunRecord

BASELINES = ("B0", "B1", "B2", "M", "M_no_cross")


def run_baseline(name: str, case: CaseInput) -> RunRecord:
    """TODO(E)：B0 规则；B1 单模型；B2 单 agent+工具；M 全系统。

    M_no_cross 为关闭交叉回应的消融。模型与数据快照需一致。
    """
    if name not in BASELINES:
        raise ValueError("未知基线")
    raise ModuleNotReady(f"TODO(E): {name} 基线尚未实现，不能产生实验结果")
