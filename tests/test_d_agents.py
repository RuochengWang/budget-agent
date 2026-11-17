"""D 负责的四个节点的单元测试（欲望 / 优惠 / 裁判 / 交叉回应）。

与 `test_workflow.py` 的分工：那边验证总控在 demo 模式下能跑通，用的全是 scripted 替身；
这里直接测 D 的正式模块，用 FakeModel 喂"模型可能说错的输出"，验证程序侧的兜底行为。
不依赖 C 与 B 的正式实现（它们仍是 TODO），所以现在就能跑。
"""

from time import monotonic

import pytest

from budget_agent.agents import cross_response, deal, desire, judge
from budget_agent.config import PROJECT_ROOT
from budget_agent.demo import DemoCatalog, calculate_demo_budget
from budget_agent.errors import AgentError, ToolLimitReached
from budget_agent.schemas import (
    Argument,
    Evidence,
    ModelTrace,
    OfferResult,
    Product,
    PromotionRule,
    RoleContext,
)
from budget_agent.tools.registry import ToolRegistry
from budget_agent.workflow import OptimizeArgs, PromotionArgs


class ScriptModel:
    """按顺序回放预设输出；每条都会被 response_type 校验，与真实客户端一致。"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.traces: list[ModelTrace] = []

    def generate_json(self, role, prompt, payload, response_type):
        if not self.responses:
            raise AgentError("测试脚本已用完")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        self.traces.append(ModelTrace(role=role, model="test/scripted", elapsed_ms=0))
        return response_type.model_validate(item)


def make_registry(max_calls: int = 6) -> ToolRegistry:
    data = DemoCatalog(PROJECT_ROOT / "data")
    tools = ToolRegistry(max_calls, monotonic() + 60)
    tools.register(
        "get_promotion_rules", PromotionArgs, list[PromotionRule], data.get_promotion_rules
    )
    tools.register("optimize_basket", OptimizeArgs, OfferResult, data.optimize_basket)
    return tools


def build_context(case, products: list[Product]) -> RoleContext:
    wanted = {case.request.target_product_id, *case.request.needed_addon_ids}
    selected = [p for p in products if p.id in wanted]
    budget = calculate_demo_budget(case.profile)
    evidence = [
        Evidence(
            id="input:request",
            kind="input",
            description="用户购买需求",
            facts=case.request.model_dump(mode="json"),
        ),
        Evidence(
            id="input:profile",
            kind="input",
            description="用户预算输入",
            facts=case.profile.model_dump(mode="json"),
        ),
        Evidence(
            id="budget:initial",
            kind="budget",
            description="购买前预算",
            facts=budget.model_dump(mode="json"),
        ),
        *[
            Evidence(
                id=f"product:{p.id}",
                kind="product",
                description=p.name,
                facts=p.model_dump(mode="json"),
                is_demo=p.is_demo,
            )
            for p in selected
        ],
    ]
    return RoleContext(case=case, products=selected, budget=budget, evidence=evidence)


def deal_argument(**overrides) -> dict:
    payload = {
        "role": "deal",
        "stance": "support",
        "claims": ["加一包纸巾跨过门槛，总付款比单买低"],
        "evidence_ids": ["offer:chosen"],
        "unknowns": [],
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------- 欲望角色
def test_desire_keeps_unknown_evidence_for_policy(cases, products):
    context = build_context(cases["tissue_buy"], products)
    model = ScriptModel(
        [
            {
                "role": "desire",
                "stance": "support",
                "claims": ["纸巾宿舍快用完了，日用品也是刚需"],
                "evidence_ids": ["input:request", "product:made-up"],
                "unknowns": [],
            }
        ]
    )
    argument = desire.run(context, model)
    assert argument.evidence_ids == ["input:request", "product:made-up"]
    assert any("product:made-up" in item for item in argument.unknowns)


def test_desire_rejects_mismatched_role(cases, products):
    context = build_context(cases["tissue_buy"], products)
    model = ScriptModel(
        [
            {
                "role": "judge",
                "stance": "support",
                "claims": ["越界"],
                "evidence_ids": [],
                "unknowns": [],
            }
        ]
    )
    with pytest.raises(AgentError):
        desire.run(context, model)


def test_desire_payload_has_no_budget(cases, products):
    """角色隔离必须是结构性的：发给欲望角色的上下文里根本没有 budget 这个键。"""

    class CaptureModel:
        def __init__(self, item):
            self.item = item
            self.payload = None
            self.traces: list[ModelTrace] = []

        def generate_json(self, role, prompt, payload, response_type):
            self.payload = payload
            self.traces.append(ModelTrace(role=role, model="test/capture", elapsed_ms=0))
            return response_type.model_validate(self.item)

    context = build_context(cases["tissue_buy"], products)
    model = CaptureModel(
        {
            "role": "desire",
            "stance": "support",
            "claims": ["纸巾该补了"],
            "evidence_ids": ["input:request"],
            "unknowns": [],
        }
    )
    desire.run(context, model)
    assert "budget" not in model.payload
    assert "evidence" in model.payload and "case" in model.payload


def test_desire_does_not_touch_budget_numbers(cases, products):
    """欲望角色只做证据过滤，不读取、不改写预算字段。"""
    context = build_context(cases["tissue_buy"], products)
    model = ScriptModel(
        [
            {
                "role": "desire",
                "stance": "neutral",
                "claims": ["想换新的"],
                "evidence_ids": [],
                "unknowns": ["使用频率"],
            }
        ]
    )
    argument = desire.run(context, model)
    assert argument.unknowns == ["使用频率"]
    assert argument.evidence_ids == []


# --------------------------------------------------------------------- 优惠节点
def test_deal_runs_fixed_sequence_and_exports_evidence(cases, products):
    context = build_context(cases["tissue_buy"], products)
    tools = make_registry()
    result = deal.run(context, ScriptModel([deal_argument()]), tools)

    assert [trace.name for trace in tools.traces] == ["get_promotion_rules", "optimize_basket"]
    assert result.offer.payable_cents == 25500
    assert result.offer.baseline_payable_cents == 28000
    ids = {item.id for item in result.evidence}
    assert "offer:chosen" in ids
    assert "promotion:daily-50" in ids
    assert result.argument.role == "deal"


def test_deal_never_recomputes_money_itself(cases, products):
    """求解器说 25500 就是 25500；即使模型在观点里写别的数，offer 也不受影响。"""
    context = build_context(cases["tissue_buy"], products)
    tools = make_registry()
    model = ScriptModel([deal_argument(claims=["大概两百块就能拿下吧"])])
    result = deal.run(context, model, tools)
    assert result.offer.payable_cents == 25500


def test_deal_checks_remaining_quota_before_calling(cases, products):
    """额度必须预留给 A 的最终预算复算；不够时明确退出，不试探。"""
    context = build_context(cases["tissue_buy"], products)
    tools = make_registry(max_calls=2)  # 2 - 0 - 1(留给 A) = 1，不够"查询 + 求解"两次
    with pytest.raises(ToolLimitReached):
        deal.run(context, ScriptModel([deal_argument()]), tools)
    assert tools.traces == []


def test_deal_reports_offer_unknowns(cases, products):
    context = build_context(cases["unknown_shipping"], products)
    tools = make_registry()
    result = deal.run(context, ScriptModel([deal_argument()]), tools)
    assert result.offer.verified is False
    assert result.offer.payable_cents is None
    assert any("运费" in item for item in result.argument.unknowns)


def test_deal_rejects_mismatched_role(cases, products):
    context = build_context(cases["tissue_buy"], products)
    tools = make_registry()
    with pytest.raises(AgentError):
        deal.run(context, ScriptModel([deal_argument(role="judge")]), tools)


# --------------------------------------------------------------------- 裁判
def test_judge_preserves_original_proposal_for_policy(cases, products):
    context = build_context(cases["tissue_buy"], products)
    model = ScriptModel(
        [
            {
                "action": "wait",
                "reason_summary": "先攒钱",
                "counterargument": "如果想立刻用，等生活费到账也不算久",
                "evidence_ids": ["budget:initial", "made-up"],
                "next_steps": ["等三天"],
            }
        ]
    )
    proposal = judge.run(context, model)
    assert proposal.evidence_ids == ["budget:initial", "made-up"]
    assert proposal.next_steps == ["等三天"]


# --------------------------------------------------------------------- 交叉回应
def two_arguments() -> list[Argument]:
    return [
        Argument(
            role="desire",
            stance="support",
            claims=["纸巾宿舍确实快用完了，顺手买一包合理"],
            evidence_ids=["input:request"],
        ),
        Argument(
            role="rational",
            stance="oppose",
            claims=["凑单容易变成多买，先确认是不是真的需要"],
            evidence_ids=["input:profile"],
        ),
    ]


def cross_context(cases, products, arguments=None) -> RoleContext:
    context = build_context(cases["tissue_buy"], products)
    return context.model_copy(update={"arguments": arguments or two_arguments()})


def test_cross_response_one_reply_per_role(cases, products):
    context = cross_context(cases, products)
    model = ScriptModel(
        [
            {
                "role": "desire",
                "answers_role": "rational",
                "stance": "neutral",
                "claim": "接受这一点，但纸巾本来就写在采购清单里",
                "evidence_ids": ["input:request"],
            },
            {
                "role": "rational",
                "answers_role": "desire",
                "stance": "oppose",
                "claim": "清单里有写，不等于这次非得和日用品一起下单",
                "evidence_ids": ["input:profile"],
            },
        ]
    )
    replies = cross_response.run(context, model)
    assert [reply.role for reply in replies] == ["desire", "rational"]
    assert all(reply.claims[0].startswith("（回应") for reply in replies)
    assert len(model.traces) == 2


def test_cross_response_skips_self_answer_and_repeat(cases, products):
    context = cross_context(cases, products)
    model = ScriptModel(
        [
            # 回应自己 → 丢弃
            {
                "role": "desire",
                "answers_role": "desire",
                "stance": "support",
                "claim": "我自己刚才说的还是对的",
                "evidence_ids": ["input:request"],
            },
            # 复读对方原话 → 丢弃
            {
                "role": "rational",
                "answers_role": "desire",
                "stance": "oppose",
                "claim": "纸巾宿舍确实快用完了，顺手买一包合理",
                "evidence_ids": ["input:request"],
            },
        ]
    )
    with pytest.raises(AgentError):
        cross_response.run(context, model)


def test_cross_response_requires_evidence(cases, products):
    context = cross_context(cases, products)
    model = ScriptModel(
        [
            {
                "role": "desire",
                "answers_role": "rational",
                "stance": "neutral",
                "claim": "你说的多买风险我承认",
                "evidence_ids": ["ghost:1"],
            },
            {
                "role": "rational",
                "answers_role": "desire",
                "stance": "oppose",
                "claim": "那就在清单里只保留纸巾这一项",
                "evidence_ids": ["input:profile"],
            },
        ]
    )
    replies = cross_response.run(context, model)
    assert [reply.role for reply in replies] == ["rational"]


@pytest.mark.parametrize(
    "ids",
    [
        ["ghost:1"],
        ["input:request", "ghost:1"],
        ["budget:initial"],
    ],
)
def test_cross_response_rejects_invisible_or_partially_forged_citations(cases, products, ids):
    context = cross_context(cases, products)
    model = ScriptModel(
        [
            {
                "role": "desire",
                "answers_role": "rational",
                "stance": "neutral",
                "claim": "应该先结合用户说的使用场景判断需求",
                "evidence_ids": ids,
            },
            {
                "role": "rational",
                "answers_role": "desire",
                "stance": "neutral",
                "claim": "最终付款仍需在生活费约束之内核对",
                "evidence_ids": ["input:profile"],
            },
        ]
    )
    replies = cross_response.run(context, model)
    assert [reply.role for reply in replies] == ["rational"]
