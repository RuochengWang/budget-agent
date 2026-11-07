from budget_agent.errors import ModuleNotReady
from budget_agent.main import main
from budget_agent.schemas import DecisionProposal
from budget_agent.storage import load_record, save_record
from budget_agent.tools import budget
from budget_agent.workflow import build_services, run_case


def test_offline_end_to_end_and_replay(cases, config):
    record = run_case(cases["tissue_buy"], config)
    assert record.status == "completed", record.errors
    assert record.mode == "demo"
    assert record.model == "fake/scripted"
    assert record.final_decision.action == "buy"
    assert record.final_decision.offer_result.payable_cents == 25500
    assert record.final_decision.budget_result.remaining_cash_cents == 94500
    assert record.final_decision.offer_result.verification_method == "demo_fixture"
    assert len(record.tool_calls) == 5
    assert len(record.model_calls) == 4
    restored = load_record(save_record(record, config.output_dir))
    assert restored == record
    assert restored.prompt_hashes
    assert "api_key" not in record.config_snapshot


def test_missing_profile_stops_before_models(cases, config):
    record = run_case(cases["missing_profile"], config)
    assert record.status == "needs_input"
    assert record.final_decision.action == "need_info"
    assert len(record.tool_calls) == 1
    assert not record.model_calls


def test_unknown_shipping_is_not_approved(cases, config):
    record = run_case(cases["unknown_shipping"], config)
    assert record.status == "needs_input"
    assert record.final_decision.offer_result.payable_cents is None
    assert record.final_decision.action == "need_info"


def test_real_mode_does_not_fallback(cases, config, monkeypatch):
    def not_ready(*args, **kwargs):
        raise ModuleNotReady("测试：正式预算暂不可用")

    monkeypatch.setattr(budget, "calculate_budget", not_ready)
    real = config.model_copy(update={"mode": "real"})
    record = run_case(cases["sneakers_wait"], real)
    assert record.mode == "real"
    assert record.status == "partial"
    assert record.final_decision is None
    assert not record.model_calls
    assert "正式预算暂不可用" in record.errors[0]


def test_model_buy_is_overridden_but_original_saved(cases, config):
    services = build_services(config)
    services.judge = lambda context, model: DecisionProposal(
        action="buy", reason_summary="错误地推荐购买", evidence_ids=["budget:final"], next_steps=[]
    )
    record = run_case(cases["sneakers_wait"], config, services)
    assert record.proposed_decision.action == "buy"
    assert record.final_decision.action == "wait"
    assert record.policy_violations


def test_tool_limit_preserves_partial_trace(cases, config):
    record = run_case(cases["tissue_buy"], config.model_copy(update={"max_tool_calls": 3}))
    assert record.status == "partial"
    assert len(record.tool_calls) == 3
    assert record.errors
    assert record.evidence


def test_cli_real_exit_is_nonzero_and_demo_zero(monkeypatch):
    def not_ready(*args, **kwargs):
        raise ModuleNotReady("测试：正式预算暂不可用")

    monkeypatch.setattr(budget, "calculate_budget", not_ready)
    assert main(["run", "--mode", "real"]) == 2
    assert main(["run", "--case", "sneakers_wait"]) == 0
