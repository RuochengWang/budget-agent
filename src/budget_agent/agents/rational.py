"""B：必要性、机会成本和重复购买分析。

理性角色只引用预算工具已计算的金额，不自行估算余额、不编造事实。
初次发言发生在优惠方案之前，此时 budget.within_budget 为 None 是正常状态，
不可声称已复核付款或预算已通过。
"""

from budget_agent.agents.base import call_role
from budget_agent.model_client import ModelClient
from budget_agent.schemas import Argument, RoleContext


def run(context: RoleContext, model: ModelClient) -> Argument:
    """生成理性角色的结构化观点，role=rational。

    复用 base.call_role 读取版本化提示词并交给模型，模型按要求
    返回符合 Argument 的 JSON；随后做角色一致性校验。
    """
    argument = call_role("rational", context, model, Argument)

    # 角色一致性：理性节点必须返回 role=rational，否则视为异常。
    if argument.role != "rational":
        raise ValueError("理性角色返回了不匹配的 role")

    return argument
