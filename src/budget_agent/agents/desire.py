"""D：购买价值与主观收益。

职责边界（写在这里，避免后人改坏）：
1. 只谈需求、偏好与使用价值，不谈"划不划算"。预算结论由 B 的工具与最终校验给出；
   欲望角色一旦开始算钱，四角色就退化成四份语气不同的作文，对照实验也失去意义。
   **做法是结构性隔离，不是提示词自觉**：`build_payload` 会把 `budget` 整个键从上下文里
   删掉，模型连"余额有多少"这个字段都看不到 —— 看不到的数字编不出来，比"看到但要求别说"
   可靠得多。（A 的 `RoleContext` 里确实有 budget，此处只改本节点发出的 payload，
   不动公共契约。）
2. 事实必须引用已有 evidence ID。模型编造的 ID 在这里剔除，并写进 unknowns 留痕；
   静默删除会让报告里的「虚构引用率」无从统计。
"""

from budget_agent.agents.base import PROMPT_DIR
from budget_agent.errors import AgentError
from budget_agent.model_client import ModelClient
from budget_agent.schemas import Argument, RoleContext


def known_evidence_ids(context: RoleContext) -> set[str]:
    return {item.id for item in context.evidence}


def filter_evidence_ids(ids: list[str], known: set[str]) -> tuple[list[str], list[str]]:
    """返回 (保留的 ID, 被剔除的 ID)，同时去重并保持原顺序。"""
    kept: list[str] = []
    dropped: list[str] = []
    for raw in ids:
        if raw in kept or raw in dropped:
            continue
        (kept if raw in known else dropped).append(raw)
    return kept, dropped


def build_payload(context: RoleContext) -> dict:
    """发给模型的上下文；刻意剔除 budget，保证角色隔离是结构性的。

    没有走 `call_role`（它固定发 `context.model_dump()`），代价是本节点少了一层
    公共封装，收益是"欲望角色看不到余额"这条约束不依赖模型自觉。测试
    `test_desire_payload_has_no_budget` 会锁住这个行为。
    """
    payload = context.model_dump(mode="json")
    payload.pop("budget", None)
    return payload


def run(context: RoleContext, model: ModelClient) -> Argument:
    prompt = (PROMPT_DIR / "desire.md").read_text(encoding="utf-8")
    argument = model.generate_json("desire", prompt, build_payload(context), Argument)
    if argument.role != "desire":
        raise AgentError("欲望角色返回了不匹配的 role")

    kept, dropped = filter_evidence_ids(argument.evidence_ids, known_evidence_ids(context))
    unknowns = list(argument.unknowns)
    if dropped:
        unknowns.append("已忽略上下文中不存在的证据引用：" + "、".join(dropped))
    return argument.model_copy(update={"evidence_ids": kept, "unknowns": unknowns})
