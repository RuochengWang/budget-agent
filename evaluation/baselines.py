"""E：基线契约与运行入口。不得用演示替身冒充任何基线。

分工边界：
- M / M_no_cross 只复用 A 的 workflow.run_case()，E 不重写流程；现在就能接线，
  正式业务未实现时返回 partial，由运行器拒绝当成成绩。
- B0 / B1 / B2 需要替换 Services 中的角色或工具组合，涉及 A 的注入点与 B/C/D
  的正式模块。这里提供 register_baseline() 注册钩子与明确的未实现错误，
  不伪造 "规则系统" 输出。A 确认注入方式后，由负责人注册实现即可，无需改本文件结构。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from budget_agent.config import AppConfig, load_config
from budget_agent.errors import ModuleNotReady
from budget_agent.schemas import CaseInput, RunRecord
from budget_agent.workflow import run_case

BASELINES = ("B0", "B1", "B2", "M", "M_no_cross")

BASELINE_NOTES: dict[str, str] = {
    "B0": "纯规则：不调用模型，但仍须使用 B 的正式预算与 C 的正式求解器；需要 A 提供无角色 Services。",
    "B1": "单模型：一次文本/JSON 模型调用直接给建议，不走四角色与工具循环；需要 A 确认提示词与注入点。",
    "B2": "单 Agent+工具：一个模型节点配合白名单工具，不走四角色分工；需要 A/D 确认角色组合。",
    "M": "完整系统：直接调用 workflow.run_case()，使用配置中的全部正式模块。",
    "M_no_cross": "消融：与 M 同模型/快照/工具额度，仅强制关闭 cross_response_enabled。",
}

BaselineFn = Callable[[CaseInput, AppConfig], RunRecord]
_IMPLS: dict[str, BaselineFn] = {}


def register_baseline(name: str, fn: BaselineFn) -> None:
    """A/B/C/D 实现对应基线后注册；重复注册需显式注销，避免悄悄覆盖口径。"""
    if name not in BASELINES:
        raise ValueError(f"未知基线：{name}")
    if name in _IMPLS:
        raise ValueError(f"基线 {name} 已注册；请先确认口径再覆盖")
    _IMPLS[name] = fn


def unregister_baseline(name: str) -> None:
    _IMPLS.pop(name, None)


def available_baselines() -> tuple[str, ...]:
    """返回当前可运行的基线名；用于运行前检查，不产生任何结果。"""
    return tuple(name for name in BASELINES if name in _IMPLS)


def baseline_plan(name: str) -> dict[str, Any]:
    """描述基线的口径与所需依赖，供 docs/E/report.md 与展示脚本引用。"""
    if name not in BASELINES:
        raise ValueError(f"未知基线：{name}")
    return {
        "name": name,
        "note": BASELINE_NOTES[name],
        "registered": name in _IMPLS,
        "uses_model": name != "B0",
        "cross_response": "forced_off" if name == "M_no_cross" else "from_config",
    }


def _run_full_system(case: CaseInput, config: AppConfig) -> RunRecord:
    if config.mode != "real":
        raise ModuleNotReady("正式基线只允许 real 模式；拒绝 demo 替身")
    return run_case(case, config)


def _run_no_cross(case: CaseInput, config: AppConfig) -> RunRecord:
    if config.mode != "real":
        raise ModuleNotReady("正式基线只允许 real 模式；拒绝 demo 替身")
    return run_case(case, config.model_copy(update={"cross_response_enabled": False}))


# M / M_no_cross 只调用 A 的统一入口，不依赖 B/C/D 是否已实现：
# 未实现时如实返回 partial，由 evaluation.run 拒绝写入成绩。
register_baseline("M", _run_full_system)
register_baseline("M_no_cross", _run_no_cross)


def run_baseline(name: str, case: CaseInput, *, config: AppConfig | None = None) -> RunRecord:
    """运行单个基线。config 由运行器统一注入，保证同模型/快照/工具额度。"""
    if name not in BASELINES:
        raise ValueError(f"未知基线：{name}")
    impl = _IMPLS.get(name)
    if impl is None:
        raise ModuleNotReady(
            f"TODO(E): {name} 基线尚未实现，不能产生实验结果。"
            f"口径：{BASELINE_NOTES[name]} 实现后用 register_baseline() 注册。"
        )
    cfg = config if config is not None else load_config(mode="real")
    if cfg.mode != "real":
        raise ModuleNotReady("正式评测只允许 real 模式；拒绝 demo 替身")
    return impl(case, cfg)
