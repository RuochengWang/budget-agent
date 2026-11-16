"""B：预算计算工具。

按接口契约 v0.1 实现预算公式与缺失字段处理。
金额单位为分，缺失数值用 None，不自动补零；负可支配预算如实保留。

契约要点（docs/common/contracts.md）：
    essential      = days_remaining * daily_essential_cents + fixed_expenses_cents
    discretionary  = cash_cents - essential - reserve_cents
    remaining_cash = cash_cents - payable_cents
    within_budget  = remaining_cash >= essential + reserve_cents

两次计算语义：
- payable_cents=None 时，只计算 essential/discretionary，
  remaining_cash 与 within_budget 均为 None。
- 传入最终付款额时，才计算 remaining_cash 与 within_budget。

关键行为：
- 任一必填预算字段缺失，列入 missing_fields，且依赖该字段的结果为 None。
- 零预留金、零剩余天数是合法输入；None 不是零。
- 不原地修改输入；不调用模型、不读 .env、不查商品。
"""

from budget_agent.schemas import BudgetResult, UserProfile


def _missing_fields(profile: UserProfile) -> list[str]:
    """收集缺失的必填预算字段。

    必填字段：cash_cents / days_remaining / daily_essential_cents /
    fixed_expenses_cents / reserve_cents。None 即缺失；
    明确给定的 0 是合法值，不算缺失。
    """
    required = (
        "cash_cents",
        "days_remaining",
        "daily_essential_cents",
        "fixed_expenses_cents",
        "reserve_cents",
    )
    return [name for name in required if getattr(profile, name) is None]


def calculate_budget(
    profile: UserProfile, payable_cents: int | None = None
) -> BudgetResult:
    """计算基本支出、可支配金额，并可按最终付款额复核。

    参数：
        profile: 用户预算输入（Pydantic 模型，金额已由公共模型校验为分）。
        payable_cents: 最终方案实际付款额（分）。为 None 时只计算
                       essential/discretionary，不判定预算是否通过。

    返回：
        BudgetResult；缺失字段导致无法可靠计算的结果为 None。
    """
    missing = _missing_fields(profile)

    # 仅当所有参与计算的字段都齐备时，才计算 essential 与 discretionary。
    essential_ready = all(
        name not in missing
        for name in (
            "days_remaining",
            "daily_essential_cents",
            "fixed_expenses_cents",
        )
    )
    discretionary_ready = essential_ready and all(
        name not in missing for name in ("cash_cents", "reserve_cents")
    )

    essential_total: int | None = None
    discretionary: int | None = None

    if essential_ready:
        essential_total = (
            profile.days_remaining * profile.daily_essential_cents
            + profile.fixed_expenses_cents
        )
    if discretionary_ready:
        discretionary = (
            profile.cash_cents - essential_total - profile.reserve_cents
        )

    # 未给付款额：remaining_cash 与 within_budget 必须是 None。
    remaining_cash: int | None = None
    within_budget: bool | None = None

    if payable_cents is not None:
        # 付款额已提供，但现金、基本支出或预留金缺失时仍无法判定。
        if (
            "cash_cents" in missing
            or essential_total is None
            or "reserve_cents" in missing
        ):
            remaining_cash = None
            within_budget = None
        else:
            remaining_cash = profile.cash_cents - payable_cents
            within_budget = remaining_cash >= (
                essential_total + profile.reserve_cents
            )

    return BudgetResult(
        essential_total_cents=essential_total,
        discretionary_cents=discretionary,
        remaining_cash_cents=remaining_cash,
        within_budget=within_budget,
        missing_fields=missing,
    )
