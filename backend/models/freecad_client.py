import json
import logging

import httpx

from .freecad_extraction import EXTRACTION_SCRIPT
from .mock_cad_contexts import get_desk_mock

logger = logging.getLogger(__name__)


class FreecadConnectionError(Exception):
    """Raised when FreeCAD RPC server is unreachable."""


class FreecadExecutionError(Exception):
    """Raised when FreeCAD fails to execute a Python script."""


class FreecadClient:
    """Async client for FreeCAD JSON-RPC server.

    Communicates with FreeCAD via the freecad-mcp RPC server pattern:
    POST JSON-RPC requests to execute Python code inside FreeCAD's interpreter.
    """

    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 9875

    def __init__(self, host: str | None = None, port: int | None = None):
        self.host = host or self.DEFAULT_HOST
        self.port = port or self.DEFAULT_PORT
        self.base_url = f"http://{self.host}:{self.port}"
        self._client = httpx.AsyncClient(timeout=10.0)
        self._mock_mode = False

    async def health_check(self) -> bool:
        """Check if FreeCAD RPC server is reachable."""
        if self._mock_mode:
            return True
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "execute_python",
                "params": {"code": "import FreeCAD; result = {'version': FreeCAD.Version()}"},
                "id": 1,
            }
            resp = await self._client.post(self.base_url, json=payload)
            resp.raise_for_status()
            logger.info("FreeCAD RPC health check passed at %s", self.base_url)
            return True
        except (httpx.HTTPError, httpx.ConnectError, OSError) as e:
            logger.debug("FreeCAD RPC not reachable at %s: %s", self.base_url, e)
            return False

    async def execute_python(self, code: str) -> dict:
        """Execute Python code inside FreeCAD and return the result."""
        payload = {
            "jsonrpc": "2.0",
            "method": "execute_python",
            "params": {"code": code},
            "id": 1,
        }
        try:
            resp = await self._client.post(self.base_url, json=payload)
            resp.raise_for_status()
        except httpx.ConnectError as e:
            logger.error("FreeCAD RPC connection failed: %s", e)
            raise FreecadConnectionError(
                f"Cannot connect to FreeCAD RPC at {self.base_url}: {e}"
            ) from e
        except httpx.HTTPError as e:
            logger.error("FreeCAD RPC HTTP error: %s", e)
            raise FreecadConnectionError(
                f"FreeCAD RPC request failed: {e}"
            ) from e

        body = resp.json()

        if "error" in body:
            logger.error("FreeCAD execution error: %s", body["error"])
            raise FreecadExecutionError(
                f"FreeCAD execution error: {body['error']}"
            )

        result = body.get("result", {})
        # The RPC server returns the result as a string or dict depending on
        # the server implementation. Handle both.
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError as e:
                logger.error("FreeCAD returned unparseable result: %s", result[:200])
                raise FreecadExecutionError(
                    f"Failed to parse FreeCAD result as JSON: {e}"
                ) from e

        logger.info("FreeCAD execute_python completed, result keys=%s", list(result.keys()) if isinstance(result, dict) else type(result).__name__)
        return result

    async def extract_cad_context(self, description_hint: str = "") -> dict:
        """Run the full CAD extraction script inside FreeCAD.

        Returns structured data: objects, sketches, materials, bounding box.
        Falls back to mock data when in mock mode.
        """
        if self._mock_mode:
            return get_desk_mock()
        return await self.execute_python(EXTRACTION_SCRIPT)

    async def close(self):
        """Close the underlying HTTP client."""
        await self._client.aclose()
