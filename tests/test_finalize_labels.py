"""标签收尾工具验收：只改状态，不改数值，dry-run 默认不写文件。"""

from __future__ import annotations

import json
from pathlib import Path

from budget_agent.config import PROJECT_ROOT
from budget_agent.main import load_cases
from evaluation.finalize_labels import finalize, main, validate


def _row(cid="case_a"):
    return {
        "case_id": cid, "review_status": "draft", "reviewers": [], "reviewed_at": None,
        "budget": {"essential_total_cents": 1, "discretionary_cents": 2,
                   "remaining_cash_cents": 3, "within_budget": True, "missing_fields": []},
        "offer": {"feasible": True, "optimal_payable_cents": 4,
                  "optimal_basket_ids": [], "optimal_rule_ids": [],
                  "baseline_payable_cents": 4},
        "reference_action": "buy", "notes": "人工复算",
    }


def test_validate_accepts_well_formed_row():
    assert validate([_row()]) == []


def test_validate_flags_duplicates_and_bad_fields():
    bad = _row()
    bad["budget"].pop("within_budget")
    problems = validate([_row(), _row(), bad])
    assert any("重复" in p for p in problems)
    assert any("budget" in p for p in problems)


def test_finalize_only_changes_review_metadata():
    row = _row()
    before = json.dumps({k: v for k, v in row.items() if not k.startswith("review") and k != "frozen_commit"}, sort_keys=True)
    out = finalize([row], ["A", "C"], "2026-11-17", "abc123")[0]
    after = json.dumps({k: v for k, v in out.items() if not k.startswith("review") and k != "frozen_commit"}, sort_keys=True)
    assert before == after
    assert out["review_status"] == "reviewed"
    assert out["reviewers"] == ["A", "C"] and out["reviewed_at"] == "2026-11-17"
    assert out["frozen_commit"] == "abc123"


def test_main_dry_run_does_not_write(tmp_path: Path):
    path = tmp_path / "labels.jsonl"
    original = json.dumps(_row(), ensure_ascii=False) + "\n"
    path.write_text(original, encoding="utf-8")
    code = main(["--labels", str(path), "--reviewers", "A", "C", "--date", "2026-11-17"])
    assert code == 0
    assert path.read_text(encoding="utf-8") == original


def test_main_apply_writes_reviewed_status(tmp_path: Path):
    path = tmp_path / "labels.jsonl"
    path.write_text(json.dumps(_row(), ensure_ascii=False) + "\n", encoding="utf-8")
    code = main(["--labels", str(path), "--reviewers", "A", "C", "--date", "2026-11-17", "--apply"])
    assert code == 0
    row = json.loads(path.read_text(encoding="utf-8"))
    assert row["review_status"] == "reviewed" and row["reviewers"] == ["A", "C"]
    assert row["budget"]["essential_total_cents"] == 1  # 数值未变


def test_main_rejects_single_reviewer_and_bad_date(tmp_path: Path):
    path = tmp_path / "labels.jsonl"
    path.write_text(json.dumps(_row(), ensure_ascii=False) + "\n", encoding="utf-8")
    assert main(["--labels", str(path), "--reviewers", "A", "--date", "2026-11-17"]) == 2
    assert main(["--labels", str(path), "--reviewers", "A", "C", "--date", "bad"]) == 2


def test_main_updates_only_selected_cases_and_rejects_duplicate_signers(tmp_path):
    labels = tmp_path / "labels.jsonl"
    cases_path = tmp_path / "test.jsonl"
    case = load_cases(PROJECT_ROOT / "data/cases/test.jsonl")[0]
    rows = [_row(case.case_id), _row("dev_smoke")]
    original = "".join(json.dumps(row) + "\n" for row in rows)
    labels.write_text(original, encoding="utf-8")
    cases_path.write_text(case.model_dump_json() + "\n", encoding="utf-8")
    base = ["--labels", str(labels), "--cases", str(cases_path), "--date", "2026-11-18", "--apply"]
    assert main([*base, "--reviewers", "A", "A"]) == 2
    assert labels.read_text(encoding="utf-8") == original
    assert main([*base, "--reviewers", "A", "C"]) == 0
    first, untouched = [json.loads(line) for line in labels.read_text(encoding="utf-8").splitlines()]
    assert first["review_status"] == "reviewed" and first["budget"] == rows[0]["budget"]
    assert untouched == rows[1]


def test_real_labels_file_passes_structure_check():
    rows = [json.loads(line) for line in (PROJECT_ROOT / "data/cases/labels.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert validate(rows) == []
    assert len(rows) == 40