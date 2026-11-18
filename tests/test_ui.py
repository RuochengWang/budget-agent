"""界面验收：演示标识、表单提交、缺失值、正式失败与历史回放。"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from budget_agent import config
from budget_agent.config import PROJECT_ROOT


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


def test_ui_load_and_submit():
    app = _app()
    assert not app.exception
    assert "演示" in app.info[0].value
    app.button[0].click().run()
    assert not app.exception
    assert len(app.metric) == 3
    record = app.session_state["record"]
    assert record.mode == "demo"
    assert record.config_snapshot["request_timeout_seconds"] == 45
    assert record.config_snapshot["workflow_timeout_seconds"] == 180
    assert record.final_decision.action == "wait"
    assert any(subheader.value == "本次结果" for subheader in app.subheader)


def test_ui_blank_money_stays_missing():
    app = _app()
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
    _text_input(app, "当前现金（元）").set_value("0")
    app.button[0].click().run()
    assert not app.exception
    record = app.session_state["record"]
    assert record.input.profile.cash_cents == 0
    assert record.input.profile.reserve_cents == 10000


def test_ui_switch_case_uses_new_inputs():
    app = _app()
    labels = [widget.proto.label for widget in app.selectbox]
    assert "目标商品" in labels
    assert "需求紧迫程度" in labels
    assert [widget.proto.label for widget in app.multiselect] == ["确实需要一并购买的凑单品（最多 8 个）"]
    _selectbox(app, "加载开发案例").select_index(6).run()
    app.button[0].click().run()
    assert not app.exception
    record = app.session_state["record"]
    assert record.input.case_id == "addon_not_worth_it"
    assert record.final_decision.offer_result.payable_cents == 28000
    assert record.final_decision.action == "buy"


def test_ui_real_mode_uses_validation_config_and_does_not_fall_back():
    app = _app()
    _selectbox(app, "运行方式").set_value("real").run()
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


def test_ui_replay_saved_record():
    app = _app()
    app.button[0].click().run()
    assert not app.exception
    saved = Path(app.session_state["saved"])
    assert saved.is_file()
    app.radio[0].set_value("历史回放").run()
    assert not app.exception
    assert any("历史回放" in warning.value for warning in app.warning)
