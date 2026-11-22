"""界面验收：演示标识、表单提交、缺失值、正式失败与历史回放。"""

from datetime import date, time
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from budget_agent import config, workflow
from budget_agent.config import PROJECT_ROOT
from budget_agent.model_client import FakeModel


@pytest.fixture(autouse=True)
def isolated_app_config(monkeypatch, tmp_path):
    # 读实际 TOML，但隔离本地环境、密钥与输出。
    load_config = config.load_config
    monkeypatch.setattr(config, "load_dotenv", lambda *args, **kwargs: False)
    for name in ("BUDGET_AGENT_API_KEY", "BUDGET_AGENT_MODEL", "BUDGET_AGENT_BASE_URL"):
        monkeypatch.delenv(name, raising=False)

    def load_isolated(path=None, *, mode=None):
        return load_config(path, mode=mode).model_copy(update={"output_dir": tmp_path})

    monkeypatch.setattr(config, "load_config", load_isolated)


def _app() -> AppTest:
    return AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=30).run()


def _text_input(app: AppTest, label: str):
    return [widget for widget in app.text_input if widget.proto.label == label][0]


def _selectbox(app: AppTest, label: str):
    return [widget for widget in app.selectbox if widget.proto.label == label][0]


def _fill_example(app: AppTest, target: str = "sneakers") -> None:
    app.selectbox(key="target").set_value(target)
    for key, value in {
        "cash_cents": "1200",
        "daily_essential_cents": "40",
        "fixed_expenses_cents": "0",
        "reserve_cents": "100",
        "days": "20",
        "shipping": "0",
    }.items():
        app.text_input(key=key).set_value(value)
    app.date_input(key="date").set_value(date(2026, 11, 18))
    app.time_input(key="time").set_value(time(16, 0))
    app.text_area(key="reason").set_value("课堂演示购买需求")


def test_ui_load_and_submit():
    app = _app()
    assert not app.exception
    assert "演示" in app.info[0].value
    assert "加载开发案例" not in [widget.label for widget in app.selectbox]
    assert not app.checkbox
    assert app.selectbox(key="target").value is None
    assert app.text_input(key="cash_cents").value == ""
    assert app.text_input(key="cash_cents").proto.placeholder == "例如 1200"
    _fill_example(app)
    app.button[0].click().run()
    assert not app.exception
    assert len(app.metric) == 3
    record = app.session_state["record"]
    assert record.mode == "demo"
    assert record.config_snapshot["request_timeout_seconds"] == 45
    assert record.config_snapshot["workflow_timeout_seconds"] == 180
    assert record.input.case_id.startswith("manual_")
    assert record.final_decision.action == "wait"
    assert record.final_decision.offer_result.payable_cents == 65000
    assert any(subheader.value == "本次结果" for subheader in app.subheader)


def test_ui_blank_money_stays_missing():
    app = _app()
    _fill_example(app)
    # 表单内的控件只在提交时提交，因此先设置值再点击提交按钮。
    _text_input(app, "当前现金（元）").set_value("")
    app.button[0].click().run()
    assert not app.exception
    record = app.session_state["record"]
    assert record.input.profile.cash_cents is None
    assert record.status == "needs_input"
    assert record.final_decision.action == "need_info"


def test_ui_zero_is_kept_apart_from_missing():
    app = _app()
    _fill_example(app)
    _text_input(app, "当前现金（元）").set_value("0")
    app.button[0].click().run()
    assert not app.exception
    record = app.session_state["record"]
    assert record.input.profile.cash_cents == 0
    assert record.input.profile.reserve_cents == 10000


def test_ui_can_enter_a_different_product_and_addon():
    app = _app()
    labels = [widget.proto.label for widget in app.selectbox]
    assert "目标商品" in labels
    assert "需求紧迫程度" in labels
    assert [widget.proto.label for widget in app.multiselect] == ["确实需要一并购买的凑单品（最多 8 个）"]
    _fill_example(app, target="daily_goods")
    app.multiselect(key="addons").set_value(["tissue"])
    app.button[0].click().run()
    assert not app.exception
    record = app.session_state["record"]
    assert record.input.request.target_product_id == "daily_goods"
    assert record.input.request.needed_addon_ids == ["tissue"]
    assert record.final_decision.offer_result.payable_cents == 25500
    assert record.final_decision.action == "buy"


def test_ui_reports_a_missing_product_or_reason():
    app = _app()
    app.button[0].click().run()
    assert app.error[0].value == "请选择目标商品。"
    app.selectbox(key="target").set_value("sneakers")
    app.button[0].click().run()
    assert app.error[0].value == "请填写购买理由。"
    assert "record" not in app.session_state


def test_ui_real_mode_uses_validation_config_and_does_not_fall_back():
    app = _app()
    _selectbox(app, "运行方式").set_value("real").run()
    assert app.checkbox(key="cross_response").value is False
    _fill_example(app)
    app.button[0].click().run()
    assert not app.exception
    record = app.session_state["record"]
    assert record.mode == "real"
    assert record.config_snapshot["request_timeout_seconds"] == 90
    assert record.config_snapshot["workflow_timeout_seconds"] == 540
    assert record.config_snapshot["cross_response_enabled"] is False
    assert "api_key" not in record.config_snapshot
    assert record.status == "partial"
    assert any("部分完成" in warning.value for warning in app.warning)


def test_ui_runs_cross_response_and_displays_the_round_on_replay(monkeypatch):
    build_services = workflow.build_services

    def respond(role, payload):
        if role == "cross_response":
            speaker = payload["speaking_as"]
            return {
                "role": speaker,
                "answers_role": "rational" if speaker == "desire" else "desire",
                "stance": "oppose",
                "claim": (
                    "先弄清这周末所需的防滑条件。"
                    if speaker == "desire"
                    else "借鞋也可能满足同样的步行需求。"
                ),
                "evidence_ids": ["input:request"],
            }
        if role == "judge":
            return {
                "action": "wait",
                "reason_summary": "先确认借鞋安排。",
                "evidence_ids": ["input:request"],
                "next_steps": ["问同学是否能借到合适的鞋。"],
            }
        return {
            "role": role,
            "stance": "neutral",
            "claims": ["根据输入说明本角色的看法。"],
            "evidence_ids": ["input:request"],
        }

    def build_offline(app_config):
        services = build_services(app_config)
        services.model = FakeModel(respond)
        return services

    monkeypatch.setattr(workflow, "build_services", build_offline)
    app = _app()
    _selectbox(app, "运行方式").set_value("real").run()
    _fill_example(app)
    app.text_input(key="cash_cents").set_value("1600")
    app.text_area(key="reason").set_value("周末需要长时间步行，可能借到鞋。")
    app.checkbox(key="cross_response").check()
    app.button[0].click().run()
    assert not app.exception
    record = app.session_state["record"]
    assert record.status == "completed"
    assert record.config_snapshot["cross_response_enabled"] is True
    assert record.final_decision.budget_result.discretionary_cents == 70000
    assert record.final_decision.offer_result.payable_cents == 65000
    assert len([trace for trace in record.model_calls if trace.role == "cross_response"]) == 2

    for replay in (False, True):
        if replay:
            app.radio[0].set_value("历史回放").run()
        assert not app.exception
        headings = [item.value for item in app.markdown]
        assert headings.index("### 初始观点") < headings.index("### 交叉回应")
        assert headings.index("### 交叉回应") < headings.index("### 裁判建议")
        expanders = [item.label for item in app.expander]
        assert "欲望回应理性 · 反对" in expanders
        assert "理性回应欲望 · 反对" in expanders
        assert "- 借鞋也可能满足同样的步行需求。" in headings


def test_ui_replay_saved_record():
    app = _app()
    _fill_example(app)
    app.button[0].click().run()
    assert not app.exception
    saved = Path(app.session_state["saved"])
    assert saved.is_file()
    app.radio[0].set_value("历史回放").run()
    assert not app.exception
    assert any("历史回放" in warning.value for warning in app.warning)
