"""D：可选的一轮交叉回应；默认关闭，完成后再由 A 打开配置。

四条硬限制都写在代码里，不靠提示词自觉：
1. 每个角色最多一条，总数 ≤ 2（只有欲望与理性会回应；优惠节点已经给了数字，
   裁判要在回应之后才发言，让它回应等于给自己递话）；
2. 必须针对**另一个角色**的某条主张，不能自说自话；
3. 复读丢弃：回应文本与已有主张或已有回应重合即视为无新信息；
4. 回应同样要过证据白名单，且至少引用一条证据 —— 没有依据的回应不算"有实际信息"。

结构上就没有递归入口，所以不可能出现"无限辩论"。
"""

from typing import Literal

from pydantic import Field

from budget_agent.agents.base import PROMPT_DIR
from budget_agent.agents.desire import filter_evidence_ids, known_evidence_ids
from budget_agent.errors import AgentError
from budget_agent.model_client import ModelClient
from budget_agent.schemas import Argument, Contract, RoleContext

SPEAKERS: tuple[str, ...] = ("desire", "rational")
MAX_REPLIES = len(SPEAKERS)
MIN_TEXT_LENGTH = 8


class CrossReply(Contract):
    """一次交叉回应的结构化输出。"""

    role: Literal["desire", "rational"]
    answers_role: Literal["desire", "rational", "deal"]
    stance: Literal["support", "oppose", "neutral"]
    claim: str = Field(min_length=MIN_TEXT_LENGTH)
    evidence_ids: list[str] = Field(min_length=1)


def _normalise(text: str) -> str:
    return "".join(text.split())


def _is_repeat(text: str, seen: set[str]) -> bool:
    """与已知文本高度重合即视为复读：完全包含关系足够，不做语义相似度。"""
    current = _normalise(text)
    if len(current) < MIN_TEXT_LENGTH:
        return True
    return any(current == other or current in other or other in current for other in seen)


def load_prompt() -> str:
    return (PROMPT_DIR / "cross_response.md").read_text(encoding="utf-8")


def run(context: RoleContext, model: ModelClient) -> list[Argument]:
    speakers = {argument.role: argument for argument in context.arguments}
    if len(speakers) < 2:
        raise AgentError("交叉回应至少需要两个已有观点")

    known = known_evidence_ids(context)
    seen = {
        _normalise(claim) for argument in context.arguments for claim in argument.claims
    }
    prompt = load_prompt()
    replies: list[Argument] = []

    for speaker, own in speakers.items():
        if speaker not in SPEAKERS or len(replies) >= MAX_REPLIES:
            continue
        others = [
            {"role": role, "claims": argument.claims, "evidence_ids": argument.evidence_ids}
            for role, argument in speakers.items()
            if role != speaker
        ]
        payload = {
            "speaking_as": speaker,
            "my_claims": own.claims,
            "their_claims": others,
            "already_said": [claim for reply in replies for claim in reply.claims],
            "case": context.case.model_dump(mode="json"),
            "budget": context.budget.model_dump(mode="json"),
        }
        if speaker == "desire":
            # 与 desire.run 保持同一条隔离规则：欲望角色回应时同样拿不到预算数字，
            # 否则"第一轮看不到、第二轮看得到"会让隔离形同虚设。
            payload.pop("budget")
        try:
            reply = model.generate_json("cross_response", prompt, payload, CrossReply)
        except AgentError:
            continue  # 单个角色回应失败不拖垮整次运行，由下面的汇总判断
        if reply.role != speaker or reply.answers_role == speaker:
            continue
        if reply.answers_role not in speakers:
            continue
        if _is_repeat(reply.claim, seen):
            continue
        evidence_ids, _ = filter_evidence_ids(reply.evidence_ids, known)
        if not evidence_ids:
            continue
        seen.add(_normalise(reply.claim))
        replies.append(
            Argument(
                role=speaker,
                stance=reply.stance,
                claims=[f"（回应{reply.answers_role}）{reply.claim.strip()}"],
                evidence_ids=evidence_ids,
                unknowns=[],
            )
        )

    if not replies:
        raise AgentError("一轮交叉回应没有产生任何有效内容")
    return replies
