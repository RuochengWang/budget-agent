"""A 维护的协作契约。字段改动先同步；金额单位一律为分。

缺失数值使用 None；不得用 0 代替。Money 用 strict=True 拒绝浮点数和 bool。
时间使用带时区的 ISO 8601；所有模块共享这些对象，不自建同名字典协议。
"""

from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Money = Annotated[int, Field(strict=True, ge=0)]
SignedMoney = Annotated[int, Field(strict=True)]
Action = Literal["buy", "wait", "skip", "need_info"]
Role = Literal["desire", "rational", "deal", "judge"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UserProfile(Contract):
    cash_cents: Money | None = None
    days_remaining: Annotated[int, Field(strict=True, ge=0)] | None = None
    daily_essential_cents: Money | None = None
    fixed_expenses_cents: Money | None = None
    reserve_cents: Money | None = None
    owned_similar_items: list[str] = Field(default_factory=list)


class PurchaseRequest(Contract):
    target_product_id: str = Field(min_length=1)
    need_reason: str = Field(min_length=1)
    urgency: Literal["low", "medium", "high"] = "medium"
    needed_addon_ids: list[str] = Field(default_factory=list, max_length=8)
    shipping_cents: Money | None = None
    as_of: AwareDatetime

    @model_validator(mode="after")
    def distinct_addons(self):
        if len(set(self.needed_addon_ids)) != len(self.needed_addon_ids):
            raise ValueError("凑单候选不能重复")
        if self.target_product_id in self.needed_addon_ids:
            raise ValueError("目标商品不能同时作为凑单候选")
        return self


class CaseInput(Contract):
    case_id: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    title: str
    profile: UserProfile
    request: PurchaseRequest


class Product(Contract):
    id: str
    name: str
    price_cents: Money
    merchant: str
    source_url: str | None = None
    observed_at: AwareDatetime
    is_demo: bool


class PromotionRule(Contract):
    id: str
    kind: Literal["reduction", "coupon"]
    merchant: str
    eligible_product_ids: list[str]
    threshold_cents: Money
    discount_cents: Money
    stackable: bool
    threshold_basis: Literal["original_eligible", "after_reduction_eligible"]
    valid_from: AwareDatetime
    valid_to: AwareDatetime
    source_url: str | None = None
    is_demo: bool

    @model_validator(mode="after")
    def valid_interval(self):
        if self.valid_to <= self.valid_from:
            raise ValueError("优惠结束时间必须晚于开始时间")
        if self.kind == "reduction" and self.threshold_basis != "original_eligible":
            raise ValueError("满减门槛第一版只按参与商品原价计算")
        return self


class BudgetResult(Contract):
    essential_total_cents: Money | None = None
    discretionary_cents: SignedMoney | None = None
    remaining_cash_cents: SignedMoney | None = None
    within_budget: bool | None = None
    missing_fields: list[str] = Field(default_factory=list)


class OptimizationInput(Contract):
    """C 的求解器只在已确认需要的候选里搜索；不能隐式加载全局数据。"""

    target_product_id: str
    candidate_ids: list[str] = Field(max_length=8)
    products: list[Product]
    rules: list[PromotionRule]
    shipping_cents: Money | None
    as_of: AwareDatetime


class OfferResult(Contract):
    basket_ids: list[str]
    subtotal_cents: Money | None = None
    discount_cents: Money | None = None
    shipping_cents: Money | None = None
    payable_cents: Money | None = None
    baseline_payable_cents: Money | None = None
    rule_ids: list[str] = Field(default_factory=list)
    verified: bool = False
    verification_method: Literal["unverified", "demo_fixture", "solver"] = "unverified"
    is_demo: bool
    unknowns: list[str] = Field(default_factory=list)
    excluded_reasons: list[str] = Field(default_factory=list)


class Evidence(Contract):
    id: str
    kind: Literal["input", "budget", "product", "promotion", "offer"]
    description: str
    facts: dict[str, Any] = Field(default_factory=dict)
    source_url: str | None = None
    is_demo: bool = False


class Argument(Contract):
    role: Role
    stance: Literal["support", "oppose", "neutral"]
    claims: list[str]
    evidence_ids: list[str]
    unknowns: list[str] = Field(default_factory=list)


class DecisionProposal(Contract):
    action: Action
    reason_summary: str
    counterargument: str = ""
    evidence_ids: list[str]
    next_steps: list[str]


class Decision(DecisionProposal):
    budget_result: BudgetResult
    offer_result: OfferResult | None


class RoleContext(Contract):
    case: CaseInput
    products: list[Product]
    budget: BudgetResult
    offer: OfferResult | None = None
    arguments: list[Argument] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


class DealResult(Contract):
    argument: Argument
    offer: OfferResult
    evidence: list[Evidence]


class ToolTrace(Contract):
    id: str
    name: str
    arguments: dict[str, Any]
    result: Any = None
    error: str | None = None
    elapsed_ms: int = 0


class ModelTrace(Contract):
    role: str
    model: str
    elapsed_ms: int
    usage: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class RunRecord(Contract):
    run_id: str
    contract_version: str
    code_version: str
    mode: Literal["demo", "real"]
    status: Literal["running", "completed", "needs_input", "partial", "failed"]
    started_at: AwareDatetime
    finished_at: AwareDatetime | None = None
    input: CaseInput
    config_snapshot: dict[str, Any]
    prompt_hashes: dict[str, str]
    model: str
    tool_calls: list[ToolTrace] = Field(default_factory=list)
    model_calls: list[ModelTrace] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    arguments: list[Argument] = Field(default_factory=list)
    proposed_decision: DecisionProposal | None = None
    final_decision: Decision | None = None
    policy_violations: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
