"""B：必要性、机会成本和重复购买分析。"""

from budget_agent.errors import ModuleNotReady
from budget_agent.model_client import ModelClient
from budget_agent.schemas import Argument, RoleContext


def run(context: RoleContext, model: ModelClient) -> Argument:
    """TODO(B)：使用预算工具结果；付款额未知时不得声称已通过预算。"""
    raise ModuleNotReady("TODO(B): agents.rational.run 尚未实现")
