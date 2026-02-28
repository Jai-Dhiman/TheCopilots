import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import httpx

from models.freecad_client import (
    FreecadClient,
    FreecadConnectionError,
    FreecadExecutionError,
)


@pytest.fixture
def client():
    return FreecadClient(host="127.0.0.1", port=9875)


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_returns_true_when_server_responds(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "result": {"version": ["0", "21", "0"]},
            "id": 1,
        }

        with patch.object(client._client, "post", new_callable=AsyncMock, return_value=mock_response):
            assert await client.health_check() is True

    @pytest.mark.asyncio
    async def test_returns_false_on_connection_error(self, client):
        with patch.object(
            client._client, "post", new_callable=AsyncMock,
            side_effect=httpx.ConnectError("refused"),
        ):
            assert await client.health_check() is False

    @pytest.mark.asyncio
    async def test_returns_false_on_http_error(self, client):
        with patch.object(
            client._client, "post", new_callable=AsyncMock,
            side_effect=httpx.HTTPStatusError(
                "500", request=MagicMock(), response=MagicMock()
            ),
        ):
            assert await client.health_check() is False


class TestExecutePython:
    @pytest.mark.asyncio
    async def test_returns_parsed_dict_result(self, client):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "result": {"document_name": "test_part", "objects": []},
            "id": 1,
        }

        with patch.object(client._client, "post", new_callable=AsyncMock, return_value=mock_response):
            result = await client.execute_python("import FreeCAD; result = {}")
            assert result == {"document_name": "test_part", "objects": []}

    @pytest.mark.asyncio
    async def test_parses_string_result_as_json(self, client):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "result": json.dumps({"document_name": "bracket", "objects": [{"name": "Pad"}]}),
            "id": 1,
        }

        with patch.object(client._client, "post", new_callable=AsyncMock, return_value=mock_response):
            result = await client.execute_python("some code")
            assert result["document_name"] == "bracket"
            assert result["objects"][0]["name"] == "Pad"

    @pytest.mark.asyncio
    async def test_raises_on_connection_error(self, client):
        with patch.object(
            client._client, "post", new_callable=AsyncMock,
            side_effect=httpx.ConnectError("refused"),
        ):
            with pytest.raises(FreecadConnectionError, match="Cannot connect"):
                await client.execute_python("code")

    @pytest.mark.asyncio
    async def test_raises_on_rpc_error(self, client):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "error": {"code": -1, "message": "NameError: name 'foo' is not defined"},
            "id": 1,
        }

        with patch.object(client._client, "post", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(FreecadExecutionError, match="execution error"):
                await client.execute_python("foo()")

    @pytest.mark.asyncio
    async def test_raises_on_invalid_json_string(self, client):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "result": "this is not json {{{",
            "id": 1,
        }

        with patch.object(client._client, "post", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(FreecadExecutionError, match="Failed to parse"):
                await client.execute_python("code")

    @pytest.mark.asyncio
    async def test_sends_correct_jsonrpc_payload(self, client):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"jsonrpc": "2.0", "result": {}, "id": 1}

        with patch.object(client._client, "post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
            await client.execute_python("print('hello')")
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args
            payload = call_kwargs.kwargs["json"] if "json" in call_kwargs.kwargs else call_kwargs[1]["json"]
            assert payload["jsonrpc"] == "2.0"
            assert payload["method"] == "execute_python"
            assert payload["params"]["code"] == "print('hello')"


class TestExtractCadContext:
    @pytest.mark.asyncio
    async def test_calls_execute_python_with_extraction_script(self, client):
        from models.freecad_extraction import EXTRACTION_SCRIPT

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "result": json.dumps({
                "document_name": "bracket",
                "objects": [{"name": "Pad", "type": "PartDesign::Pad"}],
                "sketches": [],
                "materials": [],
                "bounding_box": {"x_min": 0, "x_max": 50},
            }),
            "id": 1,
        }

        with patch.object(client._client, "post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
            result = await client.extract_cad_context()

            assert result["document_name"] == "bracket"
            assert len(result["objects"]) == 1

            payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1]["json"]
            assert payload["params"]["code"] == EXTRACTION_SCRIPT


class TestClientInit:
    def test_default_host_and_port(self):
        c = FreecadClient()
        assert c.host == "127.0.0.1"
        assert c.port == 9875
        assert c.base_url == "http://127.0.0.1:9875"

    def test_custom_host_and_port(self):
        c = FreecadClient(host="192.168.1.10", port=8080)
        assert c.host == "192.168.1.10"
        assert c.port == 8080
        assert c.base_url == "http://192.168.1.10:8080"

    @pytest.mark.asyncio
    async def test_close_closes_http_client(self):
        c = FreecadClient()
        with patch.object(c._client, "aclose", new_callable=AsyncMock) as mock_close:
            await c.close()
            mock_close.assert_called_once()
