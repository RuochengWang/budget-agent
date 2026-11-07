"""D：可选的一轮交叉回应；默认关闭，完成后再开启配置。"""

from budget_agent.errors import ModuleNotReady
from budget_agent.model_client import ModelClient
from budget_agent.schemas import Argument, RoleContext


def run(context: RoleContext, model: ModelClient) -> list[Argument]:
    """TODO(D)：返回简短的证据回应，不递归调用自己，不增加讨论轮次。"""
    raise ModuleNotReady("TODO(D): agents.cross_response.run 尚未实现")
