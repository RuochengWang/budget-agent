from time import monotonic

import pytest

from budget_agent.errors import AgentError, ToolLimitReached
from budget_agent.schemas import Contract, Money
from budget_agent.tools.registry import ToolRegistry


class Args(Contract):
    value: Money


def test_unknown_name_is_not_executed():
    tools = ToolRegistry(1, monotonic() + 20)
    with pytest.raises(AgentError, match="白名单"):
        tools.call("arbitrary_code", {})
    assert tools.traces[0].error
    with pytest.raises(ToolLimitReached):
        tools.call("arbitrary_code", {})


def test_invalid_arguments_never_reach_handler():
    reached = []
    tools = ToolRegistry(2, monotonic() + 20)
    tools.register("test", Args, int, lambda value: reached.append(value) or value)
    with pytest.raises(AgentError, match="校验"):
        tools.call("test", {"value": 2.5})
    assert not reached
    assert tools.call("test", {"value": 250}) == 250


def test_expired_deadline_prevents_execution():
    tools = ToolRegistry(6, monotonic() - 1)
    with pytest.raises(ToolLimitReached):
        tools.call("test", {})
