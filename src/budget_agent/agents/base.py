"""A：角色调用辅助。正式角色由 B/D 编写，不在此隐藏业务判断。"""

from pathlib import Path

from budget_agent.model_client import ModelClient, T
from budget_agent.schemas import RoleContext

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"


def call_role(role: str, context: RoleContext, model: ModelClient, result_type: type[T]) -> T:
    """读取版本化提示词，以统一格式交给模型；上下文不含密钥。"""
    if role not in {"desire", "rational", "deal", "judge"}:
        raise ValueError("未知角色")
    prompt = (PROMPT_DIR / f"{role}.md").read_text(encoding="utf-8")
    return model.generate_json(role, prompt, context.model_dump(mode="json"), result_type)
