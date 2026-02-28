from models.prompts import (
    FEATURE_EXTRACTION_SYSTEM,
    CLASSIFICATION_SYSTEM,
    WORKER_SYSTEM,
    build_worker_user_prompt,
)


def test_feature_extraction_prompt_has_schema():
    assert "feature_type" in FEATURE_EXTRACTION_SYSTEM
    assert "geometry" in FEATURE_EXTRACTION_SYSTEM
    assert "material" in FEATURE_EXTRACTION_SYSTEM
    assert "JSON" in FEATURE_EXTRACTION_SYSTEM


def test_classification_prompt_has_symbols():
    assert "\u22a5" in CLASSIFICATION_SYSTEM  # perpendicularity
    assert "\u2295" in CLASSIFICATION_SYSTEM  # position
    assert "datum_required" in CLASSIFICATION_SYSTEM


def test_classification_prompt_has_runout_rule():
    assert "runout" in CLASSIFICATION_SYSTEM.lower()
    assert "concentricity" in CLASSIFICATION_SYSTEM.lower()


def test_worker_prompt_has_fcf_format():
    assert "feature_control_frame" in WORKER_SYSTEM
    assert "callouts" in WORKER_SYSTEM
    assert "warnings" in WORKER_SYSTEM


def test_build_worker_user_prompt():
    result = build_worker_user_prompt(
        features={"feature_type": "boss", "geometry": {"diameter": 12.0}},
        classification={"primary_control": "perpendicularity", "symbol": "\u22a5"},
        datum_scheme={"primary": {"datum": "A", "surface": "face"}},
        standards=[{"key": "7.1", "score": 0.9}],
        tolerances={"tolerance_range": {"min_mm": 0.02, "max_mm": 0.1}},
    )
    assert "boss" in result
    assert "perpendicularity" in result
    assert "12.0" in result
