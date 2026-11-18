"""E：11/20 彩排自检（只读，不调用模型、不联网、不修改业务文件）。

用法：
    .venv/bin/python -m evaluation.rehearsal_check
    .venv/bin/python -m evaluation.rehearsal_check --strict   # 有阻塞项时退出 2

检查项对应 docs/E/demo.md §8 清单；只报告事实，不把 TODO 写成已完成。
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from budget_agent.config import PROJECT_ROOT, load_config
from budget_agent.main import load_cases
from evaluation.metrics import validate_labels


def _git(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args], capture_output=True, text=True, check=True, timeout=5
        )
        return result.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _check(label: str, ok: bool, detail: str) -> dict:
    return {"item": label, "status": "OK" if ok else "TODO", "detail": detail}


def collect(config_path: Path | None = None) -> dict:
    config = load_config(config_path)
    out: list[dict] = []

    commit = _git("rev-parse", "HEAD")
    tag = _git("describe", "--tags", "--exact-match")
    out.append(_check(
        "冻结 commit", bool(commit),
        f"HEAD={commit or '不可读'}；展示脚本 TODO 需填写此值" + (f"，tag={tag}" if tag else "，尚无 tag"),
    ))

    dirty = _git("status", "--porcelain")
    out.append(_check(
        "工作区干净", dirty == "",
        "无未提交改动" if dirty == "" else f"有 {len((dirty or '').splitlines())} 处改动，冻结版本应提交后再彩排",
    ))

    dev = load_cases(config.data_dir / "cases" / "dev.jsonl")
    test = load_cases(config.data_dir / "cases" / "test.jsonl")
    labels_path = config.data_dir / "cases" / "labels.jsonl"
    labels = [
        json.loads(line)
        for line in labels_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    test_ids = {case.case_id for case in test}
    test_labels = [label for label in labels if label.get("case_id") in test_ids]
    reviewed = [
        label for label in test_labels if not validate_labels([label], require_reviewed=True)
    ]
    out.append(_check(
        "开发/测试案例数量", len(dev) == 10 and len(test) == 30,
        f"dev={len(dev)}，test={len(test)}",
    ))
    label_ids = {label["case_id"] for label in test_labels}
    all_reviewed = (
        bool(test_ids) and len(test_labels) == len(reviewed) == len(test_ids) and label_ids == test_ids
    )
    out.append(_check(
        "独立标签已复核", all_reviewed,
        f"测试集：有效 reviewed={len(reviewed)}/{len(test_ids)}；"
        + ("开发集不在本轮冻结范围" if all_reviewed else "仍有 draft、缺失或不合规标签"),
    ))
    sheet = config.data_dir / "cases" / "review_sheet.md"
    out.append(_check(
        "复核工作表", sheet.is_file(), str(sheet) if sheet.is_file() else "缺失",
    ))

    records = sorted(config.output_dir.glob("*.json")) if config.output_dir.is_dir() else []
    demo_records: list[str] = []
    real_records: list[str] = []
    partial_records: list[str] = []
    for path in records:
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        mode, status = row.get("mode"), row.get("status")
        if mode == "demo":
            demo_records.append(path.name)
        if mode == "real":
            real_records.append(path.name)
        if status == "partial":
            partial_records.append(path.name)
    out.append(_check(
        "历史记录可回放", bool(records),
        f"共 {len(records)} 条：demo={len(demo_records)}，real={len(real_records)}，partial={len(partial_records)}"
        "（11/20 需生成 3 条冻结版本记录并记路径）",
    ))

    evals = sorted(config.output_dir.glob("*.summary.json")) if config.output_dir.is_dir() else []
    out.append(_check(
        "正式评测结果", True,  # 有无成绩都不阻塞彩排，只如实报告数量与来源。
        f"本机汇总文件 {len(evals)} 个；标签未复核、缺模型密钥或实验未运行前为 0 属正常，"
        "11/17–18 真实实验后应能追溯到 outputs/*.summary.json（不入库）",
    ))

    app = PROJECT_ROOT / "app.py"
    app_text = app.read_text(encoding="utf-8") if app.is_file() else ""
    out.append(_check(
        "界面两页", "历史回放" in app_text and "运行" in app_text,
        "运行 / 历史回放 均存在" if "历史回放" in app_text else "缺少历史回放页",
    ))

    demo_doc = PROJECT_ROOT / "docs" / "E" / "demo.md"
    demo_text = demo_doc.read_text(encoding="utf-8") if demo_doc.is_file() else ""
    out.append(_check(
        "展示脚本", demo_doc.is_file() and "20 分钟" in demo_text,
        f"{demo_doc}，TODO 项 {demo_text.count('TODO')} 处待 11/19–20 填写",
    ))

    video = list(PROJECT_ROOT.glob("docs/E/*录像*")) + list(PROJECT_ROOT.glob("docs/E/*.mp4"))
    out.append(_check(
        "备用录像", bool(video),
        "已找到 " + ", ".join(p.name for p in video) if video else "未找到；11/20 需录制并填写路径",
    ))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(PROJECT_ROOT),
        "mode_default": config.mode,
        "checks": out,
        "blockers": [item["item"] for item in out if item["status"] == "TODO"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="E：11/20 彩排自检")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--strict", action="store_true", help="有阻塞项时退出 2")
    parser.add_argument("--json", action="store_true", help="输出 JSON 而非表格")
    args = parser.parse_args(argv)
    result = collect(args.config)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"彩排自检（{result['generated_at']}）")
        print(f"默认模式={result['mode_default']} | 项目={result['project_root']}")
        for item in result["checks"]:
            print(f"[{item['status']:4s}] {item['item']}: {item['detail']}")
        print(f"待办/阻塞项：{', '.join(result['blockers']) or '无'}")
    return 2 if args.strict and result["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
