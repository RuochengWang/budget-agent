"""A：工具白名单、参数与返回值校验、调用上限及可回放轨迹。"""

from collections.abc import Callable
from time import monotonic
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, TypeAdapter, ValidationError

from budget_agent.errors import AgentError, ModuleNotReady, ToolLimitReached
from budget_agent.schemas import ToolTrace


class ToolRegistry:
    def __init__(self, max_calls: int, deadline: float):
        self.max_calls = max_calls
        self.deadline = deadline
        self.traces: list[ToolTrace] = []
        self._tools: dict[str, tuple[type[BaseModel], TypeAdapter, Callable]] = {}

    def register(self, name: str, arguments: type[BaseModel], result_type: Any, handler: Callable):
        if name in self._tools:
            raise ValueError(f"工具重复注册：{name}")
        self._tools[name] = (arguments, TypeAdapter(result_type), handler)

    def check_deadline(self):
        if monotonic() >= self.deadline:
            raise ToolLimitReached("工作流已达到时间上限")

    def call(self, name: str, arguments: dict[str, Any]) -> Any:
        """只执行预注册函数；不使用 eval，不允许传入代码或数据目录。"""
        self.check_deadline()
        if len(self.traces) >= self.max_calls:
            raise ToolLimitReached("工具调用次数已达到上限")
        trace = ToolTrace(id=f"tool:{uuid4().hex}", name=name, arguments=arguments)
        self.traces.append(trace)  # 无效参数与未知工具也计入上限。
        started = monotonic()
        try:
            if name not in self._tools:
                raise AgentError("请求的工具不在白名单中")
            schema, adapter, handler = self._tools[name]
            params = schema.model_validate(arguments)
            values = {field: getattr(params, field) for field in type(params).model_fields}
            result = adapter.validate_python(handler(**values))
            self.check_deadline()
            trace.result = adapter.dump_python(result, mode="json")
            return result
        except (ModuleNotReady, ToolLimitReached, AgentError) as exc:
            trace.error = str(exc)
            raise
        except ValidationError:
            trace.error = "工具参数或返回值未通过数据格式校验"
            raise AgentError(trace.error) from None
        except Exception as exc:
            trace.error = f"工具执行失败（{type(exc).__name__}），请在本机调试对应模块"
            raise AgentError(trace.error) from None
        finally:
            trace.elapsed_ms = round((monotonic() - started) * 1000)
