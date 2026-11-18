"""11/20 彩排自检脚本的验收：只读、如实报告、--strict 语义。"""

from __future__ import annotations

import json

from budget_agent.config import PROJECT_ROOT
from evaluation import rehearsal_check
from evaluation.rehearsal_check import collect, main


def test_collect_is_read_only_and_reports_facts(monkeypatch, tmp_path):
    # 用临时目录替换 output_dir，避免读取本机历史记录。
    real_load = rehearsal_check.load_config

    def fake_load(path=None):
        config = real_load(path)
        return config.model_copy(update={"output_dir": tmp_path})

    monkeypatch.setattr(rehearsal_check, "load_config", fake_load)
    before = sorted(p.stat().st_mtime_ns for p in PROJECT_ROOT.glob("*") if p.is_file())
    result = collect()
    after = sorted(p.stat().st_mtime_ns for p in PROJECT_ROOT.glob("*") if p.is_file())
    assert before == after
    assert "generated_at" in result
    assert any(item["item"] == "独立标签已复核" for item in result["checks"])
    assert any(item["item"] == "备用录像" for item in result["checks"])
    assert all(item["status"] in {"OK", "TODO"} for item in result["checks"])


def test_collect_only_requires_review_for_test_labels(monkeypatch, tmp_path):
    from shutil import copyfile

    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    for name in ("dev.jsonl", "test.jsonl", "labels.jsonl"):
        copyfile(PROJECT_ROOT / "data" / "cases" / name, cases_dir / name)
    test_ids = {c.case_id for c in rehearsal_check.load_cases(cases_dir / "test.jsonl")}
    labels = [json.loads(line) for line in (cases_dir / "labels.jsonl").read_text(
        encoding="utf-8"
    ).splitlines() if line.strip()]
    for row in labels:
        row.update(review_status="draft", reviewers=[], reviewed_at=None)
    config = rehearsal_check.load_config().model_copy(
        update={"data_dir": tmp_path, "output_dir": tmp_path},
    )
    monkeypatch.setattr(rehearsal_check, "load_config", lambda _: config)

    def status():
        (cases_dir / "labels.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in labels), encoding="utf-8",
        )
        return next(x for x in collect()["checks"] if x["item"] == "独立标签已复核")["status"]

    assert status() == "TODO"
    for row in labels:
        if row["case_id"] in test_ids:
            row.update(review_status="reviewed", reviewers=["A", "C"], reviewed_at="2026-11-18")
    assert status() == "OK"


def test_main_json_mode_and_strict_exit(monkeypatch, capsys):
    result = collect()
    result["blockers"] = ["示例阻塞项"]
    monkeypatch.setattr(rehearsal_check, "collect", lambda _: result)
    assert main(["--json"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["checks"]
    assert main(["--strict"]) == 2
    assert main([]) == 0
