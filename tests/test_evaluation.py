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
                within: bool = True, missing: list[str] | None = None,
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
