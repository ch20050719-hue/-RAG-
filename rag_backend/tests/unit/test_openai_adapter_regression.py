import asyncio
from unittest.mock import AsyncMock, Mock, patch

from app.agent_framework.llm.base_adapter import LLMResponse
from app.agent_framework.llm.openai_adapter import OpenAIAdapter


def test_openai_adapter_supports_agenerate_prompt_list():
    adapter = OpenAIAdapter(
        api_key="test-key",
        model_name="test-model",
        base_url="https://example.test/v1",
    )
    expected = LLMResponse(content="ok", model="test-model")
    adapter.generate = AsyncMock(return_value=expected)

    result = asyncio.run(adapter.agenerate(["hello"], temperature=0.2, max_tokens=32))

    assert result is expected
    adapter.generate.assert_awaited_once_with(
        "hello", 0.2, 32
    )


def test_openai_client_does_not_inherit_broken_proxy_and_honors_ssl_setting():
    with patch("app.agent_framework.llm.openai_adapter.settings") as settings, \
            patch("app.agent_framework.llm.openai_adapter.httpx.AsyncClient") as client_cls:
        settings.OPENAI_VERIFY_SSL = False
        settings.OPENAI_TRUST_ENV = False
        client_cls.return_value = Mock()
        adapter = OpenAIAdapter(api_key="test-key")

        adapter._get_client()

    client_cls.assert_called_once()
    kwargs = client_cls.call_args.kwargs
    assert kwargs["verify"] is False
    assert kwargs["trust_env"] is False
