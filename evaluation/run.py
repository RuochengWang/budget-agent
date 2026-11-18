"""E：统一评测运行器。

python -m evaluation.run --baseline M --cases data/cases/test.jsonl \
    --labels data/cases/labels.jsonl --output outputs/evaluation-M.jsonl

硬性守卫（任何一条不满足都 exit 2，不写结果文件）：
- 测试集与标签必须是已复核冻结版本；
- 配置统一 mode=real，拒绝 demo / fake/scripted / demo_fixture 记录；
- 未运行样本只进分母，不记为正确；
- 输出包含配置快照、数据哈希与 commit（若可读），不换算费用。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from budget_agent.config import AppConfig, load_config
from budget_agent.errors import AgentError, ModuleNotReady
from budget_agent.main import load_cases
from budget_agent.schemas import RunRecord
from evaluation.baselines import BASELINES, baseline_plan, run_baseline
from evaluation.metrics import compute_metrics, validate_labels


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{number} 不是合法 JSON：{exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{number} 必须是 JSON 对象")
        rows.append(row)
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, timeout=5
        )
        return result.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _config_snapshot(config: AppConfig) -> dict[str, Any]:
    """不含密钥（AppConfig.api_key 已 exclude=True）。"""
    data = config.model_dump(mode="json")
    data.pop("api_key", None)
    return data


def _unusable_records(records: list[RunRecord]) -> list[str]:
    """返回不能作为正式成绩的记录说明；partial/failed 绝不写成"已评测"。"""
    problems: list[str] = []
    for record in records:
        offer = record.final_decision.offer_result if record.final_decision else None
        if record.mode != "real" or record.model == "fake/scripted":
            problems.append(f"{record.run_id}: 演示替身（mode={record.mode}, model={record.model}）")
        if offer is not None and offer.verification_method == "demo_fixture":
            problems.append(f"{record.run_id}: 手工优惠 fixture")
        if record.status not in {"completed", "needs_input"}:
            problems.append(f"{record.run_id}: 状态={record.status}，未形成完整业务结论")
        if record.final_decision is None:
            problems.append(f"{record.run_id}: 没有最终建议，不能计为已运行")
        if record.errors:
            problems.append(f"{record.run_id}: 运行含错误 {record.errors}")
    return problems


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, Path)):
        return str(value)
    raise TypeError(f"无法序列化：{type(value).__name__}")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, default=_json_default) + "\n" for row in rows),
        encoding="utf-8",
    )


def evaluate(
    *, baseline: str, cases_path: Path, labels_path: Path, config: AppConfig, strict_labels: bool
) -> tuple[list[RunRecord], dict, list[str]]:
    """可复用的评测函数；返回 (records, summary, problems)。"""
    problems: list[str] = []
    cases = load_cases(cases_path)
    if not cases:
        return [], {}, ["评测集为空：请先由 E 编写、复核并冻结案例。"]
    all_labels = _read_jsonl(labels_path)
    # 一个标签文件可同时包含 dev 与 test 标签；只校验本次案例对应的标签，
    # 其它案例的标签既不算分母也不算"未知案例"。
    label_index = {label.get("case_id"): label for label in all_labels}
    case_ids = {case.case_id for case in cases}
    labels = [label_index[cid] for cid in case_ids if cid in label_index]
    problems.extend(validate_labels(labels, require_reviewed=strict_labels))
    missing = sorted(case_ids - set(label_index))
    duplicates = sorted(
        cid for cid in {label.get("case_id") for label in all_labels}
        if sum(1 for label in all_labels if label.get("case_id") == cid) > 1
    )
    if missing:
        problems.append(f"缺少独立标签：{missing}")
    if duplicates:
        problems.append(f"标签文件中存在重复 case_id：{duplicates}")
    if config.mode != "real":
        problems.append("配置必须是 real 模式；拒绝演示替身")
    if problems:
        return [], {}, problems

    try:
        records = [run_baseline(baseline, case, config=config) for case in cases]
    except (ModuleNotReady, AgentError) as exc:
        return [], {}, [str(exc)]

    unusable = _unusable_records(records)
    if unusable:
        return [], {}, ["拒绝把演示替身、手工 fixture 或未完成的运行当作正式实验结果：", *unusable]

    metrics = compute_metrics(records, labels)
    summary: dict[str, Any] = {
        "baseline": baseline,
        "baseline_plan": baseline_plan(baseline),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "config": _config_snapshot(config),
        "cases": {"path": str(cases_path), "sha256": _sha256(cases_path), "count": len(cases)},
        "labels": {"path": str(labels_path), "sha256": _sha256(labels_path), "count": len(labels)},
        "strict_labels": strict_labels,
        "status": "computed",
        "metrics": metrics,
    }
    return records, summary, []


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="E：基线评测运行器")
    parser.add_argument("--baseline", required=True, choices=BASELINES)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True, help="独立人工标签 JSONL")
    parser.add_argument("--output", type=Path, default=Path("outputs/evaluation.jsonl"))
    parser.add_argument("--summary", type=Path, default=None, help="汇总 JSON，默认与 output 同名 .summary.json")
    parser.add_argument("--config", type=Path, default=None, help="A 的统一 TOML 配置")
    parser.add_argument("--mode", choices=["demo", "real"], default="real")
    parser.add_argument(
        "--allow-draft-labels", action="store_true",
        help="仅用于本地自测：允许未复核标签；绝不能用于正式成绩",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.mode != "real":
        print("正式评测只允许 real 模式；演示模式不产生成绩。")
        return 2
    try:
        config = load_config(args.config, mode="real")
        records, summary, problems = evaluate(
            baseline=args.baseline,
            cases_path=args.cases,
            labels_path=args.labels,
            config=config,
            strict_labels=not args.allow_draft_labels,
        )
    except (OSError, ValueError, ValidationError) as exc:
        print(f"评测输入或配置错误（{type(exc).__name__}）：{exc}")
        return 2
    if problems:
        for problem in problems:
            print(problem)
        print("没有产生评测结果。")
        return 2

    _write_jsonl(args.output, [record.model_dump(mode="json") for record in records])
    summary_path = args.summary or args.output.with_suffix(".summary.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8"
    )
    print(f"基线={args.baseline} | 记录={len(records)} | 汇总={summary_path}")
    print(f"总样本={summary['metrics']['total_cases']} | "
          f"未运行={len(summary['metrics']['not_run'])} | "
          f"无标签记录={len(summary['metrics']['unmatched_records'])}")
    print(f"记录文件={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
