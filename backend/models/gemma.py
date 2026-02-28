import json
import httpx


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
            timeout=httpx.Timeout(30.0, connect=5.0),
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

        try:
            resp = await self.client.post("/api/chat", json=payload)
            resp.raise_for_status()
        except httpx.ConnectError as e:
            raise OllamaUnavailableError(str(e)) from e
        except httpx.TimeoutException as e:
            raise OllamaUnavailableError(
                f"Ollama timed out on model {model}"
            ) from e

        return resp.json()

    async def chat_json(self, model: str, messages: list[dict], **kwargs) -> dict:
        """Chat and parse the response content as JSON."""
        result = await self.chat(model, messages, format="json", **kwargs)
        content = result["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise OllamaParseError(
                f"Model {model} returned invalid JSON: {content[:200]}"
            ) from e

    async def extract_features(
        self, text: str, image_base64: str | None = None
    ) -> dict:
        """Layer 1: Student -- Gemma 3n feature extraction."""
        from .prompts import FEATURE_EXTRACTION_SYSTEM

        messages = [
            {"role": "system", "content": FEATURE_EXTRACTION_SYSTEM},
            {"role": "user", "content": text},
        ]
        images = [image_base64] if image_base64 else None
        return await self.chat_json("gemma3n:e2b", messages, images=images)

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

    async def generate_output(
        self,
        features: dict,
        classification: dict,
        datum_scheme: dict,
        standards: list[dict],
        tolerances: dict,
    ) -> dict:
        """Layer 5: Worker -- Gemma 3n output generation."""
        from .prompts import WORKER_SYSTEM, build_worker_user_prompt

        messages = [
            {"role": "system", "content": WORKER_SYSTEM},
            {
                "role": "user",
                "content": build_worker_user_prompt(
                    features, classification, datum_scheme, standards, tolerances
                ),
            },
        ]
        return await self.chat_json("gemma3n:e2b", messages)

    async def close(self):
        await self.client.aclose()
