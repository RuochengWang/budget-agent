"""A：有界、串行、可注入的总控；E 的 UI/CLI/评测只调用 run_case。

正式模式不会回退到 demo。任一正式模块未完成即返回 partial 并保存已有轨迹。
超时为协作式检查；同步 Python 工具执行中无法强制中断，C 须保证有限穷举。
"""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from time import monotonic
from uuid import uuid4

from pydantic import AwareDatetime, Field

from budget_agent import CONTRACT_VERSION, __version__
from budget_agent.agents import cross_response, deal, desire, judge, rational
from budget_agent.agents.base import PROMPT_DIR
from budget_agent.config import AppConfig
from budget_agent.decision_policy import apply_decision_policy
from budget_agent.errors import AgentError, ModuleNotReady
from budget_agent.model_client import ChatModelClient, FakeModel, ModelClient
from budget_agent.schemas import (
    Argument,
    BudgetResult,
    CaseInput,
    Contract,
    DealResult,
    DecisionProposal,
    Evidence,
    Money,
    OfferResult,
    OptimizationInput,
    Product,
    PromotionRule,
    RoleContext,
    RunRecord,
    UserProfile,
)
from budget_agent.tools import budget, catalog, optimizer, promotions
from budget_agent.tools.registry import ToolRegistry


class BudgetArgs(Contract):
    profile: UserProfile
    payable_cents: Money | None = None


class ProductArgs(Contract):
    product_ids: list[str] = Field(min_length=1, max_length=9)


class SearchArgs(Contract):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)


class PromotionArgs(ProductArgs):
    as_of: AwareDatetime


class OptimizeArgs(Contract):
    request: OptimizationInput


@dataclass
class Services:
    tools: ToolRegistry
    model: ModelClient
    desire: Callable[[RoleContext, ModelClient], Argument]
    rational: Callable[[RoleContext, ModelClient], Argument]
    deal: Callable[[RoleContext, ModelClient, ToolRegistry], DealResult]
    judge: Callable[[RoleContext, ModelClient], DecisionProposal]
    cross_response: Callable[[RoleContext, ModelClient], list[Argument]]


def build_services(config: AppConfig) -> Services:
    tools = ToolRegistry(config.max_tool_calls, monotonic() + config.workflow_timeout_seconds)
    if config.mode == "demo":
        from budget_agent.demo import (
            DemoCatalog,
            calculate_demo_budget,
            run_demo_deal,
            run_demo_judge,
            run_demo_role,
            scripted_response,
        )

        data = DemoCatalog(config.data_dir)
        budget_fn = calculate_demo_budget
        search_fn, products_fn = data.search_products, data.get_products
        rules_fn, optimize_fn = data.get_promotion_rules, data.optimize_basket
        services = Services(
            tools,
            FakeModel(scripted_response),
            partial(run_demo_role, "desire"),
            partial(run_demo_role, "rational"),
            run_demo_deal,
            run_demo_judge,
            lambda context, model: [],
        )
    else:
        budget_fn = budget.calculate_budget
        search_fn = partial(catalog.search_products, data_dir=config.data_dir)
        products_fn = partial(catalog.get_products, data_dir=config.data_dir)
        rules_fn = partial(promotions.get_promotion_rules, data_dir=config.data_dir)
        optimize_fn = optimizer.optimize_basket
        client = ChatModelClient(config)
        client.deadline = tools.deadline
        services = Services(
            tools, client, desire.run, rational.run, deal.run, judge.run, cross_response.run
        )
    tools.register("calculate_budget", BudgetArgs, BudgetResult, budget_fn)
    tools.register("search_products", SearchArgs, list[Product], search_fn)
    tools.register("get_products", ProductArgs, list[Product], products_fn)
    tools.register("get_promotion_rules", PromotionArgs, list[PromotionRule], rules_fn)
    tools.register("optimize_basket", OptimizeArgs, OfferResult, optimize_fn)
    return services


def run_case(case: CaseInput, config: AppConfig, services: Services | None = None) -> RunRecord:
    """每次运行创建独立 services；测试可注入，禁止跨运行复用工具调用计数。"""
    services = services or build_services(config)
    record = RunRecord(
        run_id=uuid4().hex,
        contract_version=CONTRACT_VERSION,
        code_version=__version__,
        mode=config.mode,
        status="running",
        started_at=datetime.now(timezone.utc),
        input=case,
        config_snapshot=config.model_dump(mode="json"),
        model="fake/scripted" if config.mode == "demo" else config.model,
        prompt_hashes={
            p.stem: hashlib.sha256(p.read_bytes()).hexdigest() for p in PROMPT_DIR.glob("*.md")
        },
    )
    context = None
    try:
        tools = services.tools
        initial = tools.call("calculate_budget", {"profile": case.profile.model_dump()})
        evidence = [
            Evidence(
                id="input:request",
                kind="input",
                description="用户购买需求",
                facts=case.request.model_dump(mode="json"),
            ),
            Evidence(
                id="input:profile",
                kind="input",
                description="用户预算输入",
                facts=case.profile.model_dump(mode="json"),
            ),
            Evidence(
                id="budget:initial",
                kind="budget",
                description="购买前预算",
                facts=initial.model_dump(mode="json"),
                is_demo=config.mode == "demo",
            ),
        ]
        context = RoleContext(case=case, products=[], budget=initial, evidence=evidence)
        if initial.missing_fields:
            proposal = DecisionProposal(
                action="need_info",
                reason_summary="请补充预算必填信息",
                evidence_ids=["budget:initial"],
                next_steps=initial.missing_fields,
            )
        else:
            ids = [case.request.target_product_id, *case.request.needed_addon_ids]
            if len(case.request.needed_addon_ids) > config.max_addon_candidates:
                raise AgentError("凑单候选超过配置上限")
            context.products = tools.call("get_products", {"product_ids": ids})
            context.evidence.extend(
                [
                    Evidence(
                        id=f"product:{p.id}",
                        kind="product",
                        description=p.name,
                        facts=p.model_dump(mode="json"),
                        source_url=p.source_url,
                        is_demo=p.is_demo,
                    )
                    for p in context.products
                ]
            )
            for expected_role, node in [
                ("desire", services.desire),
                ("rational", services.rational),
            ]:
                tools.check_deadline()
                argument = Argument.model_validate(node(context, services.model))
                if argument.role != expected_role:
                    raise AgentError("角色节点返回了不匹配的 role")
                context.arguments.append(argument)
            tools.check_deadline()
            result = DealResult.model_validate(services.deal(context, services.model, tools))
            if result.argument.role != "deal":
                raise AgentError("优惠节点返回了不匹配的 role")
            context.offer = result.offer
            context.evidence.extend(result.evidence)
            context.arguments.append(result.argument)
            context.budget = tools.call(
                "calculate_budget",
                {
                    "profile": case.profile.model_dump(),
                    "payable_cents": result.offer.payable_cents,
                },
            )
            context.evidence.append(
                Evidence(
                    id="budget:final",
                    kind="budget",
                    description="最终付款预算",
                    facts=context.budget.model_dump(mode="json"),
                    is_demo=config.mode == "demo",
                )
            )
            if config.cross_response_enabled:
                tools.check_deadline()
                context.arguments.extend(
                    Argument.model_validate(a)
                    for a in services.cross_response(context, services.model)
                )
            tools.check_deadline()
            proposal = DecisionProposal.model_validate(services.judge(context, services.model))
        tools.check_deadline()
        record.proposed_decision = proposal
        record.final_decision, record.policy_violations = apply_decision_policy(proposal, context)
        record.status = (
            "needs_input" if record.final_decision.action == "need_info" else "completed"
        )
    except ModuleNotReady as exc:
        record.status = "partial"
        record.errors.append(str(exc))
    except AgentError as exc:
        record.status = "partial" if context is not None else "failed"
        record.errors.append(str(exc))
    except Exception as exc:
        record.status = "failed"
        record.errors.append(f"未预期错误（{type(exc).__name__}），请检查对应模块")
    finally:
        if context is not None:
            record.evidence = context.evidence
            record.arguments = context.arguments
        record.tool_calls = services.tools.traces
        record.model_calls = services.model.traces
        record.finished_at = datetime.now(timezone.utc)
    return record
