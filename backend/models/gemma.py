import json
import logging
import time

import httpx

logger = logging.getLogger(__name__)


class OllamaUnavailableError(Exception):
    """Raised when Ollama server is not reachable."""
    pass


class OllamaParseError(Exception):
    """Raised when Ollama returns non-JSON or unparseable output."""
    pass


class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(90.0, connect=5.0),
        )

    async def health_check(self) -> dict:
        """GET /api/tags -- verify Ollama is running and list loaded models."""
        try:
            resp = await self.client.get("/api/tags")
            resp.raise_for_status()
            return resp.json()
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise OllamaUnavailableError(
                f"Ollama not reachable at {self.base_url}: {e}"
            ) from e

    async def chat(
        self,
        model: str,
        messages: list[dict],
        format: str = "json",
        images: list[str] | None = None,
    ) -> dict:
        """Send a chat completion request to Ollama /api/chat."""
        if images:
            messages[-1]["images"] = images

        payload = {
            "model": model,
            "messages": messages,
            "format": format,
            "stream": False,
        }

        t0 = time.monotonic()
        logger.info("Ollama /api/chat request to model=%s", model)
        try:
            resp = await self.client.post("/api/chat", json=payload)
            resp.raise_for_status()
        except httpx.ConnectError as e:
            logger.error("Ollama connection failed: %s", e)
            raise OllamaUnavailableError(str(e)) from e
        except httpx.TimeoutException as e:
            logger.error("Ollama timed out after %.1fs for model=%s", time.monotonic() - t0, model)
            raise OllamaUnavailableError(
                f"Ollama timed out on model {model}"
            ) from e
        except httpx.HTTPStatusError as e:
            logger.error("Ollama HTTP %d for model=%s", e.response.status_code, model)
            raise OllamaUnavailableError(
                f"Ollama returned {e.response.status_code} for model {model}"
            ) from e

        elapsed = time.monotonic() - t0
        logger.info("Ollama /api/chat completed in %.1fs for model=%s", elapsed, model)
        return resp.json()

    async def chat_json(self, model: str, messages: list[dict], **kwargs) -> dict:
        """Chat and parse the response content as JSON."""
        result = await self.chat(model, messages, format="json", **kwargs)
        content = result["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning("Ollama model=%s returned invalid JSON: %s", model, content[:200])
            raise OllamaParseError(
                f"Model {model} returned invalid JSON: {content[:200]}"
            ) from e

    async def generate_output(
        self,
        features: dict,
        classification: dict,
        datum_scheme: dict,
        standards: list[dict],
        tolerances: dict,
        model: str = "gemma3:1b",
    ) -> dict:
        """Layer 5: Worker -- GD&T output generation via Ollama."""
        from .prompts import WORKER_SYSTEM, build_worker_user_prompt

        user_content = build_worker_user_prompt(
            features, classification, datum_scheme, standards, tolerances
        )
        messages = [
            {"role": "system", "content": WORKER_SYSTEM},
            {"role": "user", "content": user_content},
        ]
        return await self.chat_json(model, messages)

    async def extract_features(
        self, description: str, model: str = "gemma3:1b"
    ) -> dict:
        """Extract structured features from a text description via Ollama."""
        from .prompts import FEATURE_EXTRACTION_SYSTEM

        messages = [
            {"role": "system", "content": FEATURE_EXTRACTION_SYSTEM},
            {"role": "user", "content": description},
        ]
        return await self.chat_json(model, messages)

    async def classify_gdt(
        self, features: dict, model: str = "gemma3:1b"
    ) -> dict:
        """Layer 2: Classifier -- Gemma GD&T classification."""
        from .prompts import CLASSIFICATION_SYSTEM

        messages = [
            {"role": "system", "content": CLASSIFICATION_SYSTEM},
            {"role": "user", "content": json.dumps(features)},
        ]
        return await self.chat_json(model, messages)

    async def close(self):
        await self.client.aclose()
