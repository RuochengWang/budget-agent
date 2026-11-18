"""离线端到端联调检查（不调用真实模型/网络，不写 outputs）。

用 FakeModel 占位响应验证 B/C/D 正式模块与 E 评测框架的衔接：
- real 模式能走通预算→商品→规则→求解→复核→裁判→最终校验；
- C 求解器返回 verification_method=solver；
- E 的严格标签校验拒绝一份合成草案（不运行真实评测）；
- 缺字段/运费未知时如实 needs_input，不伪造付款额。

注意：占位响应不代表模型效果，任何"建议"都不能用于报告。
"""

from __future__ import annotations

from budget_agent.config import load_config
from budget_agent.main import load_cases
from budget_agent.model_client import FakeModel
from budget_agent.schemas import Argument, DecisionProposal
from budget_agent.workflow import build_services, run_case
from evaluation.metrics import validate_labels


def _responder(role: str, payload: dict) -> dict:
    if role == "judge":
        budget = payload.get("budget") or {}
        offer = payload.get("offer") or {}
        if offer.get("payable_cents") is None or budget.get("missing_fields"):
            action = "need_info"
        else:
            action = "buy" if budget.get("within_budget") else "wait"
        return DecisionProposal(
            action=action,
            reason_summary="离线联调占位，不代表模型效果",
            evidence_ids=["budget:final", "offer:chosen"] if action == "buy" else ["input:request"],
            next_steps=[],
        ).model_dump()
    return Argument(
        role=role,
        stance="neutral",
        claims=["离线联调占位观点"],
        evidence_ids=["input:request"],
    ).model_dump()


def run_probe() -> dict:
    config = load_config(mode="real")
    cases = {c.case_id: c for c in load_cases(config.data_dir / "cases" / "dev.jsonl")}
    out: dict = {}
    for cid in ("sneakers_wait", "tissue_buy", "missing_profile", "unknown_shipping"):
        services = build_services(config)
        services.model = FakeModel(_responder)
        record = run_case(cases[cid], config, services)
        offer = record.final_decision.offer_result if record.final_decision else None
        out[cid] = {
            "status": record.status,
            "action": record.final_decision.action if record.final_decision else None,
            "payable": offer.payable_cents if offer else None,
            "verification": offer.verification_method if offer else None,
            "tool_calls": len(record.tool_calls),
            "errors": record.errors,
        }
    # 使用合成草案验证评测所共用的纯校验函数；即使项目标签已冻结，
    # 这里也从不调用真实评测运行器或读取标签的数据内容。
    draft = {
        "case_id": "probe_draft", "review_status": "draft",
        "reviewers": [], "reviewed_at": None,
        "budget": {
            "essential_total_cents": None, "discretionary_cents": None,
            "remaining_cash_cents": None, "within_budget": None,
            "missing_fields": ["reserve_cents"],
        },
        "offer": None,
    }
    out["label_guard"] = {
        "valid_draft": not validate_labels([draft], require_reviewed=False),
        "rejected_in_strict_mode": bool(validate_labels([draft], require_reviewed=True)),
    }
    return out


def main() -> int:
    result = run_probe()
    for key, value in result.items():
        print(f"{key}: {value}")
    ok = (
        result["sneakers_wait"]["status"] == "completed"
        and result["sneakers_wait"]["verification"] == "solver"
        and result["sneakers_wait"]["tool_calls"] == 5
        and result["tissue_buy"]["status"] == "completed"
        and result["tissue_buy"]["action"] == "buy"
        and result["missing_profile"]["payable"] is None
        and result["unknown_shipping"]["payable"] is None
        and result["label_guard"] == {"valid_draft": True, "rejected_in_strict_mode": True}
    )
    print("联调结论：", "OK（仅接口衔接，非模型效果）" if ok else "异常，需检查")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
