"""E：复核人签字后的标签收尾工具（只改复核状态，绝不改任何数值/答案）。

用法：
    .venv/bin/python -m evaluation.finalize_labels \
        --cases data/cases/test.jsonl --reviewers A C --date YYYY-MM-DD

设计目的：
- 你/复核人先用 review_sheet.md 独立把数值算完、必要时直接改 labels.jsonl 的数值；
- 这个脚本只做机械收尾：检查字段完整、ID 唯一、reviewers 至少两人、日期合法，
  然后仅更新选定案例的 review_status、复核人与日期，可选记录冻结 commit。
- 它**不重新计算任何金额、不生成答案、不调用模型、不碰 dev/test 案例文件**。
- 默认 dry-run 只检查；加 --apply 才写回 labels.jsonl。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from budget_agent.config import PROJECT_ROOT
from budget_agent.main import load_cases
from evaluation.metrics import valid_review_date, valid_reviewers

LABELS = PROJECT_ROOT / "data" / "cases" / "labels.jsonl"

BUDGET_KEYS = {
    "essential_total_cents", "discretionary_cents", "remaining_cash_cents",
    "within_budget", "missing_fields",
}
OFFER_KEYS = {
    "feasible", "optimal_payable_cents", "optimal_basket_ids",
    "optimal_rule_ids", "baseline_payable_cents",
}


def _read(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def validate(rows: list[dict]) -> list[str]:
    problems: list[str] = []
    if any(not isinstance(row, dict) for row in rows):
        return ["标签每行必须是 JSON 对象"]
    ids = [row.get("case_id") for row in rows]
    if any(not isinstance(cid, str) or not cid for cid in ids):
        problems.append("标签 case_id 缺失或不是非空字符串")
    duplicates = sorted({x for x in ids if isinstance(x, str) and ids.count(x) > 1})
    if duplicates:
        problems.append(f"重复 case_id：{duplicates}")
    for row in rows:
        cid = row.get("case_id", "?")
        budget = row.get("budget")
        if not isinstance(budget, dict) or set(budget) != BUDGET_KEYS:
            problems.append(f"{cid}: budget 字段不完整或多余")
        offer = row.get("offer")
        if offer is not None and not (isinstance(offer, dict) and OFFER_KEYS <= set(offer)):
            problems.append(f"{cid}: offer 字段不完整")
        if row.get("review_status") not in {"draft", "reviewed"}:
            problems.append(f"{cid}: review_status 非法")
    return problems


def finalize(rows: list[dict], reviewers: list[str], day: str, commit: str | None) -> list[dict]:
    result: list[dict] = []
    for row in rows:
        new = dict(row)
        new["review_status"] = "reviewed"
        new["reviewers"] = reviewers
        new["reviewed_at"] = day
        if commit:
            new["frozen_commit"] = commit
        result.append(new)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="E：标签复核收尾（只改状态）")
    parser.add_argument("--labels", type=Path, default=LABELS)
    parser.add_argument("--cases", type=Path, help="仅更新所选案例；省略则处理标签文件全部行")
    parser.add_argument("--reviewers", nargs="+", required=True, help="至少两位复核人 A—E 标识")
    parser.add_argument("--date", required=True, help="复核日期 YYYY-MM-DD")
    parser.add_argument("--commit", default=None, help="可选：冻结 commit 完整 hash")
    parser.add_argument("--apply", action="store_true", help="不加则只检查，不写文件")
    args = parser.parse_args(argv)

    if not valid_reviewers(args.reviewers):
        print("至少需要两位独立复核人，使用不重复的 A—E 标识。")
        return 2
    if not valid_review_date(args.date):
        print("日期格式应为 YYYY-MM-DD。")
        return 2

    try:
        rows = _read(args.labels)
        cases = load_cases(args.cases) if args.cases is not None else None
    except (OSError, ValueError) as exc:
        print(f"读取标签或案例失败：{exc}")
        return 2
    if not rows or cases == []:
        print("标签文件或所选案例集为空。")
        return 2
    problems = validate(rows)
    if problems:
        for p in problems:
            print(p)
        print("标签结构检查未通过，未做任何修改。")
        return 2

    all_ids = {row["case_id"] for row in rows}
    selected_ids = {case.case_id for case in cases} if cases is not None else all_ids
    missing = sorted(selected_ids - all_ids)
    if missing:
        print(f"所选案例缺少标签：{missing}；未做任何修改。")
        return 2

    if not args.apply:
        print(f"检查通过：检查 {len(rows)} 条标签，选中 {len(selected_ids)} 条。")
        print(f"待写入：review_status=reviewed, reviewers={args.reviewers}, reviewed_at={args.date}")
        print("确认无误后加 --apply 执行。")
        return 0

    finalized = [
        finalize([row], args.reviewers, args.date, args.commit)[0]
        if row["case_id"] in selected_ids else row
        for row in rows
    ]
    args.labels.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in finalized),
        encoding="utf-8",
    )
    print(f"已更新 {len(selected_ids)} 条复核记录；数值与案例文件未改动。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
