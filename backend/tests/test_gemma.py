import json
import pytest
import httpx
from unittest.mock import AsyncMock, patch
from models.gemma import OllamaClient, OllamaUnavailableError, OllamaParseError


@pytest.fixture
def ollama():
    return OllamaClient(base_url="http://localhost:11434")


def _fake_request() -> httpx.Request:
    """Create a dummy request so httpx.Response.raise_for_status() works."""
    return httpx.Request("POST", "http://localhost:11434/api/chat")


def _mock_chat_response(content: dict) -> httpx.Response:
    """Create a mock Ollama /api/chat response."""
    return httpx.Response(
        200,
        json={
            "model": "gemma3n:e2b",
            "message": {"role": "assistant", "content": json.dumps(content)},
            "done": True,
        },
        request=_fake_request(),
    )


@pytest.mark.asyncio
async def test_chat_json_parses_response(ollama):
    mock_content = {"feature_type": "boss", "geometry": {"diameter": 12.0}}
    mock_resp = _mock_chat_response(mock_content)

    with patch.object(ollama.client, "post", new_callable=AsyncMock, return_value=mock_resp):
        result = await ollama.chat_json("gemma3n:e2b", [{"role": "user", "content": "test"}])
    assert result["feature_type"] == "boss"


@pytest.mark.asyncio
async def test_chat_json_raises_on_invalid_json(ollama):
    bad_resp = httpx.Response(
        200,
        json={
            "model": "gemma3n:e2b",
            "message": {"role": "assistant", "content": "not valid json {{{"},
            "done": True,
        },
        request=_fake_request(),
    )
    with patch.object(ollama.client, "post", new_callable=AsyncMock, return_value=bad_resp):
        with pytest.raises(OllamaParseError):
            await ollama.chat_json("gemma3n:e2b", [{"role": "user", "content": "test"}])


@pytest.mark.asyncio
async def test_chat_raises_on_connection_error(ollama):
    with patch.object(
        ollama.client, "post", new_callable=AsyncMock, side_effect=httpx.ConnectError("refused")
    ):
        with pytest.raises(OllamaUnavailableError):
            await ollama.chat("gemma3n:e2b", [{"role": "user", "content": "test"}])


@pytest.mark.asyncio
async def test_chat_raises_on_timeout(ollama):
    with patch.object(
        ollama.client, "post", new_callable=AsyncMock, side_effect=httpx.ReadTimeout("timeout")
    ):
        with pytest.raises(OllamaUnavailableError):
            await ollama.chat("gemma3n:e2b", [{"role": "user", "content": "test"}])


@pytest.mark.asyncio
async def test_classify_gdt_uses_specified_model(ollama):
    mock_content = {
        "primary_control": "perpendicularity",
        "symbol": "\u22a5",
        "symbol_name": "perpendicularity",
        "tolerance_class": "tight",
        "datum_required": True,
        "modifier": None,
        "reasoning_key": "test",
        "confidence": 0.9,
    }
    mock_resp = _mock_chat_response(mock_content)

    with patch.object(ollama.client, "post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
        await ollama.classify_gdt({"feature_type": "boss"}, model="gemma3:1b-gdt-ft")
        call_payload = mock_post.call_args[1]["json"]
        assert call_payload["model"] == "gemma3:1b-gdt-ft"


@pytest.mark.asyncio
async def test_health_check_success(ollama):
    mock_resp = httpx.Response(
        200,
        json={"models": [{"name": "gemma3n:e2b"}]},
        request=httpx.Request("GET", "http://localhost:11434/api/tags"),
    )
    with patch.object(ollama.client, "get", new_callable=AsyncMock, return_value=mock_resp):
        result = await ollama.health_check()
        assert "models" in result


@pytest.mark.asyncio
async def test_health_check_ollama_down(ollama):
    with patch.object(
        ollama.client, "get", new_callable=AsyncMock, side_effect=httpx.ConnectError("refused")
    ):
        with pytest.raises(OllamaUnavailableError):
            await ollama.health_check()
