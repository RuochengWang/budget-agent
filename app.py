"""E 的交互界面：正式表单、结果与失败展示、证据轨迹和历史回放。

界面只调用 workflow.run_case，不重算预算或优惠。金额以元输入、内部整数分；
空白表示尚未提供，0 表示已确认没有该项支出。历史回放读取本地记录，不调用模型。
"""

import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

import streamlit as st
from pydantic import ValidationError

from budget_agent.config import PROJECT_ROOT, load_config
from budget_agent.errors import AgentError
from budget_agent.schemas import Argument, CaseInput, PurchaseRequest, RunRecord, UserProfile
from budget_agent.storage import load_record, save_record
from budget_agent.workflow import run_case

REAL_CONFIG_PATH = PROJECT_ROOT / "configs" / "validation.toml"
CROSS_CONFIG_PATH = PROJECT_ROOT / "configs" / "validation_cross.toml"
CROSS_REPLY_PREFIX = re.compile(r"^（回应([a-z_]+)）")
TZ = timezone(timedelta(hours=8))
ACTION_LABELS = {"buy": "购买", "wait": "等待", "skip": "放弃", "need_info": "补充信息"}
ROLE_LABELS = {"desire": "欲望观点", "rational": "理性观点", "deal": "优惠观点", "judge": "裁判"}
STANCE_LABELS = {"support": "支持", "oppose": "反对", "neutral": "中性"}
URGENCY_LABELS = {"low": "不着急", "medium": "一般", "high": "着急"}
STATUS_LABELS = {
    "running": "执行中",
    "completed": "完成",
    "needs_input": "需要补充信息",
    "partial": "部分完成（有模块未实现或调用中止）",
    "failed": "失败",
}


def money_input(value: str) -> int | None:
    """空白为缺失；用 Decimal 避免元转分出现浮点误差；拒绝负数与超过两位小数。"""
    text = value.strip()
    if not text:
        return None
    amount = Decimal(text)
    if not amount.is_finite() or amount < 0 or amount * 100 != (amount * 100).to_integral_value():
        raise ValueError("金额必须为非负数，且最多两位小数（元）")
    return int(amount * 100)


def days_input(value: str) -> int | None:
    text = value.strip()
    if not text:
        return None
    days = int(text)
    if days < 0:
        raise ValueError("天数必须为非负整数")
    return days


def yuan(value: int | None) -> str:
    return "待确认" if value is None else f"¥{Decimal(value) / 100:,.2f}"


def split_items(text: str) -> list[str]:
    normalized = text.replace("，", ",").replace("、", ",").replace("；", ",")
    return [item.strip() for item in normalized.replace("\n", ",").split(",") if item.strip()]


def load_catalog_products(data_dir: Path) -> list[dict]:
    """读取商品快照用于选择商品；界面只读数据，不实现 C 的业务逻辑。"""
    path = data_dir / "catalog" / "products.json"
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [row for row in rows if isinstance(row, dict) and row.get("id")]


def product_label(row: dict) -> str:
    name = row.get("name", row["id"])
    return f"{row['id']} · {name} · {yuan(row.get('price_cents'))}"


def kv_markdown(rows: list[tuple[str, str]]) -> str:
    body = "\n".join(f"| {key} | {value} |" for key, value in rows)
    return "| 项目 | 值 |\n|---|---|\n" + body


def render_status(record: RunRecord) -> None:
    text = f"状态：{STATUS_LABELS.get(record.status, record.status)}"
    if record.status == "completed":
        st.success(text)
    elif record.status == "needs_input":
        st.info(text)
    elif record.status == "partial":
        st.warning(text + "；未实现或中止的步骤见下方错误与轨迹。")
    else:
        st.error(text)


def render_input(case: CaseInput) -> None:
    profile = case.profile
    request = case.request
    with st.expander("输入与需求"):
        st.markdown(
            kv_markdown(
                [
                    ("目标商品", request.target_product_id),
                    ("购买理由", request.need_reason),
                    ("紧迫程度", URGENCY_LABELS.get(request.urgency, request.urgency)),
                    ("已有相似物品", "、".join(profile.owned_similar_items) or "无"),
                    ("确需一并购买", "、".join(request.needed_addon_ids) or "无"),
                    ("当前现金", yuan(profile.cash_cents)),
                    (
                        "距下次生活费天数",
                        "待确认" if profile.days_remaining is None else str(profile.days_remaining),
                    ),
                    ("每日基本开支", yuan(profile.daily_essential_cents)),
                    ("剩余固定支出", yuan(profile.fixed_expenses_cents)),
                    ("预留金", yuan(profile.reserve_cents)),
                    ("运费", yuan(request.shipping_cents)),
                    ("评估时点", request.as_of.isoformat()),
                ]
            )
        )


def render_calculation(record: RunRecord) -> None:
    decision = record.final_decision
    if decision is None:
        return
    budget = decision.budget_result
    st.markdown("### 客观计算")
    st.markdown("**预算**")
    st.markdown(
        kv_markdown(
            [
                ("基本生活支出", yuan(budget.essential_total_cents)),
                ("可自由支配", yuan(budget.discretionary_cents)),
                ("购买后剩余现金", yuan(budget.remaining_cash_cents)),
                (
                    "是否在预算内",
                    "待确认"
                    if budget.within_budget is None
                    else ("是" if budget.within_budget else "否"),
                ),
                ("缺失字段", "、".join(budget.missing_fields) or "无"),
            ]
        )
    )
    offer = decision.offer_result
    if offer is None:
        st.info("尚未形成可确认的优惠方案。")
        return
    st.markdown("**优惠方案**")
    st.markdown(
        kv_markdown(
            [
                ("购物篮", "、".join(offer.basket_ids) or "无"),
                ("商品小计", yuan(offer.subtotal_cents)),
                ("优惠减免", yuan(offer.discount_cents)),
                ("运费", yuan(offer.shipping_cents)),
                ("方案总付款", yuan(offer.payable_cents)),
                ("单买基准总付款", yuan(offer.baseline_payable_cents)),
                ("使用规则", "、".join(offer.rule_ids) or "无"),
                ("是否已验证", "是" if offer.verified else "否"),
                ("验证方式", offer.verification_method),
                ("未知项", "；".join(offer.unknowns) or "无"),
                ("排除理由", "；".join(offer.excluded_reasons) or "无"),
            ]
        )
    )


def render_argument(
    argument: Argument, title: str, claims: list[str], *, expanded: bool = False
) -> None:
    stance = STANCE_LABELS.get(argument.stance, argument.stance)
    with st.expander(f"{title} · {stance}", expanded=expanded):
        for claim in claims:
            st.markdown(f"- {claim}")
        st.caption("证据：" + ("、".join(argument.evidence_ids) or "无"))
        if argument.unknowns:
            st.caption("未知项：" + "；".join(argument.unknowns))


def render_arguments(record: RunRecord) -> None:
    cross_enabled = record.config_snapshot.get("cross_response_enabled") is True
    initial: list[Argument] = []
    replies: list[tuple[Argument, str, str]] = []
    for argument in record.arguments:
        # D 已在交叉回应正文前加上回应对象，旧记录也使用这个标记。
        if cross_enabled and len(argument.claims) == 1:
            body = argument.claims[0]
            match = CROSS_REPLY_PREFIX.match(body)
            if match and match[1] in ROLE_LABELS and match[1] != argument.role:
                replies.append((argument, match[1], body[match.end():].strip()))
                continue
        initial.append(argument)

    if initial:
        st.markdown("### 初始观点")
        for argument in initial:
            title = ROLE_LABELS.get(argument.role, argument.role)
            render_argument(argument, title, argument.claims)
    if cross_enabled:
        st.markdown("### 交叉回应")
        if not replies:
            st.caption("本次记录没有可展示的交叉回应。")
        for argument, target, body in replies:
            speaker = ROLE_LABELS.get(argument.role, argument.role).removesuffix("观点")
            listener = ROLE_LABELS[target].removesuffix("观点")
            render_argument(argument, f"{speaker}回应{listener}", [body], expanded=True)


def render_decision(record: RunRecord) -> None:
    final = record.final_decision
    if final is None:
        st.info("本次没有形成最终建议：请查看下方错误与轨迹，或补充信息后重试。")
        return
    proposed = record.proposed_decision
    st.markdown("### 裁判建议")
    if proposed is not None and proposed.action != final.action:
        before = ACTION_LABELS.get(proposed.action, proposed.action)
        after = ACTION_LABELS.get(final.action, final.action)
        st.warning(f"程序约束检查把建议从「{before}」调整为「{after}」。")
    for reason in record.policy_violations:
        st.warning("程序检查：" + reason)
    st.write(final.reason_summary)
    if proposed is not None:
        st.caption(
            "原始建议："
            + ACTION_LABELS.get(proposed.action, proposed.action)
            + "；最终建议："
            + ACTION_LABELS.get(final.action, final.action)
        )
    if final.counterargument:
        st.caption("反方观点：" + final.counterargument)
    if final.next_steps:
        st.write("下一步：" + "；".join(final.next_steps))
    st.caption("引用证据：" + ("、".join(final.evidence_ids) or "无"))


def render_traces(record: RunRecord) -> None:
    st.markdown("### 证据与轨迹")
    if record.evidence:
        st.markdown("**证据**")
        st.dataframe(
            [
                {
                    "ID": item.id,
                    "类型": item.kind,
                    "说明": item.description,
                    "演示": "是" if item.is_demo else "否",
                }
                for item in record.evidence
            ]
        )
    if record.tool_calls:
        st.markdown("**工具调用**")
        st.dataframe(
            [
                {
                    "序号": index,
                    "工具": trace.name,
                    "参数": json.dumps(trace.arguments, ensure_ascii=False),
                    "耗时(ms)": trace.elapsed_ms,
                    "错误": trace.error or "",
                }
                for index, trace in enumerate(record.tool_calls, 1)
            ]
        )
    if record.model_calls:
        st.markdown("**模型调用**")
        st.dataframe(
            [
                {
                    "序号": index,
                    "角色": trace.role,
                    "模型": trace.model,
                    "耗时(ms)": trace.elapsed_ms,
                    "用量": json.dumps(trace.usage, ensure_ascii=False) if trace.usage else "未提供",
                    "错误": trace.error or "",
                }
                for index, trace in enumerate(record.model_calls, 1)
            ]
        )


def render_record(record: RunRecord, *, saved_path: str | None, replay: bool) -> None:
    if replay:
        st.warning(
            f"历史回放：原模式={record.mode}，原开始时间={record.started_at.isoformat()}。"
            "以下内容来自保存的记录，不是本次推理。"
        )
    st.caption(
        f"案例：{record.input.title} | 模式：{record.mode} | 状态：{record.status} | "
        f"模型：{record.model} | 记录 {record.run_id}"
    )
    render_status(record)
    for error in record.errors:
        st.error(error)
    render_input(record.input)
    decision = record.final_decision
    if decision is not None:
        columns = st.columns(3)
        columns[0].metric("可自由支配预算", yuan(decision.budget_result.discretionary_cents))
        payable = decision.offer_result.payable_cents if decision.offer_result else None
        columns[1].metric("方案总付款", yuan(payable))
        columns[2].metric("建议", ACTION_LABELS.get(decision.action, decision.action))
    render_calculation(record)
    render_arguments(record)
    render_decision(record)
    render_traces(record)
    with st.expander("原始记录（JSON）"):
        st.json(record.model_dump(mode="json"))
        st.download_button(
            "下载本次记录",
            record.model_dump_json(indent=2),
            file_name=f"{record.run_id}.json",
            mime="application/json",
        )
    if saved_path and not replay:
        st.caption(f"已保存本地记录：{saved_path}")


def render_replay(config) -> None:
    st.subheader("历史回放")
    st.caption("读取 outputs/ 中保存的原始记录；回放不调用模型，也不代表当前推理。")
    files = sorted(
        config.output_dir.glob("*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not files:
        st.info("还没有本地记录：请先在「运行」页运行一次案例。")
        return
    chosen = st.selectbox(
        "选择本地记录",
        files,
        format_func=lambda path: (
            f"{path.name} · {datetime.fromtimestamp(path.stat().st_mtime, TZ):%Y-%m-%d %H:%M}"
        ),
        key="replay_file",
    )
    try:
        record = load_record(chosen)
    except (OSError, ValueError, ValidationError) as exc:
        st.error(f"无法读取该记录（{type(exc).__name__}）。")
        return
    st.subheader("回放结果")
    render_record(record, saved_path=str(chosen), replay=True)


def main() -> None:
    st.set_page_config(page_title="赛博节俭局 · 消费决策", page_icon="🛒", layout="wide")
    st.title("🛒 赛博节俭局")
    st.caption("消费决策 Agent · 五人协作开发骨架")
    page = st.radio("页面", ["运行", "历史回放"], horizontal=True, key="page")
    if page == "历史回放":
        render_replay(load_config())
        return
    mode = st.selectbox(
        "运行方式",
        ["demo", "real"],
        format_func=lambda item: "离线演示替身" if item == "demo" else "正式模块（B/C/D 已集成）",
        key="mode",
    )
    if mode == "real":
        config = load_config(REAL_CONFIG_PATH, mode="real")
        st.caption(
            f"单次模型请求上限 {config.request_timeout_seconds:g} 秒，"
            f"全流程上限 {config.workflow_timeout_seconds:g} 秒；商品与活动仍来自样例快照。"
        )
        st.warning("正式业务已集成 B/C/D；缺少本机模型密钥或接口失败时会显示 partial，不会切换到演示替身。")
    else:
        config = load_config(mode="demo")
        st.info("离线演示使用脚本角色与手工优惠样例。商品和活动来自样例快照，不是实时购物信息。")

    catalog = load_catalog_products(config.data_dir)
    rows = {row["id"]: row for row in catalog}
    if not rows:
        st.error("无法读取商品，暂时不能开始评估。")
        return

    product_ids = sorted(rows)

    def label_product(product_id: str) -> str:
        return product_label(rows[product_id])

    now = datetime.now(TZ).replace(second=0, microsecond=0)
    with st.form("purchase_input"):
        enable_cross = mode == "real" and st.checkbox(
            "一轮角色回应",
            help="欲望和理性角色各回应一条具体观点，再由裁判给出建议。",
            key="cross_response",
        )
        st.caption("金额以元填写。留空表示尚未提供，填 0 表示确认该项为零。")
        target = st.selectbox(
            "目标商品",
            product_ids,
            index=None,
            format_func=label_product,
            placeholder="请选择，例如演示球鞋",
            key="target",
        )
        cols = st.columns(3)
        fields = [
            ("cash_cents", "当前现金", "1200"),
            ("daily_essential_cents", "每日基本开支", "40"),
            ("fixed_expenses_cents", "剩余固定支出", "0"),
            ("reserve_cents", "预留金", "100"),
        ]
        inputs = {}
        for index, (field, label, example) in enumerate(fields):
            inputs[field] = cols[index % 3].text_input(
                f"{label}（元）",
                placeholder=f"例如 {example}",
                key=field,
            )
        days = cols[1].text_input(
            "距下次生活费天数",
            placeholder="例如 20",
            key="days",
        )
        shipping = cols[2].text_input(
            "运费（元）",
            placeholder="例如 0",
            key="shipping",
        )
        urgency = st.selectbox(
            "需求紧迫程度",
            ["low", "medium", "high"],
            index=1,
            format_func=lambda item: URGENCY_LABELS[item],
            key="urgency",
        )
        owned = st.text_area(
            "已有相似物品（逗号或换行分隔）",
            placeholder="例如 旧球鞋",
            key="owned",
        )
        addons = st.multiselect(
            "确实需要一并购买的凑单品（最多 8 个）",
            product_ids,
            format_func=label_product,
            max_selections=8,
            placeholder="选填，不含目标商品",
            key="addons",
        )
        when_date = st.date_input("评估日期", value=now.date(), key="date")
        when_time = st.time_input("评估时间", value=now.time(), key="time")
        reason = st.text_area(
            "购买理由", placeholder="例如 喜欢新配色，希望换一双球鞋", key="reason"
        )
        submitted = st.form_submit_button("运行并保存本地记录")

    if submitted:
        if target is None:
            st.error("请选择目标商品。")
            return
        if not reason.strip():
            st.error("请填写购买理由。")
            return
        if target in addons:
            st.error("凑单品不能与目标商品相同。")
            return
        if when_date is None or when_time is None:
            st.error("请填写评估日期和时间。")
            return
        try:
            case = CaseInput(
                case_id=f"manual_{uuid4().hex}",
                title=f"{rows[target].get('name', target)}购买评估",
                profile=UserProfile(
                    **{field: money_input(value) for field, value in inputs.items()},
                    days_remaining=days_input(days),
                    owned_similar_items=split_items(owned),
                ),
                request=PurchaseRequest(
                    target_product_id=target,
                    need_reason=reason.strip(),
                    urgency=urgency,
                    needed_addon_ids=addons,
                    shipping_cents=money_input(shipping),
                    as_of=datetime.combine(when_date, when_time, tzinfo=TZ),
                ),
            )
            if enable_cross:
                config = load_config(CROSS_CONFIG_PATH, mode="real")
            with st.spinner("正在运行…"):
                record = run_case(case, config)
                saved = save_record(record, config.output_dir)
            st.session_state["record"] = record
            st.session_state["saved"] = str(saved)
        except (AgentError, InvalidOperation, ValidationError, ValueError) as exc:
            if isinstance(exc, (AgentError, ValidationError)):
                st.error(f"运行失败（{type(exc).__name__}）：{exc}")
            else:
                st.error("请检查输入：金额最多两位小数且非负，天数为非负整数。")
            return

    record = st.session_state.get("record")
    if record is not None:
        st.subheader("本次结果" if submitted else "上次提交结果")
        render_record(record, saved_path=st.session_state.get("saved"), replay=False)


main()
