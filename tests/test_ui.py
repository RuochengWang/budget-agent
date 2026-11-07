"""最小端到端界面检查：明确演示标识、提交后能看到结果。"""

from streamlit.testing.v1 import AppTest

from budget_agent.config import PROJECT_ROOT


def test_ui_load_and_submit():
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=20).run()
    assert not app.exception
    assert "演示" in app.info[0].value
    app.button[0].click().run()
    assert not app.exception
    assert len(app.metric) == 3
    assert app.session_state["record"].mode == "demo"
    assert app.session_state["record"].final_decision.action == "wait"
