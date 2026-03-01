import asyncio
import base64
import logging
import os
import tempfile
import time

logger = logging.getLogger(__name__)

INFERENCE_TIMEOUT = 120
DESCRIBE_MAX_TOKENS = 256

# Lazy sentinel -- actual imports happen in _ensure_imports().
# Module-level names exist so tests can patch them at "models.mlx_vlm_client.<name>".
mlx_load = None
mlx_generate = None
apply_chat_template = None
load_config = None


def _ensure_imports():
    global mlx_load, mlx_generate, apply_chat_template, load_config
    if mlx_load is not None:
        return
    from mlx_vlm import load as _load, generate as _generate
    from mlx_vlm.prompt_utils import apply_chat_template as _apply
    from mlx_vlm.utils import load_config as _cfg
    mlx_load = _load
    mlx_generate = _generate
    apply_chat_template = _apply
    load_config = _cfg


class MlxVlmLoadError(Exception):
    """Raised when mlx-vlm model fails to load."""
    pass


class MlxVlmTimeoutError(Exception):
    """Raised when mlx-vlm inference exceeds the timeout."""
    pass


class MlxVlmClient:
    MODEL_ID = "mlx-community/paligemma2-3b-mix-224-4bit"

    def __init__(self):
        self.model = None
        self.processor = None
        self.config = None

    def load(self):
        """Load model into memory. Call once on startup."""
        _ensure_imports()
        try:
            self.model, self.processor = mlx_load(self.MODEL_ID)
            self.config = load_config(self.MODEL_ID)
        except Exception as e:
            raise MlxVlmLoadError(f"Failed to load {self.MODEL_ID}: {e}") from e

    async def describe_image(self, image_base64: str) -> str:
        """Describe a CAD screenshot using PaliGemma 2. Returns plain text."""
        from .prompts import PALIGEMMA_DESCRIBE_PROMPT

        image_paths, temp_path = self._prepare_image(image_base64)
        try:
            raw = await self._generate(
                PALIGEMMA_DESCRIBE_PROMPT, image_paths, max_tokens=DESCRIBE_MAX_TOKENS
            )
        finally:
            if temp_path:
                os.unlink(temp_path)
        return raw.strip()

    async def _generate(
        self, prompt: str, image_paths: list[str] | None, max_tokens: int = 256
    ) -> str:
        """Run mlx_vlm.generate in a thread to avoid blocking the event loop."""
        num_images = len(image_paths) if image_paths else 0
        formatted = apply_chat_template(
            self.processor, self.config, prompt, num_images=num_images
        )
        t0 = time.monotonic()
        logger.info("mlx-vlm inference starting (max_tokens=%d)", max_tokens)
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    mlx_generate,
                    self.model,
                    self.processor,
                    formatted,
                    image_paths,
                    verbose=False,
                    max_tokens=max_tokens,
                ),
                timeout=INFERENCE_TIMEOUT,
            )
        except asyncio.TimeoutError:
            elapsed = time.monotonic() - t0
            logger.error("mlx-vlm inference timed out after %.1fs", elapsed)
            raise MlxVlmTimeoutError(
                f"Inference timed out after {INFERENCE_TIMEOUT}s"
            )
        elapsed = time.monotonic() - t0
        logger.info("mlx-vlm inference completed in %.1fs", elapsed)
        return result.text

    def _prepare_image(
        self, image_base64: str | None
    ) -> tuple[list[str] | None, str | None]:
        """Convert base64 image to temp file. Returns (paths_list, temp_path_for_cleanup)."""
        if not image_base64:
            return None, None
        image_bytes = base64.b64decode(image_base64)
        fd, temp_path = tempfile.mkstemp(suffix=".png")
        try:
            os.write(fd, image_bytes)
        finally:
            os.close(fd)
        return [temp_path], temp_path
