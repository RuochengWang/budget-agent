"""E 的案例与标签验收：开发案例可加载、覆盖关键情形、标签草案可追溯。"""

import json
from datetime import datetime

from budget_agent.config import PROJECT_ROOT
from budget_agent.main import load_cases
from evaluation.metrics import validate_labels

CASES_DIR = PROJECT_ROOT / "data" / "cases"
REQUIRED_CASES = {
    "sneakers_wait",
    "tissue_buy",
    "missing_profile",
    "unknown_shipping",
    "exact_budget",
    "sneakers_owned_similar",
    "addon_not_worth_it",
    "promo_expired",
    "shipping_known",
    "missing_essential",
}


def _read_labels():
    return [
        json.loads(line)
        for line in (CASES_DIR / "labels.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_dev_cases_load_and_are_unique():
    cases = load_cases(CASES_DIR / "dev.jsonl")
    assert len(cases) >= 10
    assert len({case.case_id for case in cases}) == len(cases)


def test_dev_cases_cover_required_scenarios():
    cases = {case.case_id: case for case in load_cases(CASES_DIR / "dev.jsonl")}
    assert REQUIRED_CASES <= cases.keys()
    assert cases["sneakers_wait"].profile.owned_similar_items
    assert cases["addon_not_worth_it"].request.needed_addon_ids
    assert cases["promo_expired"].request.as_of.month == 12
    assert cases["shipping_known"].request.shipping_cents == 1200
    assert cases["missing_essential"].profile.daily_essential_cents is None
    assert cases["unknown_shipping"].request.shipping_cents is None


def test_cases_load_and_are_distinct_from_dev():
    test = load_cases(CASES_DIR / "test.jsonl")
    dev = load_cases(CASES_DIR / "dev.jsonl")
    assert len(test) == 30
    assert len({case.case_id for case in test}) == len(test)
    assert not ({case.case_id for case in test} & {case.case_id for case in dev})


def test_cases_cover_key_boundaries():
    cases = {case.case_id: case for case in load_cases(CASES_DIR / "test.jsonl")}
    start = datetime.fromisoformat("2026-11-01T00:00:00+08:00")
    end = datetime.fromisoformat("2026-12-01T00:00:00+08:00")
    assert cases["t_exact_budget_sneakers"].request.as_of == start  # 左闭
    assert cases["t_promo_expired_boundary"].request.as_of == end  # 右开
    assert cases["t_promo_not_started_boundary"].request.as_of < start
    missing = {
        field: sum(
            1 for case in cases.values() if getattr(case.profile, field) is None
        )
        for field in ("cash_cents", "days_remaining", "daily_essential_cents",
                      "fixed_expenses_cents", "reserve_cents")
    }
    assert all(count == 1 for count in missing.values())
    assert sum(1 for c in cases.values() if c.request.shipping_cents is None) == 2
    assert sum(1 for c in cases.values() if c.request.shipping_cents == 0) == 25
    assert sum(1 for c in cases.values()
               if isinstance(c.request.shipping_cents, int)
               and c.request.shipping_cents > 0) == 3
    assert cases["t_zero_days"].profile.days_remaining == 0
    assert cases["t_zero_reserve"].profile.reserve_cents == 0


def test_labels_are_traceable_and_not_model_input():
    labels = _read_labels()
    dev = load_cases(CASES_DIR / "dev.jsonl")
    test = load_cases(CASES_DIR / "test.jsonl")
    all_ids = {case.case_id for case in [*dev, *test]}
    ids = [label["case_id"] for label in labels]
    assert len(ids) == len(set(ids)) == len(dev) + len(test) == 40
    assert set(ids) == all_ids
    assert all(label["review_status"] in {"draft", "reviewed"} for label in labels)
    assert all(isinstance(label["reviewers"], list) for label in labels)
    for label in labels:
        assert set(label["budget"]) == {
            "essential_total_cents",
            "discretionary_cents",
            "remaining_cash_cents",
            "within_budget",
            "missing_fields",
        }
        assert label["offer"] is None or set(label["offer"]) >= {
            "feasible",
            "optimal_payable_cents",
            "optimal_basket_ids",
            "optimal_rule_ids",
            "baseline_payable_cents",
        }


def test_labels_are_well_formed_and_review_metadata_matches_status():
    labels = _read_labels()
    problems = validate_labels(labels, require_reviewed=False)
    assert problems == [], problems
    reviewed = [label for label in labels if label["review_status"] == "reviewed"]
    problems = validate_labels(reviewed, require_reviewed=True)
    assert problems == [], problems
    for label in labels:
        if label["review_status"] == "draft":
            assert label["reviewers"] == [] and label["reviewed_at"] is None


def test_review_sheet_covers_all_test_cases():
    sheet = (CASES_DIR / "review_sheet.md").read_text(encoding="utf-8")
    test = load_cases(CASES_DIR / "test.jsonl")
    for case in test:
        assert f"| {case.case_id} |" in sheet


def test_essential_labels_depend_only_on_days_daily_and_fixed_expenses():
    # 独立按输入公式检查；不使用被评估的 B/C 实现给标签生成标准答案。
    cases = {
        case.case_id: case
        for name in ("dev.jsonl", "test.jsonl")
        for case in load_cases(CASES_DIR / name)
    }
    for label in _read_labels():
        profile = cases[label["case_id"]].profile
        days, daily, fixed = (
            profile.days_remaining, profile.daily_essential_cents, profile.fixed_expenses_cents,
        )
        expected = days * daily + fixed if all(v is not None for v in (days, daily, fixed)) else None
        assert label["budget"]["essential_total_cents"] == expected, label["case_id"]
