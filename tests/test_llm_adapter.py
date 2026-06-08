import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.engine.llm_adapter import (
    BaseLLMProvider,
    create_provider,
    FallbackProvider,
    LLMProviderError,
    MockProvider,
    OpenAIProvider,
)


@pytest.fixture
def mock_response():
    def _make(content: str, status_code: int = 200):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = status_code
        resp.json.return_value = {
            "choices": [{"message": {"content": content}}],
        }
        resp.text = content
        return resp
    return _make


@pytest.mark.asyncio
async def test_openai_provider_success(mock_response):
    provider = OpenAIProvider(api_key="test-key", base_url="https://api.example.com/v1")
    expected = "你好，旅行者。"
    with patch.object(
        provider._client, "post",
        new_callable=AsyncMock,
        return_value=mock_response(expected),
    ):
        result = await provider.generate("system", "user")
        assert result == expected


@pytest.mark.asyncio
async def test_openai_provider_network_error():
    provider = OpenAIProvider(api_key="test-key")
    with patch.object(
        provider._client, "post",
        new_callable=AsyncMock,
        side_effect=httpx.ConnectError("connection refused"),
    ):
        with pytest.raises(LLMProviderError, match="Network error"):
            await provider.generate("system", "user")


@pytest.mark.asyncio
async def test_openai_provider_http_error(mock_response):
    provider = OpenAIProvider(api_key="test-key")
    with patch.object(
        provider._client, "post",
        new_callable=AsyncMock,
        return_value=mock_response("unauthorized", status_code=401),
    ):
        with pytest.raises(LLMProviderError, match="status 401"):
            await provider.generate("system", "user")


@pytest.mark.asyncio
async def test_openai_provider_json_decode_error(mock_response):
    provider = OpenAIProvider(api_key="test-key")
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.side_effect = ValueError("bad json")
    resp.text = "not json"
    with patch.object(
        provider._client, "post",
        new_callable=AsyncMock,
        return_value=resp,
    ):
        with pytest.raises(LLMProviderError, match="JSON decode error"):
            await provider.generate("system", "user")


@pytest.mark.asyncio
async def test_openai_provider_bad_response_format(mock_response):
    provider = OpenAIProvider(api_key="test-key")
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = {"no_choices": True}
    resp.text = "{}"
    with patch.object(
        provider._client, "post",
        new_callable=AsyncMock,
        return_value=resp,
    ):
        with pytest.raises(LLMProviderError, match="Unexpected response format"):
            await provider.generate("system", "user")


@pytest.mark.asyncio
async def test_fallback_provider_primary_success():
    primary = AsyncMock(spec=BaseLLMProvider)
    primary.generate.return_value = "LLM response"
    fallback = AsyncMock(spec=BaseLLMProvider)

    provider = FallbackProvider(primary=primary, fallback=fallback)
    result = await provider.generate("system", "user")

    assert result == "LLM response"
    primary.generate.assert_awaited_once_with("system", "user")
    fallback.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_fallback_provider_primary_fails():
    primary = AsyncMock(spec=BaseLLMProvider)
    primary.generate.side_effect = LLMProviderError("timeout")
    fallback = AsyncMock(spec=BaseLLMProvider)
    fallback.generate.return_value = "Mock fallback"

    provider = FallbackProvider(primary=primary, fallback=fallback)
    result = await provider.generate("system", "user")

    assert result == "Mock fallback"
    primary.generate.assert_awaited_once()
    fallback.generate.assert_awaited_once_with("system", "user")


@pytest.mark.asyncio
async def test_fallback_provider_unexpected_exception():
    primary = AsyncMock(spec=BaseLLMProvider)
    primary.generate.side_effect = RuntimeError("unexpected")
    fallback = AsyncMock(spec=BaseLLMProvider)
    fallback.generate.return_value = "safe"

    provider = FallbackProvider(primary=primary, fallback=fallback)
    result = await provider.generate("system", "user")

    assert result == "safe"


def test_create_provider_default_is_mock():
    with patch.dict(os.environ, {}, clear=True):
        provider = create_provider()
        assert isinstance(provider, MockProvider)


def test_create_provider_explicit_mock():
    with patch.dict(os.environ, {"LLM_PROVIDER": "mock"}, clear=False):
        provider = create_provider()
        assert isinstance(provider, MockProvider)


def test_create_provider_openai_no_key():
    with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}, clear=False):
        os.environ.pop("LLM_API_KEY", None)
        provider = create_provider()
        assert isinstance(provider, MockProvider)


def test_create_provider_openai_with_key():
    env = {
        "LLM_PROVIDER": "openai",
        "LLM_API_KEY": "sk-test-123",
        "LLM_BASE_URL": "https://api.example.com/v1",
        "LLM_MODEL": "gpt-4o-mini",
        "LLM_TIMEOUT": "15",
    }
    with patch.dict(os.environ, env, clear=False):
        provider = create_provider()
        assert isinstance(provider, FallbackProvider)
        assert isinstance(provider._primary, OpenAIProvider)
        assert isinstance(provider._fallback, MockProvider)


def test_create_provider_openai_custom_timeout():
    env = {
        "LLM_PROVIDER": "openai",
        "LLM_API_KEY": "sk-test",
        "LLM_TIMEOUT": "15",
    }
    with patch.dict(os.environ, env, clear=False):
        provider = create_provider()
        assert isinstance(provider, FallbackProvider)
        openai_p = provider._primary
        assert openai_p._timeout == 15


def test_create_provider_timeout_invalid_string():
    env = {
        "LLM_PROVIDER": "openai",
        "LLM_API_KEY": "sk-test",
        "LLM_TIMEOUT": "abc",
    }
    with patch.dict(os.environ, env, clear=False):
        provider = create_provider()
        assert isinstance(provider, FallbackProvider)
        assert provider._primary._timeout == 30


def test_create_provider_timeout_zero():
    env = {
        "LLM_PROVIDER": "openai",
        "LLM_API_KEY": "sk-test",
        "LLM_TIMEOUT": "0",
    }
    with patch.dict(os.environ, env, clear=False):
        provider = create_provider()
        assert isinstance(provider, FallbackProvider)
        assert provider._primary._timeout == 30


def test_create_provider_timeout_negative():
    env = {
        "LLM_PROVIDER": "openai",
        "LLM_API_KEY": "sk-test",
        "LLM_TIMEOUT": "-1",
    }
    with patch.dict(os.environ, env, clear=False):
        provider = create_provider()
        assert isinstance(provider, FallbackProvider)
        assert provider._primary._timeout == 30
