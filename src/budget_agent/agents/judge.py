"""D：生成建议；最终购买动作仍由程序校验。

裁判只负责"解释取舍"，不负责"保证正确"：
- 不做多数票：`DecisionProposal` 里根本没有票数字段，谁声音大不影响结论；
- 不改写金额：金额来自 offer 与 budget 的证据，裁判引用的 ID 必须存在；
- 自己不做硬约束判断（那是 decision_policy 的事）。两者分开，才能在报告里给出
  「校验前违规率」与「校验后违规率」两个不同的数。
"""

from budget_agent.agents.base import call_role
from budget_agent.agents.desire import filter_evidence_ids, known_evidence_ids
from budget_agent.model_client import ModelClient
from budget_agent.schemas import DecisionProposal, RoleContext


def run(context: RoleContext, model: ModelClient) -> DecisionProposal:
    proposal = call_role("judge", context, model, DecisionProposal)

    kept, dropped = filter_evidence_ids(proposal.evidence_ids, known_evidence_ids(context))
    next_steps = list(proposal.next_steps)
    if dropped:
        # 留痕而不是静默删除：这些 ID 会进 RunRecord，报告里可以统计。
        next_steps.append("裁判引用了不存在的证据，已剔除：" + "、".join(dropped))
    return proposal.model_copy(update={"evidence_ids": kept, "next_steps": next_steps})
