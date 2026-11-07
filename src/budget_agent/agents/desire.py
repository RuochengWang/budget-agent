"""D：购买价值与主观收益。"""

from budget_agent.errors import ModuleNotReady
from budget_agent.model_client import ModelClient
from budget_agent.schemas import Argument, RoleContext


def run(context: RoleContext, model: ModelClient) -> Argument:
    """TODO(D)：返回 role=desire 的观点；事实引用已有 evidence ID。"""
    raise ModuleNotReady("TODO(D): agents.desire.run 尚未实现")
