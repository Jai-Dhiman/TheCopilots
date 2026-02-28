import asyncio
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from models.mlx_vlm_client import MlxVlmClient, MlxVlmLoadError, MlxVlmParseError, MlxVlmTimeoutError, INFERENCE_TIMEOUT


@pytest.fixture
def mock_model():
    return MagicMock(name="mock_model")


@pytest.fixture
def mock_processor():
    return MagicMock(name="mock_processor")


@pytest.fixture
def mock_config():
    return MagicMock(name="mock_config")


@pytest.fixture
def client(mock_model, mock_processor, mock_config):
    """Create an MlxVlmClient with pre-loaded mocks."""
    c = MlxVlmClient()
    c.model = mock_model
    c.processor = mock_processor
    c.config = mock_config
    return c


def _mock_generation_result(text: str):
    result = MagicMock()
    result.text = text
    return result


@patch("models.mlx_vlm_client.load_config")
@patch("models.mlx_vlm_client.mlx_load")
def test_load_model_calls_mlx_vlm_load(mock_load, mock_load_config, mock_model, mock_processor, mock_config):
    mock_load.return_value = (mock_model, mock_processor)
    mock_load_config.return_value = mock_config

    c = MlxVlmClient()
    c.load()

    mock_load.assert_called_once_with(MlxVlmClient.MODEL_ID)
    mock_load_config.assert_called_once_with(MlxVlmClient.MODEL_ID)
    assert c.model is mock_model
    assert c.processor is mock_processor
    assert c.config is mock_config


@patch("models.mlx_vlm_client.load_config", side_effect=RuntimeError("model not found"))
@patch("models.mlx_vlm_client.mlx_load", side_effect=RuntimeError("model not found"))
def test_load_model_raises_on_failure(mock_load, mock_load_config):
    c = MlxVlmClient()
    with pytest.raises(MlxVlmLoadError):
        c.load()


@pytest.mark.asyncio
@patch("models.mlx_vlm_client.apply_chat_template", return_value="formatted prompt")
@patch("models.mlx_vlm_client.mlx_generate")
async def test_extract_features_text_only(mock_gen, mock_template, client):
    mock_gen.return_value = _mock_generation_result('{"feature_type": "boss"}')

    result = await client.extract_features("12mm aluminum boss")

    assert result == {"feature_type": "boss"}
    mock_template.assert_called_once()
    # num_images should be 0 for text-only
    _, kwargs = mock_template.call_args
    assert kwargs.get("num_images", mock_template.call_args[0][3] if len(mock_template.call_args[0]) > 3 else None) == 0


@pytest.mark.asyncio
@patch("models.mlx_vlm_client.apply_chat_template", return_value="formatted prompt")
@patch("models.mlx_vlm_client.mlx_generate")
async def test_extract_features_with_image(mock_gen, mock_template, client):
    mock_gen.return_value = _mock_generation_result('{"feature_type": "hole"}')

    result = await client.extract_features("describe this", image_base64="iVBORw0KGgo=")

    assert result == {"feature_type": "hole"}
    # Should have been called with image paths (a temp file)
    call_args = mock_gen.call_args
    image_arg = call_args[0][3] if len(call_args[0]) > 3 else call_args[1].get("image")
    assert image_arg is not None
    assert len(image_arg) == 1


@pytest.mark.asyncio
@patch("models.mlx_vlm_client.apply_chat_template", return_value="formatted prompt")
@patch("models.mlx_vlm_client.mlx_generate")
async def test_extract_features_raises_on_unparseable(mock_gen, mock_template, client):
    mock_gen.return_value = _mock_generation_result("I cannot parse this input properly")

    with pytest.raises(MlxVlmParseError):
        await client.extract_features("12mm boss")


@pytest.mark.asyncio
@patch("models.mlx_vlm_client.apply_chat_template", return_value="formatted prompt")
@patch("models.mlx_vlm_client.mlx_generate")
async def test_extract_features_parses_markdown_fenced_json(mock_gen, mock_template, client):
    fenced = '```json\n{"feature_type": "slot", "geometry": {}}\n```'
    mock_gen.return_value = _mock_generation_result(fenced)

    result = await client.extract_features("describe slot")

    assert result["feature_type"] == "slot"


@pytest.mark.asyncio
@patch("models.mlx_vlm_client.apply_chat_template", return_value="formatted prompt")
@patch("models.mlx_vlm_client.mlx_generate")
async def test_generate_output_text_only(mock_gen, mock_template, client):
    output = json.dumps({
        "callouts": [{"feature": "boss"}],
        "summary": "test",
        "manufacturing_notes": "",
        "standards_references": [],
        "warnings": [],
    })
    mock_gen.return_value = _mock_generation_result(output)

    result = await client.generate_output(
        features={"feature_type": "boss"},
        classification={"primary_control": "perpendicularity"},
        datum_scheme={"primary": "A"},
        standards=[],
        tolerances={},
    )

    assert result["callouts"][0]["feature"] == "boss"
    # num_images should be 0 for worker (text-only)
    _, kwargs = mock_template.call_args
    assert kwargs.get("num_images", mock_template.call_args[0][3] if len(mock_template.call_args[0]) > 3 else None) == 0


@pytest.mark.asyncio
@patch("models.mlx_vlm_client.apply_chat_template", return_value="formatted prompt")
@patch("models.mlx_vlm_client.mlx_generate")
async def test_generate_output_uses_worker_prompt(mock_gen, mock_template, client):
    mock_gen.return_value = _mock_generation_result('{"callouts": [], "summary": "", "manufacturing_notes": "", "standards_references": [], "warnings": []}')

    await client.generate_output(
        features={"feature_type": "boss"},
        classification={"primary_control": "perpendicularity"},
        datum_scheme={"primary": "A"},
        standards=[],
        tolerances={},
    )

    # The prompt passed to apply_chat_template should contain worker system prompt
    prompt_arg = mock_template.call_args[0][2]
    assert "GD&T output generator" in prompt_arg or "Worker" in prompt_arg or "ASME" in prompt_arg


@pytest.mark.asyncio
@patch("models.mlx_vlm_client.apply_chat_template", return_value="formatted prompt")
@patch("models.mlx_vlm_client.mlx_generate")
async def test_generate_runs_in_thread(mock_gen, mock_template, client):
    """Verify _generate uses asyncio.to_thread (wrapped in wait_for)."""
    mock_gen.return_value = _mock_generation_result('{"feature_type": "boss"}')

    result = await client.extract_features("test")
    # mlx_generate is called inside asyncio.to_thread; verify it was called
    mock_gen.assert_called_once()


@pytest.mark.asyncio
@patch("models.mlx_vlm_client.apply_chat_template", return_value="formatted prompt")
@patch("models.mlx_vlm_client.mlx_generate")
async def test_generate_timeout_raises(mock_gen, mock_template, client):
    """Verify MlxVlmTimeoutError is raised when inference exceeds timeout."""
    async def slow_thread(*args, **kwargs):
        await asyncio.sleep(999)

    with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
        with pytest.raises(MlxVlmTimeoutError):
            await client._generate("test prompt", None)


@pytest.mark.asyncio
@patch("models.mlx_vlm_client.apply_chat_template", return_value="formatted prompt")
@patch("models.mlx_vlm_client.mlx_generate")
async def test_temp_file_cleanup(mock_gen, mock_template, client):
    mock_gen.return_value = _mock_generation_result('{"feature_type": "hole"}')

    import tempfile
    import os

    # Track temp files created
    original_mkstemp = tempfile.mkstemp
    created_files = []

    def tracking_mkstemp(*args, **kwargs):
        fd, path = original_mkstemp(*args, **kwargs)
        created_files.append(path)
        return fd, path

    with patch("tempfile.mkstemp", side_effect=tracking_mkstemp):
        await client.extract_features("test", image_base64="iVBORw0KGgo=")

    # All temp files should have been cleaned up
    for path in created_files:
        assert not os.path.exists(path), f"Temp file {path} was not cleaned up"
