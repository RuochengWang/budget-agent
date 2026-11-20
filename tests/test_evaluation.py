"""E 评测代码的单元验收：用合成的 RunRecord，不调用模型、不依赖 B/C/D。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from budget_agent.config import AppConfig
from budget_agent.schemas import (
    BudgetResult,
    CaseInput,
    Decision,
    DecisionProposal,
    Evidence,
    ModelTrace,
    OfferResult,
    RunRecord,
)
from evaluation.baselines import (
    BASELINES,
    available_baselines,
    baseline_plan,
    register_baseline,
    run_baseline,
    unregister_baseline,
)
from evaluation.metrics import compute_metrics, validate_labels
from evaluation.run import evaluate

NOW = datetime(2026, 11, 15, 8, 0, tzinfo=timezone.utc)


def make_case(case_id: str = "case_a") -> CaseInput:
    return CaseInput.model_validate({
        "case_id": case_id,
        "title": "测试案例",
        "profile": {"cash_cents": 100000, "days_remaining": 10,
                    "daily_essential_cents": 3000, "fixed_expenses_cents": 0,
                    "reserve_cents": 5000, "owned_similar_items": []},
        "request": {"target_product_id": "daily_goods", "need_reason": "补充日用品",
                    "urgency": "medium", "needed_addon_ids": [],
                    "shipping_cents": 0, "as_of": "2026-11-07T16:00:00+08:00"},
    })


def make_label(case_id: str = "case_a", *, payable: int | None = 28000,
               missing: list[str] | None = None, reviewed: bool = True) -> dict:
    return {
        "case_id": case_id,
        "review_status": "reviewed" if reviewed else "draft",
        "reviewers": ["A", "C"] if reviewed else [],
        "reviewed_at": "2026-11-15" if reviewed else None,
        "budget": {
            "essential_total_cents": 30000,
            "discretionary_cents": 65000,
            "remaining_cents": None,
            "remaining_cash_cents": 72000,
            "within_budget": True,
            "missing_fields": missing or [],
        },
        "offer": None if payable is None else {
            "feasible": True,
            "optimal_payable_cents": payable,
            "optimal_basket_ids": ["daily_goods"],
            "optimal_rule_ids": [],
            "baseline_payable_cents": payable,
        },
        "reference_action": "buy",
        "notes": "人工复算",
    }


def make_record(case: CaseInput, *, action: str = "buy", payable: int | None = 28000,
                within: bool | None = True, missing: list[str] | None = None,
                mode: str = "real", status: str = "completed",
                evidence_ids: list[str] | None = None, usage: dict | None = None) -> RunRecord:
    budget = BudgetResult(
        essential_total_cents=30000,
        discretionary_cents=65000,
        remaining_cash_cents=72000,
        within_budget=within,
        missing_fields=missing or [],
    )
    offer = None
    if payable is not None:
        offer = OfferResult(
            basket_ids=["daily_goods"], subtotal_cents=28000, discount_cents=0,
            shipping_cents=0, payable_cents=payable, baseline_payable_cents=payable,
            rule_ids=[], verified=True, verification_method="solver", is_demo=False,
        )
    ids = evidence_ids if evidence_ids is not None else ["input:profile", "budget:final"]
    decision = Decision(
        action=action, reason_summary="测试", counterargument="", evidence_ids=ids,
        next_steps=[], budget_result=budget, offer_result=offer,
    )
    return RunRecord(
        run_id="a" * 32, contract_version="0.1", code_version="0.1.0",
        mode=mode, status=status, started_at=NOW,
        finished_at=NOW + timedelta(seconds=2),
        input=case, config_snapshot={}, prompt_hashes={}, model="qwen3.8-chat",
        evidence=[Evidence(id=eid, kind="input", description="证据", is_demo=False)
                  for eid in set(ids) | {"input:profile", "budget:final", "offer:chosen"}],
        proposed_decision=DecisionProposal(
            action=action, reason_summary="测试", evidence_ids=ids, next_steps=[]
        ),
        final_decision=decision,
        model_calls=[ModelTrace(role="judge", model="qwen3.8-chat", elapsed_ms=100,
                                usage=usage or {"total_tokens": 100})],
    )


def test_validate_labels_accepts_complete_reviewed_label():
    label = make_label()
    label["budget"].pop("remaining_cents")
    assert validate_labels([label], require_reviewed=True) == []


def test_validate_labels_flags_draft_missing_reviewers_and_fields():
    label = make_label(reviewed=False)
    label["budget"].pop("remaining_cash_cents")
    problems = validate_labels([label], require_reviewed=True)
    assert any("尚未复核" in p for p in problems)
    assert any("缺少复核人" in p for p in problems)
    assert any("budget.remaining_cash_cents 缺失" in p for p in problems)


@pytest.mark.parametrize("reviewers", [["A"], ["A", "A"], ["A", "X"], "AC"])
def test_validate_labels_requires_distinct_reviewers(reviewers):
    label = make_label()
    label["reviewers"] = reviewers
    assert any("复核人" in p for p in validate_labels([label]))


def test_validate_labels_requires_valid_review_date():
    label = make_label()
    label["reviewed_at"] = "2026-02-30"
    assert any("复核日期" in p for p in validate_labels([label]))


def test_validate_labels_detects_duplicates():
    label = make_label()
    label["budget"].pop("remaining_cents")
    assert any("重复标签" in p for p in validate_labels([label, dict(label)]))


def test_metrics_all_correct_with_denominators():
    case = make_case()
    label = make_label()
    label["budget"].pop("remaining_cents")
    record = make_record(case)
    result = compute_metrics([record], [label])
    assert result["total_cases"] == 1
    assert result["not_run"] == []
    assert result["unmatched_records"] == []
    for key in ("budget_correct", "offer_optimal_amount", "offer_basket",
                "offer_feasible", "evidence_valid"):
        metric = result["metrics"][key]
        assert metric["correct"] == 1 and metric["valid"] == 1
        assert metric["total"] == 1 and metric["rate"] == 1.0
    assert result["metrics"]["missing_info_detection"]["total"] == 0
    assert result["metrics"]["constraint_violations"]["count"] == 0
    assert result["usage"]["tokens"]["total_tokens"] == 100
    assert result["usage"]["fee"] is None


def test_metrics_not_run_counts_in_denominator_but_never_correct():
    label = make_label()
    label["budget"].pop("remaining_cents")
    result = compute_metrics([], [label])
    assert result["not_run"] == ["case_a"]
    metric = result["metrics"]["budget_correct"]
    assert metric["total"] == 1 and metric["valid"] == 0 and metric["correct"] == 0
    assert metric["rate"] is None and metric["not_run"] == 1


@pytest.mark.parametrize("has_incomplete_record", [False, True])
def test_metrics_partial_coverage_uses_all_applicable_labels(has_incomplete_record):
    records = [make_record(make_case("a"))]
    if has_incomplete_record:
        incomplete = make_record(make_case("b"), status="partial")
        incomplete.final_decision = None
        records.append(incomplete)
    result = compute_metrics(records, [make_label("a"), make_label("b")])
    for key in ("budget_correct", "offer_optimal_amount", "offer_basket",
                "offer_feasible", "evidence_valid"):
        assert result["metrics"][key] == {
            "correct": 1, "valid": 1, "total": 2, "not_run": 1, "rate": 0.5,
        }


def test_metrics_unmatched_record_is_not_scored():
    label = make_label("case_a")
    label["budget"].pop("remaining_cents")
    record = make_record(make_case("case_b"))
    result = compute_metrics([record], [label])
    assert result["unmatched_records"] == ["case_b"]
    assert result["metrics"]["budget_correct"]["valid"] == 0


def test_metrics_detect_wrong_amount_and_constraint_violation():
    label = make_label(payable=28000)
    label["budget"].pop("remaining_cents")
    record = make_record(make_case(), payable=29000, within=False)
    result = compute_metrics([record], [label])
    assert result["metrics"]["offer_optimal_amount"]["correct"] == 0
    assert result["metrics"]["constraint_violations"]["count"] >= 1


@pytest.mark.parametrize("within", [None, False])
def test_buy_requires_an_explicit_budget_pass(within):
    record = make_record(make_case(), within=within)
    metric = compute_metrics([record], [make_label()])["metrics"]["constraint_violations"]
    assert any("预算未明确通过" in item for item in metric["cases"])


@pytest.mark.parametrize("update", [
    {"verified": False}, {"verification_method": "unverified"},
    {"verification_method": "demo_fixture"}, {"unknowns": ["活动条件未知"]},
    {"subtotal_cents": None}, {"discount_cents": None},
    {"shipping_cents": None}, {"payable_cents": None},
])
def test_buy_requires_a_confirmed_offer_and_payment(update):
    record = make_record(make_case())
    decision = record.final_decision
    decision.offer_result = decision.offer_result.model_copy(update=update)
    metric = compute_metrics([record], [make_label()])["metrics"]["constraint_violations"]
    assert any("方案或付款明细尚未确认" in item for item in metric["cases"])


def test_buy_cannot_assume_a_missing_offer_or_unknown_input_shipping():
    for missing_offer in (True, False):
        record = make_record(make_case())
        if missing_offer:
            record.final_decision.offer_result = None
        else:
            record.input.request.shipping_cents = None
        metric = compute_metrics([record], [make_label()])["metrics"]["constraint_violations"]
        assert any("方案或付款明细尚未确认" in item for item in metric["cases"])


@pytest.mark.parametrize("action", ["wait", "skip", "need_info"])
def test_non_buy_does_not_require_a_confirmed_purchase(action):
    record = make_record(make_case(), action=action, payable=None, within=None)
    metric = compute_metrics([record], [make_label()])["metrics"]["constraint_violations"]
    assert metric["count"] == 0


def test_solver_on_sample_catalog_is_distinct_from_demo_execution():
    record = make_record(make_case())
    record.final_decision.offer_result.is_demo = True  # 样例商品，不是演示替身。
    metric = compute_metrics([record], [make_label()])["metrics"]["constraint_violations"]
    assert metric["count"] == 0


def test_metrics_missing_info_detection():
    label = make_label(payable=None, missing=["reserve_cents"])
    label["budget"]["within_budget"] = None
    label["budget"]["discretionary_cents"] = None
    label["budget"]["remaining_cash_cents"] = None
    label["budget"]["essential_total_cents"] = None
    record = make_record(make_case(), action="need_info", payable=None,
                         within=None, missing=["reserve_cents"])
    result = compute_metrics([record], [label])
    metric = result["metrics"]["missing_info_detection"]
    assert metric["total"] == 1 and metric["valid"] == 1 and metric["correct"] == 1


def test_metrics_usage_missing_fields_stay_none():
    result = compute_metrics([make_record(make_case(), usage={"prompt_tokens": None})], [])
    assert result["usage"]["tokens"]["total_tokens"] is None
    assert "total_tokens" in result["usage"]["missing_usage_fields"]


def test_partial_usage_is_not_reported_as_a_complete_total():
    record = make_record(make_case())
    record.model_calls = [
        ModelTrace(role="judge", model="test", elapsed_ms=0,
                   usage={"prompt_tokens": 80, "completion_tokens": 20, "total_tokens": 100}),
        ModelTrace(role="judge", model="test", elapsed_ms=0,
                   usage={"prompt_tokens": 10}),
    ]
    usage = compute_metrics([record], [make_label()])["usage"]
    assert usage["tokens"] == {
        "prompt_tokens": 90, "completion_tokens": None, "total_tokens": None,
    }
    assert usage["missing_usage_fields"] == ["completion_tokens", "total_tokens"]


def test_usage_missing_in_another_record_also_invalidates_the_total():
    first, second = make_record(make_case("a")), make_record(make_case("b"))
    second.model_calls[0].usage = {}
    usage = compute_metrics([first, second], [])["usage"]
    assert usage["model_calls"] == 2
    assert usage["tokens"]["total_tokens"] is None


def test_zero_usage_is_a_known_value_and_can_be_summed():
    record = make_record(make_case())
    record.model_calls[0].usage = {
        "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
    }
    usage = compute_metrics([record], [])["usage"]
    assert usage["tokens"] == {
        "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
    }
    assert usage["missing_usage_fields"] == []


def test_baseline_plan_and_available_registry():
    assert set(BASELINES) == {"B0", "B1", "B2", "M", "M_no_cross"}
    assert baseline_plan("B0")["uses_model"] is False
    assert baseline_plan("M_no_cross")["cross_response"] == "forced_off"
    assert "M" in available_baselines()
    assert "B0" not in available_baselines()


def test_unregistered_baseline_raises_module_not_ready():
    from budget_agent.errors import ModuleNotReady
    with pytest.raises(ModuleNotReady, match="B0"):
        run_baseline("B0", make_case(), config=AppConfig(mode="real"))


def test_registered_baseline_is_invoked_with_shared_config(tmp_path):
    seen = {}

    def fake(case: CaseInput, config: AppConfig) -> RunRecord:
        seen["case"] = case.case_id
        seen["mode"] = config.mode
        return make_record(case)

    register_baseline("B1", fake)
    try:
        config = AppConfig(mode="real", output_dir=tmp_path)
        record = run_baseline("B1", make_case(), config=config)
        assert seen == {"case": "case_a", "mode": "real"}
        assert record.mode == "real"
    finally:
        unregister_baseline("B1")


def test_duplicate_registration_is_refused():
    def fake(case, config):
        return make_record(case)

    register_baseline("B2", fake)
    try:
        with pytest.raises(ValueError, match="已注册"):
            register_baseline("B2", fake)
    finally:
        unregister_baseline("B2")


def test_evaluate_rejects_demo_mode_before_running(tmp_path):
    cases = tmp_path / "cases.jsonl"
    labels = tmp_path / "labels.jsonl"
    cases.write_text(json.dumps(make_case().model_dump(mode="json")) + "\n", encoding="utf-8")
    label = make_label()
    label["budget"].pop("remaining_cents")
    labels.write_text(json.dumps(label) + "\n", encoding="utf-8")
    records, summary, problems = evaluate(
        baseline="M", cases_path=cases, labels_path=labels,
        config=AppConfig(mode="demo", output_dir=tmp_path), strict_labels=False,
    )
    assert records == [] and summary == {}
    assert any("real" in p for p in problems)


def test_evaluate_rejects_unreviewed_labels_by_default(tmp_path):
    cases = tmp_path / "cases.jsonl"
    labels = tmp_path / "labels.jsonl"
    cases.write_text(json.dumps(make_case().model_dump(mode="json")) + "\n", encoding="utf-8")
    label = make_label(reviewed=False)
    label["budget"].pop("remaining_cents")
    labels.write_text(json.dumps(label) + "\n", encoding="utf-8")
    _, _, problems = evaluate(
        baseline="M", cases_path=cases, labels_path=labels,
        config=AppConfig(mode="real", output_dir=tmp_path), strict_labels=True,
    )
    assert any("尚未复核" in p for p in problems)


def make_unconfirmed_label(case_id: str = "case_u") -> dict:
    """运费未知的标签：方案未确认，购物篮留空。"""
    label = make_label(case_id, payable=None)
    label["offer"] = {
        "feasible": None,
        "optimal_payable_cents": None,
        "optimal_basket_ids": [],
        "optimal_rule_ids": [],
        "baseline_payable_cents": None,
        "shipping_cents": None,
        "unknowns": ["运费未知"],
    }
    label["budget"]["remaining_cash_cents"] = None
    label["budget"]["within_budget"] = None
    label["budget"]["missing_fields"] = []
    label["reference_action"] = "need_info"
    return label


def make_unconfirmed_record(case_id: str = "case_u", *,
                            placeholder_basket: tuple[str, ...] = ("daily_goods",)) -> RunRecord:
    """模拟求解器在运费未知时的保守输出：basket 占位、payable 为 None。"""
    record = make_record(make_case(case_id), action="need_info", payable=None, within=None)
    record.input.request.shipping_cents = None
    record.final_decision.offer_result = OfferResult(
        basket_ids=list(placeholder_basket),
        verified=False,
        verification_method="unverified",
        is_demo=False,
        unknowns=["运费未知，无法确认到手价"],
    )
    return record


def test_unconfirmed_plan_does_not_grade_the_placeholder_basket():
    label = make_unconfirmed_label()
    record = make_unconfirmed_record()
    result = compute_metrics([record], [label])
    assert result["metrics"]["offer_optimal_amount"]["correct"] == 1
    assert result["metrics"]["offer_basket"]["correct"] == 1
    assert result["metrics"]["offer_feasible"]["correct"] == 1
    assert result["metrics"]["constraint_violations"]["count"] == 0


def test_unconfirmed_plan_labels_do_not_hide_a_confirmed_offer():
    label = make_unconfirmed_label()
    record = make_unconfirmed_record()
    record.final_decision.offer_result = OfferResult(
        basket_ids=["daily_goods"], subtotal_cents=28000, discount_cents=0,
        shipping_cents=0, payable_cents=28000, baseline_payable_cents=28000,
        rule_ids=[], verified=True, verification_method="solver", is_demo=False,
    )
    result = compute_metrics([record], [label])
    assert result["metrics"]["offer_optimal_amount"]["correct"] == 0
    assert result["metrics"]["offer_basket"]["correct"] == 0


def test_labels_match_independent_recomputation():
    from evaluation.verify_labels import collect

    report = collect()
    assert report["total"] == 40
    assert report["missing_labels"] == []
    assert report["consistent"], report["mismatched"]


def test_unknown_shipping_labels_do_not_claim_an_optimal_basket():
    from evaluation.verify_labels import CASES_DIR, _load_jsonl

    labels = {label["case_id"]: label for label in _load_jsonl(CASES_DIR / "labels.jsonl")}
    for case_id in ("unknown_shipping", "t_shipping_unknown_single", "t_shipping_unknown_basket"):
        offer = labels[case_id]["offer"]
        assert offer["optimal_payable_cents"] is None
        assert offer["optimal_basket_ids"] == []
        assert offer["optimal_rule_ids"] == []
        assert offer["unknowns"] == ["运费未知"]
