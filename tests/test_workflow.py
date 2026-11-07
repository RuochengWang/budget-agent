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


def test_workflow_deadline_preserves_partial_record(cases, config, monkeypatch):
    # 第一步：给总控和工具管理使用同一个模拟时钟，不进行真实等待。
    clock = {"now": 100.0}
    monkeypatch.setattr("budget_agent.workflow.monotonic", lambda: clock["now"])
    monkeypatch.setattr("budget_agent.tools.registry.monotonic", lambda: clock["now"])
    config = config.model_copy(update={"workflow_timeout_seconds": 10})
    services = build_services(config)
    original_desire = services.desire

    # 第二步：欲望节点返回观点时，将时钟推进到整次任务截止时间之后。
    def finish_after_deadline(context, model):
        argument = original_desire(context, model)
        clock["now"] = 111.0
        return argument

    services.desire = finish_after_deadline
    record = run_case(cases["sneakers_wait"], config, services)

    # 第三步：下一步开始前必须终止，保留已有观点、证据和工具轨迹。
    assert record.status == "partial"
    assert record.errors == ["工作流已达到时间上限"]
    assert [trace.name for trace in record.tool_calls] == ["calculate_budget", "get_products"]
    assert [argument.role for argument in record.arguments] == ["desire"]
    assert [trace.role for trace in record.model_calls] == ["desire"]
    assert any(evidence.id == "budget:initial" for evidence in record.evidence)
    assert record.proposed_decision is None
    assert record.final_decision is None
    assert record.finished_at is not None
    assert load_record(save_record(record, config.output_dir)) == record


def test_cli_real_exit_is_nonzero_and_demo_zero(monkeypatch):
    def not_ready(*args, **kwargs):
        raise ModuleNotReady("测试：正式预算暂不可用")

    monkeypatch.setattr(budget, "calculate_budget", not_ready)
    assert main(["run", "--mode", "real"]) == 2
    assert main(["run", "--case", "sneakers_wait"]) == 0
