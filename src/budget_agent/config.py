"""A：跨平台路径、TOML 配置和本机 .env；配置快照不含密钥。"""

import os
import tomllib
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from dotenv import load_dotenv
from pydantic import Field, SecretStr, field_validator

from budget_agent.schemas import Contract

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class AppConfig(Contract):
    mode: Literal["demo", "real"] = "demo"
    model: str = "qwen3.8-chat"
    base_url: str = "https://api.llm.ustc.edu.cn/v1"
    api_key: SecretStr = Field(default_factory=lambda: SecretStr(""), exclude=True)
    request_timeout_seconds: float = Field(default=45, gt=0)
    workflow_timeout_seconds: float = Field(default=180, gt=0)
    max_tool_calls: int = Field(default=6, ge=1, le=20)
    max_output_retries: int = Field(default=1, ge=0, le=1)
    max_addon_candidates: int = Field(default=8, ge=0, le=8)
    cross_response_enabled: bool = False
    data_dir: Path = PROJECT_ROOT / "data"
    output_dir: Path = PROJECT_ROOT / "outputs"

    @field_validator("base_url")
    @classmethod
    def valid_base_url(cls, value: str) -> str:
        url = urlsplit(value)
        if url.scheme != "https" or not url.hostname or url.username or url.query or url.fragment:
            raise ValueError("Base URL 必须为不含账号、查询参数的 HTTPS 地址")
        return value.rstrip("/")


def load_config(path: Path | None = None, *, mode: str | None = None) -> AppConfig:
    path = (path or PROJECT_ROOT / "configs" / "default.toml").resolve()
    root = path.parent.parent
    load_dotenv(root / ".env", override=False)
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    for field, env in [("base_url", "BUDGET_AGENT_BASE_URL"), ("model", "BUDGET_AGENT_MODEL")]:
        if os.getenv(env):
            data[field] = os.environ[env]
    data["api_key"] = os.getenv("BUDGET_AGENT_API_KEY", "")
    if mode is not None:
        data["mode"] = mode
    for field in ("data_dir", "output_dir"):
        data[field] = (root / data[field]).resolve()
    return AppConfig.model_validate(data)
