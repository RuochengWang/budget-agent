"""E：标签独立复算（不使用 C 的求解器与 catalog/promotions 模块）。

用途：给 40 条独立标签做一遍独立实现的复算，作为人工复核前的自检或替代记录。
只读 data/catalog 快照与 docs/common/contracts.md 的公式；不写标签、不调用模型。

约定（与 data/cases/review_sheet.md 一致）：
- 缺预算字段：只算依赖齐全字段的结果，其余为 None，期望 need_info；
- 运费未知：方案未确认，optimal_basket_ids / optimal_rule_ids 留空，应付额为 None，期望 need_info。

运行：
    python -m evaluation.verify_labels            # 人读报告
    python -m evaluation.verify_labels --json     # 机器可读
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from itertools import combinations
from pathlib import Path

from budget_agent.config import PROJECT_ROOT

CASES_DIR = PROJECT_ROOT / "data" / "cases"
CATALOG_DIR = PROJECT_ROOT / "data" / "catalog"
BUDGET_FIELDS = (
    "cash_cents",
    "days_remaining",
    "daily_essential_cents",
    "fixed_expenses_cents",
    "reserve_cents",
)


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def _valid_rules(promotions: list[dict], as_of: datetime) -> list[dict]:
    return [
        rule
        for rule in promotions
        if _parse(rule["valid_from"]) <= as_of < _parse(rule["valid_to"])
    ]


def _best_for_basket(items: list[str], products: dict[str, dict], rules: list[dict], shipping: int | None) -> dict:
    subtotal = sum(products[i]["price_cents"] for i in items)
    best = None
    for rule in [None, *rules]:
        discount = 0
        rule_ids: list[str] = []
        if rule is not None:
            eligible_sum = sum(
                products[i]["price_cents"] for i in items if i in rule["eligible_product_ids"]
            )
            if eligible_sum == 0 or eligible_sum < rule["threshold_cents"]:
                continue
            discount = min(rule["discount_cents"], eligible_sum)
            rule_ids = [rule["id"]]
        payable = None if shipping is None else subtotal - discount + shipping
        key = (
            0 if payable is not None else 1,
            payable if payable is not None else subtotal - discount,
            len(items),
            sorted(items),
            sorted(rule_ids),
        )
        candidate = {
            "basket": sorted(items),
            "rules": sorted(rule_ids),
            "subtotal": subtotal,
            "discount": discount,
            "payable": payable,
            "key": key,
        }
        if best is None or candidate["key"] < best["key"]:
            best = candidate
    return best


def _best_offer(target: str, addons: list[str], rules: list[dict], shipping: int | None) -> tuple[dict, dict]:
    products = _PRODUCTS
    best = None
    for size in range(len(addons) + 1):
        for extra in combinations(addons, size):
            offer = _best_for_basket([target, *extra], products, rules, shipping)
            if best is None or offer["key"] < best["key"]:
                best = offer
    baseline = _best_for_basket([target], products, rules, shipping)
    return best, baseline


_PRODUCTS: dict[str, dict] = {}
_PROMOTIONS: list[dict] = []


def _load_snapshots() -> None:
    global _PRODUCTS, _PROMOTIONS
    _PRODUCTS = {p["id"]: p for p in json.loads((CATALOG_DIR / "products.json").read_text(encoding="utf-8"))}
    _PROMOTIONS = json.loads((CATALOG_DIR / "promotions.json").read_text(encoding="utf-8"))


def verify_case(case: dict) -> tuple[dict, dict | None, str]:
    """返回 (budget, offer, expected_action)。"""
    profile, request = case["profile"], case["request"]
    missing = [field for field in BUDGET_FIELDS if profile.get(field) is None]

    essential = None
    if not {"days_remaining", "daily_essential_cents", "fixed_expenses_cents"} & set(missing):
        essential = (
            profile["days_remaining"] * profile["daily_essential_cents"]
            + profile["fixed_expenses_cents"]
        )
    discretionary = None
    if essential is not None and not {"cash_cents", "reserve_cents"} & set(missing):
        discretionary = profile["cash_cents"] - essential - profile["reserve_cents"]

    budget = {
        "essential_total_cents": essential,
        "discretionary_cents": discretionary,
        "remaining_cash_cents": None,
        "within_budget": None,
        "missing_fields": missing,
    }
    if missing:
        return budget, None, "need_info"

    as_of = _parse(request["as_of"])
    shipping = request.get("shipping_cents")
    best, baseline = _best_offer(
        request["target_product_id"], request.get("needed_addon_ids") or [],
        _valid_rules(_PROMOTIONS, as_of), shipping,
    )

    if shipping is None:
        offer = {
            "feasible": None,
            "optimal_payable_cents": None,
            # 方案未确认：不声称最优购物篮，也不拿它评分。
            "optimal_basket_ids": [],
            "optimal_rule_ids": [],
            "baseline_payable_cents": None,
            "shipping_cents": None,
            "unknowns": ["运费未知"],
        }
        return budget, offer, "need_info"

    offer = {
        "feasible": True,
        "optimal_payable_cents": best["payable"],
        "optimal_basket_ids": best["basket"],
        "optimal_rule_ids": best["rules"],
        "baseline_payable_cents": baseline["payable"],
        "shipping_cents": shipping,
    }
    budget["remaining_cash_cents"] = profile["cash_cents"] - best["payable"]
    budget["within_budget"] = (
        budget["remaining_cash_cents"] >= essential + profile["reserve_cents"]
    )
    return budget, offer, "buy" if budget["within_budget"] else "wait"


def _diff(label: dict, budget: dict, offer: dict | None, action: str) -> list[dict]:
    found: list[dict] = []
    label_budget = label.get("budget") or {}
    for key, got in budget.items():
        want = label_budget.get(key)
        if want != got:
            found.append({"field": f"budget.{key}", "label": want, "recomputed": got})
    label_offer = label.get("offer")
    if (label_offer is None) != (offer is None):
        found.append({"field": "offer", "label": label_offer, "recomputed": offer})
    elif label_offer is not None:
        for key, got in offer.items():
            want = label_offer.get(key)
            if want != got:
                found.append({"field": f"offer.{key}", "label": want, "recomputed": got})
    if label.get("reference_action") != action:
        found.append({
            "field": "reference_action",
            "label": label.get("reference_action"),
            "recomputed": action,
        })
    return found


def collect() -> dict:
    _load_snapshots()
    labels = {d["case_id"]: d for d in _load_jsonl(CASES_DIR / "labels.jsonl")}
    report = {"total": 0, "matched": 0, "mismatched": [], "missing_labels": []}
    for name in ("dev.jsonl", "test.jsonl"):
        for case in _load_jsonl(CASES_DIR / name):
            case_id = case["case_id"]
            label = labels.get(case_id)
            report["total"] += 1
            if label is None:
                report["missing_labels"].append(case_id)
                continue
            budget, offer, action = verify_case(case)
            diffs = _diff(label, budget, offer, action)
            if diffs:
                report["mismatched"].append({"case_id": case_id, "diffs": diffs})
            else:
                report["matched"] += 1
    report["consistent"] = not report["mismatched"] and not report["missing_labels"]
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="独立复算 40 条标签（不调用求解器、不调用模型）")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    args = parser.parse_args(argv)
    report = collect()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"共 {report['total']} 例，一致 {report['matched']} 例")
        if report["missing_labels"]:
            print("缺少标签:", ", ".join(report["missing_labels"]))
        for item in report["mismatched"]:
            print("=" * 60)
            print(item["case_id"])
            for diff in item["diffs"]:
                print(f"  {diff['field']}: 标签={diff['label']!r} 复算={diff['recomputed']!r}")
    return 0 if report["consistent"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
