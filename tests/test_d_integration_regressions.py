"""D 集成回归：正式 B/C/D 模块与脚本模型共同运行，验证数据边界和最终决策。

从 budget-agent 仓库根目录运行：
uv run pytest tests/test_d_integration_regressions.py -v
只替换模型为脚本；预算、商品、优惠求解、D 节点、总控与 policy 均为正式实现。
不读取密钥，不调用学校模型，不使用 demo 模块。
"""

from copy import deepcopy

import pytest

from budget_agent.config import PROJECT_ROOT, AppConfig
from budget_agent.main import load_cases
from budget_agent.model_client import FakeModel
from budget_agent.workflow import build_services, run_case


def _run(
    case_id="tissue_buy",
    *,
    cross=False,
    forged_citation=False,
    wrong_price=False,
    forged_role=None,
    claims=None,
    judge_action=None,
):
    captured = []

    def respond(role, payload):
        captured.append((role, deepcopy(payload)))
        if role in {"desire", "rational", "deal"}:
            references = {
                "desire": "input:request",
                "rational": "budget:initial",
                "deal": "offer:chosen",
            }
            role_claims = {
                "desire": "用户明确说明了这次采购的使用需求",
                "rational": "是否购买仍需依据最终付款后的预算复核",
                "deal": "购物篮和付款明细以求解器计算结果为准",
            }
            return {
                "role": role,
                "stance": "neutral",
                "claims": [(claims or {}).get(role, role_claims[role])],
                "evidence_ids": [references[role]]
                + (["ghost:argument"] if role == forged_role else []),
                "unknowns": [],
            }
        if role == "cross_response":
            speaker = payload["speaking_as"]
            return {
                "role": speaker,
                "answers_role": "rational" if speaker == "desire" else "desire",
                "stance": "neutral",
                "claim": (
                    "用户确认的采购需求还需要结合实际使用场景讨论"
                    if speaker == "desire"
                    else "最终付款之后的生活费约束仍然需要保留"
                ),
                "evidence_ids": ["input:request" if speaker == "desire" else "budget:final"],
            }
        if role == "judge":
            action = (
                "need_info"
                if not payload["offer"]["verified"]
                else "buy"
                if payload["budget"]["within_budget"]
                else "wait"
            )
            return {
                "action": judge_action or action,
                "reason_summary": (
                    "优惠后到手价为300元，建议购买"
                    if wrong_price
                    else "需求明确，最终方案经过预算复核"
                ),
                "counterargument": "仍应确认实际使用需要",
                "evidence_ids": ["budget:final", "offer:chosen"]
                + (["promotion:does-not-exist"] if forged_citation else []),
                "next_steps": [],
            }
        raise AssertionError(f"Unexpected role: {role}")

    cases = {c.case_id: c for c in load_cases(PROJECT_ROOT / "data/cases/dev.jsonl")}
    config = AppConfig(mode="real", data_dir=PROJECT_ROOT / "data", cross_response_enabled=cross)
    services = build_services(config)
    services.model = FakeModel(respond)
    record = run_case(cases[case_id], config, services)
    assert record.errors == [], record.errors
    assert record.final_decision is not None
    return record, captured


def test_desire_cannot_read_budget_through_nested_fields():
    _, captured = _run()
    payload = next(p for role, p in captured if role == "desire")
    profile = payload.get("case", {}).get("profile", {})
    budget_fields = {
        "cash_cents",
        "days_remaining",
        "daily_essential_cents",
        "fixed_expenses_cents",
        "reserve_cents",
    }
    assert not budget_fields.intersection(profile), "case.profile 仍带有预算输入"
    assert all(e["kind"] != "budget" for e in payload.get("evidence", [])), (
        "evidence 仍带有预算工具结果"
    )
    for item in payload.get("evidence", []):
        if item["id"] == "input:profile":
            assert not budget_fields.intersection(item["facts"])


def test_invalid_judge_citation_is_recorded_and_blocks_buy():
    record, _ = _run(forged_citation=True)
    assert "promotion:does-not-exist" in record.proposed_decision.evidence_ids, (
        "原始裁判建议应保留原始引用，不能在记录前清洗"
    )
    assert record.final_decision.action == "need_info"
    assert any("不存在" in issue for issue in record.policy_violations)


def test_rational_cross_response_receives_actual_offer_and_evidence():
    _, captured = _run(cross=True)
    payload = next(
        p for role, p in captured if role == "cross_response" and p["speaking_as"] == "rational"
    )
    evidence = payload.get("evidence", [])
    assert evidence, "提示词要求从 evidence 列表引用事实，但输入没有该列表"
    by_id = {e["id"]: e for e in evidence}
    assert by_id["offer:chosen"]["facts"]["payable_cents"] == 25500
    assert payload["offer"]["payable_cents"] == 25500


def test_budget_amount_cannot_validate_wrong_checkout_price():
    record, _ = _run(wrong_price=True)
    assert record.final_decision.offer_result.payable_cents == 25500
    assert record.final_decision.budget_result.discretionary_cents == 30000
    assert record.final_decision.action == "need_info", (
        "到手价 300 元不能因为预算中恰好有 300 元就被认可；实际到手价为 255 元"
    )
    assert any("金额" in issue or "价格" in issue for issue in record.policy_violations)


@pytest.mark.parametrize("cross", [False, True])
@pytest.mark.parametrize(
    "case_id,action",
    [
        ("sneakers_wait", "wait"),
        ("tissue_buy", "buy"),
        ("exact_budget", "buy"),
        ("unknown_shipping", "need_info"),
        ("missing_profile", "need_info"),
    ],
)
def test_formal_workflow_preserves_budget_and_information_boundaries(case_id, action, cross):
    record, _ = _run(case_id, cross=cross)
    assert record.final_decision.action == action
    assert record.status == ("needs_input" if action == "need_info" else "completed")
    assert len(record.tool_calls) == (1 if case_id == "missing_profile" else 5)
    if record.final_decision.offer_result is not None:
        assert record.final_decision.offer_result.verification_method in {"solver", "unverified"}


def test_desire_cross_response_gets_visible_facts_without_budget_round_trip():
    record, captured = _run(
        cross=True,
        claims={
            "rational": "可支配预算300元，不应挪用生活费",
            "deal": "最终付款为255元，明细来自求解器",
        },
    )
    payload = next(
        p for role, p in captured if role == "cross_response" and p["speaking_as"] == "desire"
    )
    assert "budget" not in payload and "offer" not in payload
    assert payload["case"]["profile"] == {"owned_similar_items": []}
    assert "shipping_cents" not in payload["case"]["request"]
    assert {e["kind"] for e in payload["evidence"]} <= {"input", "product"}
    assert all("price_cents" not in product for product in payload["products"])
    assert {e["id"] for e in payload["evidence"]} >= {"input:request", "input:profile"}
    assert all(
        "300元" not in claim and "255元" not in claim
        for item in payload["their_claims"]
        for claim in item["claims"]
    )
    # 裁剪仅作用于发送视图，原始证据和用户输入仍完整保存供其他角色与回放使用。
    assert record.input.profile.cash_cents == 120000
    budget = next(e for e in record.evidence if e.id == "budget:initial")
    assert budget.facts["discretionary_cents"] == 30000
    assert record.final_decision.action == "buy"


@pytest.mark.parametrize("role", ["desire", "deal"])
def test_argument_forged_references_reach_policy_and_block_purchase(role):
    record, _ = _run(forged_role=role)
    argument = next(a for a in record.arguments if a.role == role)
    assert "ghost:argument" in argument.evidence_ids
    assert record.final_decision.action == "need_info"
    assert any(role in issue and "不存在" in issue for issue in record.policy_violations)


def test_formal_over_budget_buy_is_overridden_without_rewriting_proposal():
    record, _ = _run("sneakers_wait", judge_action="buy")
    assert record.proposed_decision.action == "buy"
    assert record.final_decision.action == "wait"
    assert record.final_decision.offer_result.payable_cents == 65000
    assert record.final_decision.budget_result.within_budget is False
