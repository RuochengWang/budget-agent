import json

import httpx
import pytest
from pydantic import SecretStr

from budget_agent.errors import ModelError
from budget_agent.main import main
from budget_agent.model_client import ChatModelClient
from budget_agent.schemas import DecisionProposal


def test_compatible_path_and_single_retry(config):
    requests = []
    output = {"action": "wait", "reason_summary": "预算不足", "evidence_ids": [], "next_steps": []}

    def handler(request):
        requests.append(request)
        assert request.url.path == "/v1/chat/completions"
        assert json.loads(request.content)["model"] == "qwen3.8-chat"
        text = "invalid" if len(requests) == 1 else json.dumps(output)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": text}}],
                "usage": {"total_tokens": 15, "provider_extra": "ignored"},
            },
        )

    cfg = config.model_copy(update={"api_key": SecretStr("unit-test-credential")})
    client = ChatModelClient(cfg, transport=httpx.MockTransport(handler))
    result = client.generate_json("judge", "test", {}, DecisionProposal)
    assert result.action == "wait"
    assert len(requests) == 2
    assert client.traces[0].error
    assert client.traces[1].usage == {"total_tokens": 15}
    assert "unit-test-credential" not in str(cfg.model_dump())


def test_http_error_does_not_echo_response_body(config):
    client = ChatModelClient(
        config.model_copy(update={"api_key": SecretStr("unit-test-credential")}),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(401, text="sensitive-server-text")
        ),
    )
    with pytest.raises(ModelError, match="HTTP 401") as exc:
        client.check_connection()
    assert "sensitive" not in str(exc.value)


def test_format_retry_stops_at_two_requests(config):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "invalid"}}]})

    client = ChatModelClient(
        config.model_copy(update={"api_key": SecretStr("unit-test-credential")}),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ModelError, match="结构化"):
        client.generate_json("judge", "test", {}, DecisionProposal)
    assert len(requests) == 2


@pytest.mark.parametrize(
    "usage,expected_usage",
    [
        (
            {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "输入 tokens=10，输出 tokens=5，总 tokens=15",
        ),
        (None, "输入 tokens=未提供，输出 tokens=未提供，总 tokens=未提供"),
    ],
)
def test_json_cli_uses_structured_path_without_extra_connection_request(
    config, monkeypatch, capsys, usage, expected_usage
):
    requests = []
    output = {"action": "wait", "reason_summary": "格式检查", "evidence_ids": [], "next_steps": []}

    def handler(request):
        requests.append(request)
        messages = json.loads(request.content)["messages"]
        assert "JSON Schema" in messages[0]["content"]
        response = {"choices": [{"message": {"content": json.dumps(output)}}]}
        if usage is not None:
            response["usage"] = usage
        return httpx.Response(200, json=response)

    client = ChatModelClient(
        config.model_copy(update={"api_key": SecretStr("unit-test-credential")}),
        transport=httpx.MockTransport(handler),
    )
    monkeypatch.setattr("budget_agent.main.ChatModelClient", lambda config: client)
    assert main(["check-model", "--json"]) == 0
    assert len(requests) == 1
    captured = capsys.readouterr().out
    assert "结构化输出检查通过（1 次请求）" in captured
    assert expected_usage in captured


def test_timeout_is_reported_once_and_retains_trace(config):
    requests = []

    # 第一步：让模拟服务立即报告读取超时，不等待、不访问学校服务。
    def handler(request):
        requests.append(request)
        raise httpx.ReadTimeout("simulated-private-timeout-detail", request=request)

    client = ChatModelClient(
        config.model_copy(
            update={"api_key": SecretStr("unit-test-credential"), "max_output_retries": 1}
        ),
        transport=httpx.MockTransport(handler),
    )

    # 第二步：调用生产适配层，要求它返回统一的模型错误。
    with pytest.raises(ModelError, match="超时") as exc:
        client.generate_json("judge", "test", {}, DecisionProposal)

    # 第三步：连接错误只请求一次，且错误有记录、底层详情不向用户显示。
    assert len(requests) == 1
    assert len(client.traces) == 1
    assert client.traces[0].role == "judge"
    assert client.traces[0].error == str(exc.value)
    assert "simulated-private-timeout-detail" not in str(exc.value)
