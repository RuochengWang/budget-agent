"""D：工具调用策略；C 的求解器只负责计算，不能在这里重复实现。"""

from budget_agent.errors import ModuleNotReady
from budget_agent.model_client import ModelClient
from budget_agent.schemas import DealResult, RoleContext
from budget_agent.tools.registry import ToolRegistry


def run(context: RoleContext, model: ModelClient, tools: ToolRegistry) -> DealResult:
    """TODO(D)：选择工具、校验调用参数、必要时补查；总工具次数受 A 限制。

    返回优惠观点、方案与新证据。原始规则必须加入证据，供最终校验核对。
    """
    raise ModuleNotReady("TODO(D): agents.deal.run 尚未实现")
