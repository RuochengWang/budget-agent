"""D：生成建议；最终购买动作仍由程序校验。"""

from budget_agent.errors import ModuleNotReady
from budget_agent.model_client import ModelClient
from budget_agent.schemas import DecisionProposal, RoleContext


def run(context: RoleContext, model: ModelClient) -> DecisionProposal:
    """TODO(D)：结合全部论点和最终预算，返回建议与反方观点。"""
    raise ModuleNotReady("TODO(D): agents.judge.run 尚未实现")
