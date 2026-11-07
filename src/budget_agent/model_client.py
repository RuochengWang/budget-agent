"""A：学校 OpenAI 兼容文本接口；不依赖供应商 SDK，不记录认证头。

不发送 response_format/tools/temperature 等未确认支持的参数。
角色提示要求 JSON，Pydantic 校验失败最多重试一次；不自动切换付费模型。
"""

import json
from collections.abc import Callable
from time import monotonic
from typing import Any, Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from budget_agent.config import AppConfig
from budget_agent.errors import ModelError, ToolLimitReached
from budget_agent.schemas import ModelTrace

T = TypeVar("T", bound=BaseModel)


class ModelClient(Protocol):
    traces: list[ModelTrace]

    def generate_json(
        self, role: str, prompt: str, payload: dict[str, Any], response_type: type[T]
    ) -> T: ...


class FakeModel:
    """脚本化输出，只用于演示/测试，不代表模型效果。"""

    def __init__(self, responder: Callable[[str, dict], dict]):
        self.responder = responder
        self.traces: list[ModelTrace] = []

    def generate_json(self, role, prompt, payload, response_type):
        result = response_type.model_validate(self.responder(role, payload))
        self.traces.append(ModelTrace(role=role, model="fake/scripted", elapsed_ms=0))
        return result


class ChatModelClient:
    def __init__(self, config: AppConfig, *, transport: httpx.BaseTransport | None = None):
        self.config = config
        self.transport = transport
        self.traces: list[ModelTrace] = []
        self.deadline: float | None = None

    def _complete(self, messages: list[dict[str, str]]) -> dict:
        key = self.config.api_key.get_secret_value()
        if not key:
            raise ModelError("请在本机 .env 中填写 BUDGET_AGENT_API_KEY")
        timeout = self.config.request_timeout_seconds
        if self.deadline is not None:
            remaining = self.deadline - monotonic()
            if remaining <= 0:
                raise ToolLimitReached("模型调用前已达到工作流时间上限")
            timeout = min(timeout, remaining)
        try:
            with httpx.Client(
                timeout=timeout, transport=self.transport, follow_redirects=False
            ) as c:
                response = c.post(
                    f"{self.config.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={"model": self.config.model, "messages": messages},
                )
                response.raise_for_status()
                result = response.json()
                if not isinstance(result, dict):
                    raise ValueError
                return result
        except httpx.HTTPStatusError as exc:
            raise ModelError(f"模型服务返回 HTTP {exc.response.status_code}") from None
        except (httpx.HTTPError, ValueError):
            raise ModelError("模型连接失败、超时或响应格式异常；请检查地址与网络") from None

    def check_connection(self) -> str:
        """只做一次最小文本请求；由 CLI 显式触发，不在启动时自动调用。"""
        result = self._complete([{"role": "user", "content": "请只回复 OK"}])
        try:
            content = result["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError
        except (KeyError, IndexError, TypeError, ValueError):
            raise ModelError("模型响应没有可用的文本 content") from None
        return "模型接口已返回有效文本（一次请求）"

    def generate_json(self, role, prompt, payload, response_type):
        schema = json.dumps(response_type.model_json_schema(), ensure_ascii=False)
        messages = [
            {"role": "system", "content": f"{prompt}\n仅输出符合此 JSON Schema 的 JSON：{schema}"},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        for attempt in range(self.config.max_output_retries + 1):
            started = monotonic()
            trace = ModelTrace(role=role, model=self.config.model, elapsed_ms=0)
            self.traces.append(trace)
            try:
                data = self._complete(messages)
                # 只保存数值用量，不保存服务返回的任意扩展字段。
                usage = data.get("usage", {})
                if isinstance(usage, dict):
                    trace.usage = {k: v for k, v in usage.items() if type(v) is int}
                content = data["choices"][0]["message"]["content"]
                if not isinstance(content, str):
                    raise ValueError
                text = content.strip()
                if text.startswith("```json\n") and text.endswith("```"):
                    text = text[8:-3].strip()
                return response_type.model_validate_json(text)
            except (ValidationError, ValueError, KeyError, IndexError, TypeError):
                trace.error = "模型输出未通过结构化校验"
                if attempt == self.config.max_output_retries:
                    raise ModelError(trace.error) from None
                messages.append(
                    {"role": "user", "content": "输出格式无效，请严格按 Schema 重新输出 JSON。"}
                )
            except (ModelError, ToolLimitReached) as exc:
                trace.error = str(exc)
                raise
            finally:
                trace.elapsed_ms = round((monotonic() - started) * 1000)
        raise ModelError("结构化输出失败")
