"""离线联调探针的验收：只读、不调真实模型、不发网络请求。"""

from __future__ import annotations

from evaluation.integration_probe import run_probe


def test_offline_integration_probe_wires_bcd_and_e(monkeypatch):
    from budget_agent.model_client import ChatModelClient

    def no_live_model(*args, **kwargs):
        raise AssertionError("离线探针不能调用真实模型")

    monkeypatch.setattr(ChatModelClient, "generate_json", no_live_model)
    result = run_probe()
    sneakers = result["sneakers_wait"]
    assert sneakers["status"] == "completed"
    assert sneakers["payable"] == 65000
    assert sneakers["verification"] == "solver"
    assert sneakers["tool_calls"] == 5
    assert sneakers["errors"] == []
    assert result["missing_profile"]["payable"] is None
    assert result["missing_profile"]["tool_calls"] == 1
    assert result["unknown_shipping"]["payable"] is None
    assert result["unknown_shipping"]["verification"] == "unverified"
    assert result["tissue_buy"]["action"] == "buy"
    assert result["tissue_buy"]["payable"] == 25500
    assert result["label_guard"] == {"valid_draft": True, "rejected_in_strict_mode": True}


def test_probe_does_not_change_working_tree_files():
    from budget_agent.config import PROJECT_ROOT

    before = {
        p: (PROJECT_ROOT / p).stat().st_mtime_ns
        for p in ("data/cases/labels.jsonl", "data/cases/test.jsonl", "data/cases/dev.jsonl")
    }
    run_probe()
    after = {p: (PROJECT_ROOT / p).stat().st_mtime_ns for p in before}
    assert before == after