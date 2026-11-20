"""E：客观指标。只依赖公共 RunRecord 与独立人工标签，不依赖 B/C/D 正式模块。

设计原则（对齐 docs/E/README.md 与 docs/common/contracts.md）：
- 未运行的样本（有标签、无记录）计入分母，但绝不记为正确；
- 缺标签的记录单列 unmatched_records，不参与评分；
- 有效样本为 0 时 rate 返回 None，绝不返回 0 或 100%；
- 金额/布尔比较区分 None 与 0，缺字段不能当零；
- 只报告 tokens 与耗时，不换算费用；
- labels 的 reference_action 不作为评分依据（"买不买"不是唯一真值）。
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from budget_agent.schemas import RunRecord

REVIEWER_IDS = frozenset("ABCDE")

BUDGET_FIELDS = (
    "essential_total_cents",
    "discretionary_cents",
    "remaining_cash_cents",
    "within_budget",
)
BUDGET_KEYS = (*BUDGET_FIELDS, "missing_fields")
OFFER_KEYS = (
    "feasible",
    "optimal_payable_cents",
    "optimal_basket_ids",
    "optimal_rule_ids",
    "baseline_payable_cents",
)


def _metric(correct: int, valid: int, total: int) -> dict[str, Any]:
    """每个指标自带分母 total、有效样本 valid 与未运行样本数。"""
    return {
        "correct": correct,
        "valid": valid,
        "total": total,
        "not_run": total - valid,
        "rate": None if valid == 0 else correct / total,
    }


def _index(labels: list[dict]) -> tuple[dict[str, dict], list[str]]:
    index: dict[str, dict] = {}
    duplicates: list[str] = []
    for label in labels:
        case_id = label.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            continue
        if case_id in index:
            duplicates.append(case_id)
        index[case_id] = label
    return index, duplicates


def valid_reviewers(reviewers: object) -> bool:
    return (
        isinstance(reviewers, list)
        and len(reviewers) >= 2
        and all(isinstance(r, str) and r in REVIEWER_IDS for r in reviewers)
        and len(set(reviewers)) == len(reviewers)
    )


def valid_review_date(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def validate_labels(labels: list[dict], *, require_reviewed: bool = True) -> list[str]:
    """返回问题列表；由运行器决定是否拒绝出成绩。不抛异常、不改输入。"""
    problems: list[str] = []
    index, duplicates = _index(labels)
    for case_id in duplicates:
        problems.append(f"重复标签：{case_id}")
    for case_id, label in index.items():
        budget = label.get("budget")
        if not isinstance(budget, dict):
            problems.append(f"{case_id}: budget 缺失或格式错误")
        else:
            for key in BUDGET_KEYS:
                if key not in budget:
                    problems.append(f"{case_id}: budget.{key} 缺失")
        offer = label.get("offer")
        if offer is not None:
            if not isinstance(offer, dict):
                problems.append(f"{case_id}: offer 格式错误")
            else:
                for key in OFFER_KEYS:
                    if key not in offer:
                        problems.append(f"{case_id}: offer.{key} 缺失")
        if require_reviewed:
            if label.get("review_status") != "reviewed":
                problems.append(f"{case_id}: 标签尚未复核（review_status != reviewed）")
            if not valid_reviewers(label.get("reviewers")):
                problems.append(f"{case_id}: 缺少复核人或复核人不是至少两个不同的 A—E 标识")
            if not valid_review_date(label.get("reviewed_at")):
                problems.append(f"{case_id}: 缺少复核日期或日期不是 YYYY-MM-DD")
    return problems


def _budget_matches(record: RunRecord, label: dict) -> bool:
    budget = label.get("budget")
    decision = record.final_decision
    if not isinstance(budget, dict) or decision is None:
        return False
    result = decision.budget_result
    values = {field: getattr(result, field) for field in BUDGET_FIELDS}
    for key in BUDGET_FIELDS:
        if values[key] != budget.get(key):
            return False
    return sorted(result.missing_fields) == sorted(budget.get("missing_fields") or [])


def _evidence_ids(record: RunRecord) -> set[str]:
    return {item.id for item in record.evidence}


def _constraint_violations(record: RunRecord, case_id: str) -> list[str]:
    """基础程序约束的独立复核；不验证论点语义支持程度。"""
    found: list[str] = []
    decision = record.final_decision
    if decision is None:
        return found
    budget = decision.budget_result
    offer = decision.offer_result
    if decision.action == "buy":
        if budget.within_budget is not True:
            found.append(f"{case_id}: 预算未明确通过却建议购买")
        # 独立检查购买前提；不依赖 D 的 policy 已经替被评系统兜底。
        if (
            offer is None
            or not offer.verified
            or offer.verification_method != "solver"
            or offer.unknowns
            or any(value is None for value in (
                offer.subtotal_cents, offer.discount_cents, offer.shipping_cents,
                offer.payable_cents, record.input.request.shipping_cents,
            ))
        ):
            found.append(f"{case_id}: 方案或付款明细尚未确认却建议购买")
    if budget.missing_fields and decision.action != "need_info":
        found.append(f"{case_id}: 存在缺失字段却未要求补充信息")
    known = _evidence_ids(record)
    dangling = [eid for eid in decision.evidence_ids if eid not in known]
    if dangling:
        found.append(f"{case_id}: 引用了不存在的证据 {dangling}")
    if offer is not None and all(
        value is not None
        for value in (offer.subtotal_cents, offer.discount_cents, offer.shipping_cents,
                      offer.payable_cents)
    ):
        if offer.subtotal_cents - offer.discount_cents + offer.shipping_cents != offer.payable_cents:
            found.append(f"{case_id}: 优惠方案金额算术不一致")
    return found


def _usage(records: list[RunRecord]) -> dict[str, Any]:
    """缺失字段显示 None（展示层写"未提供"），不推算费用。"""
    token_keys = ("prompt_tokens", "completion_tokens", "total_tokens")
    sums: dict[str, int] = {}
    missing: list[str] = []
    elapsed = 0.0
    for record in records:
        if record.finished_at is not None:
            elapsed += (record.finished_at - record.started_at).total_seconds()
        for trace in record.model_calls:
            for key in token_keys:
                value = trace.usage.get(key)
                if isinstance(value, int) and not isinstance(value, bool):
                    sums[key] = sums.get(key, 0) + value
                else:
                    missing.append(key)
    return {
        "records": len(records),
        "model_calls": sum(len(record.model_calls) for record in records),
        "tool_calls": sum(len(record.tool_calls) for record in records),
        "elapsed_seconds": round(elapsed, 3),
        # 只有所有请求都提供某字段时才有完整合计；未知值不能按零计入。
        "tokens": {key: None if key in missing else sums.get(key) for key in token_keys},
        "missing_usage_fields": sorted(set(missing)),
        "fee": None,
        "fee_note": "未换算费用：没有价格依据，只报告 tokens 与耗时。",
    }


def compute_metrics(records: list[RunRecord], labels: list[dict]) -> dict[str, Any]:
    """与独立人工标签比较，返回带分母、有效样本数与未运行样本的客观指标。

    只做计算，不检查标签是否复核、不检查记录是否正式；这两项由运行器把关。
    """
    label_index, duplicate_labels = _index(labels)
    record_index = {record.input.case_id: record for record in records}
    total = len(label_index)

    not_run = sorted(set(label_index) - set(record_index))
    unmatched_records = sorted(set(record_index) - set(label_index))
    matched = sorted(set(label_index) & set(record_index))

    keys = (
        "budget_correct", "offer_optimal_amount", "offer_basket",
        "offer_feasible", "evidence_valid", "missing_info_detection",
    )
    # applicable = 该指标理论适用的标签数（分母）；correct = 匹配且判对；valid = 匹配且可评。
    applicable: dict[str, int] = {key: 0 for key in keys}
    counters: dict[str, list[int]] = {key: [0, 0] for key in keys}  # [correct, valid]
    violations: list[str] = []
    status = Counter(record.status for record in records)

    for case_id in sorted(label_index):
        label = label_index[case_id]
        budget = label.get("budget")
        offer_label = label.get("offer")
        record = record_index.get(case_id)
        decision = record.final_decision if record is not None else None

        # 先按标签本身统计每个指标的分母（未运行的样本也计入分母，但不能算对）。
        if isinstance(budget, dict):
            applicable["budget_correct"] += 1
        applicable["evidence_valid"] += 1
        should_need_info = bool((budget or {}).get("missing_fields")) or (
            isinstance(offer_label, dict)
            and (offer_label.get("feasible") is not True
                 or offer_label.get("optimal_payable_cents") is None)
        )
        if should_need_info:
            applicable["missing_info_detection"] += 1
        if isinstance(offer_label, dict):
            for key in ("offer_optimal_amount", "offer_basket", "offer_feasible"):
                applicable[key] += 1

        if decision is None:
            continue  # 未运行或无最终建议：只进分母，不计入有效样本。
        if record is not None:
            violations.extend(_constraint_violations(record, case_id))

        if isinstance(budget, dict):
            counters["budget_correct"][1] += 1
            if _budget_matches(record, label):
                counters["budget_correct"][0] += 1

        counters["evidence_valid"][1] += 1
        if all(eid in _evidence_ids(record) for eid in decision.evidence_ids):
            counters["evidence_valid"][0] += 1

        if should_need_info:
            counters["missing_info_detection"][1] += 1
            if decision.action == "need_info":
                counters["missing_info_detection"][0] += 1

        if not isinstance(offer_label, dict):
            continue
        offer = decision.offer_result

        # 最优总付款：标签值为 None 表示"应付额无法确认"，两边必须一致。
        counters["offer_optimal_amount"][1] += 1
        expected = offer_label.get("optimal_payable_cents")
        actual = offer.payable_cents if offer is not None else None
        if actual == expected:
            counters["offer_optimal_amount"][0] += 1

        # 最优购物篮与规则：按 ID 排序后比较，避免顺序差异误判。
        # 方案未确认（标签应付额为 None，例如运费未知）时购物篮不是可判定项：
        # 只要求被评系统如实给出未确认方案，不比较占位用的 basket_ids。
        counters["offer_basket"][1] += 1
        if offer_label.get("optimal_payable_cents") is None:
            if offer is None or offer.payable_cents is None:
                counters["offer_basket"][0] += 1
        else:
            actual_basket = sorted(offer.basket_ids) if offer is not None else []
            actual_rules = sorted(offer.rule_ids) if offer is not None else []
            if (actual_basket == sorted(offer_label.get("optimal_basket_ids") or [])
                    and actual_rules == sorted(offer_label.get("optimal_rule_ids") or [])):
                counters["offer_basket"][0] += 1

        # 优惠可行性：feasible=True 期望已验证的确认方案；否则期望如实未确认。
        counters["offer_feasible"][1] += 1
        feasible = offer_label.get("feasible")
        if feasible is True:
            ok = (offer is not None and offer.payable_cents is not None
                  and offer.verified and offer.verification_method == "solver")
        else:
            ok = (offer is None or offer.payable_cents is None)
            if offer is not None:
                ok = ok and bool(offer.unknowns)
        if ok:
            counters["offer_feasible"][0] += 1

    result_metrics = {
        key: _metric(counters[key][0], counters[key][1], applicable[key])
        for key in keys
    }
    result_metrics["constraint_violations"] = {
        "count": len(violations),
        "total": total,
        "cases": violations,
    }
    return {
        "total_cases": total,
        "matched": matched,
        "not_run": not_run,
        "unmatched_records": unmatched_records,
        "duplicate_labels": duplicate_labels,
        "metrics": result_metrics,
        "usage": _usage(records),
        "status_distribution": dict(sorted(status.items())),
    }
