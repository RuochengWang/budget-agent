"""E 的最小界面起点。正式表单、图表和历史回放页面由 E 扩展。"""

from decimal import Decimal, InvalidOperation

import streamlit as st
from pydantic import ValidationError

from budget_agent.config import load_config
from budget_agent.main import load_cases
from budget_agent.schemas import CaseInput
from budget_agent.storage import save_record
from budget_agent.workflow import run_case


def money_input(value: str) -> int | None:
    """空白为缺失；用 Decimal 避免元转分时出现浮点误差。"""
    if not value.strip():
        return None
    amount = Decimal(value.strip())
    if not amount.is_finite() or amount < 0 or amount * 100 != (amount * 100).to_integral_value():
        raise ValueError("金额必须为非负数，且最多两位小数")
    return int(amount * 100)


def yuan(value: int | None) -> str:
    return "待确认" if value is None else f"¥{Decimal(value) / 100:,.2f}"


st.set_page_config(page_title="赛博节俭局 · 协作骨架", page_icon="🛒", layout="wide")
st.title("🛒 赛博节俭局")
st.caption("消费决策 Agent · 五人协作开发骨架")
config = load_config()
cases = load_cases(config.data_dir / "cases/dev.jsonl")
selected = st.selectbox("加载开发案例", cases, format_func=lambda case: case.title)
mode = st.selectbox(
    "运行方式",
    ["demo", "real"],
    format_func=lambda mode: "离线演示替身" if mode == "demo" else "正式模块（待开发）",
)
st.info("离线模式使用脚本角色与手工优惠样例。商品、活动与建议均为演示，不是实时购物信息。")
if mode == "real":
    st.warning("正式业务接口尚待 A—E 完成；未实现时会显示 partial，不会切换到演示替身。")

# E 可扩展为完整表单；金额控件以文本输入，允许明确保留缺失值。
with st.form(f"profile_{selected.case_id}"):
    st.write("预算金额以元填写；留空表示尚未提供，0 表示已确认没有该项支出。")
    cols = st.columns(3)
    fields = [
        ("cash_cents", "当前现金"),
        ("daily_essential_cents", "每日基本开支"),
        ("fixed_expenses_cents", "剩余固定支出"),
        ("reserve_cents", "预留金"),
    ]
    inputs = {}
    for index, (field, label) in enumerate(fields):
        value = getattr(selected.profile, field)
        inputs[field] = cols[index % 3].text_input(
            f"{label}（元）", value="" if value is None else str(Decimal(value) / 100)
        )
    days = cols[1].text_input("距下次生活费天数", value=str(selected.profile.days_remaining))
    shipping = cols[2].text_input(
        "运费（元）",
        value=""
        if selected.request.shipping_cents is None
        else str(Decimal(selected.request.shipping_cents) / 100),
    )
    reason = st.text_area("购买理由", value=selected.request.need_reason)
    submitted = st.form_submit_button("运行并保存本地记录")

if submitted:
    try:
        raw = selected.model_dump(mode="json")
        raw["profile"].update({field: money_input(value) for field, value in inputs.items()})
        raw["profile"]["days_remaining"] = int(days) if days.strip() else None
        raw["request"]["shipping_cents"] = money_input(shipping)
        raw["request"]["need_reason"] = reason
        case = CaseInput.model_validate(raw)
        with st.spinner("正在运行…"):
            record = run_case(case, config.model_copy(update={"mode": mode}))
            saved = save_record(record, config.output_dir)
        st.session_state["record"] = record
        st.session_state["saved"] = str(saved)
    except (ValueError, InvalidOperation, ValidationError):
        st.error("请检查输入：金额最多两位小数，天数为非负整数，需求理由不能为空。")

record = st.session_state.get("record")
if record:
    st.subheader("本次结果")
    st.caption(
        f"案例：{record.input.title} | 模式：{record.mode} | 状态：{record.status} | 模型：{record.model}"
    )
    if record.final_decision:
        decision = record.final_decision
        a, b, c = st.columns(3)
        a.metric("可自由支配预算", yuan(decision.budget_result.discretionary_cents))
        b.metric(
            "方案总付款",
            yuan(decision.offer_result.payable_cents) if decision.offer_result else "待确认",
        )
        c.metric(
            "建议",
            {"buy": "购买", "wait": "等待", "skip": "放弃", "need_info": "补充信息"}[
                decision.action
            ],
        )
        st.write(decision.reason_summary)
        st.write("下一步：" + "；".join(decision.next_steps))
    for error in record.errors:
        st.error(error)
    for argument in record.arguments:
        with st.expander(
            {"desire": "欲望观点", "rational": "理性观点", "deal": "优惠观点"}.get(
                argument.role, argument.role
            )
        ):
            st.write("；".join(argument.claims))
            st.caption("证据：" + ", ".join(argument.evidence_ids))
    with st.expander("证据、工具轨迹与原始记录"):
        st.json(record.model_dump(mode="json"))
    st.caption(f"已保存本地记录：{st.session_state['saved']}")
    st.download_button(
        "下载本次记录",
        record.model_dump_json(indent=2),
        file_name=f"{record.run_id}.json",
        mime="application/json",
    )
