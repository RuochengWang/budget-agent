"""B 负责。详见 docs/roles/B.md 与 docs/contracts.md。"""

from budget_agent.errors import ModuleNotReady
from budget_agent.schemas import BudgetResult, UserProfile


def calculate_budget(profile: UserProfile, payable_cents: int | None = None) -> BudgetResult:
    """计算基本支出、可支配金额，并可按最终付款额复核。

    TODO(B)：缺字段返回 missing_fields；未提供付款额时 within_budget=None。
    可支配金额和购买后现金允许为负；输入不能被原地修改。
    零预留金有效，None 不是零。示例与边界见角色文档。
    """
    raise ModuleNotReady("TODO(B): tools.budget.calculate_budget 尚未实现")
