import pytest

from models.techdraw_generator import generate_techdraw_script


SAMPLE_CALLOUTS = [
    {
        "feature": "Tabletop",
        "symbol": "flatness",
        "symbol_name": "Flatness",
        "feature_control_frame": "|flatness| 0.10 |",
        "tolerance_value": "0.10",
        "datum_references": [],
        "reasoning": "Flat mounting surface",
    },
    {
        "feature": "Leg_FL",
        "symbol": "perpendicularity",
        "symbol_name": "Perpendicularity",
        "feature_control_frame": "|perpendicularity| 0.05 | A |",
        "tolerance_value": "0.05",
        "datum_references": ["A"],
        "reasoning": "Leg must be perpendicular to tabletop",
    },
]

SAMPLE_DATUM_SCHEME = {
    "primary": {"datum": "A", "surface": "Tabletop bottom face"},
    "secondary": {"datum": "B", "surface": "Front edge"},
    "tertiary": None,
}

SAMPLE_FEATURES = {
    "feature_type": "flat_surface",
    "geometry": {"length": 600.0, "width": 400.0},
}


class TestScriptGeneration:
    def test_script_is_valid_python(self):
        script = generate_techdraw_script(
            document_name="Unnamed",
            callouts=SAMPLE_CALLOUTS,
            datum_scheme=SAMPLE_DATUM_SCHEME,
            features=SAMPLE_FEATURES,
        )
        # compile() raises SyntaxError if script is invalid
        compile(script, "<techdraw_script>", "exec")

    def test_script_creates_draw_page(self):
        script = generate_techdraw_script(
            document_name="Unnamed",
            callouts=SAMPLE_CALLOUTS,
            datum_scheme=SAMPLE_DATUM_SCHEME,
            features=SAMPLE_FEATURES,
        )
        assert "TechDraw::DrawPage" in script
        assert "GDT_Drawing" in script

    def test_script_creates_view_part(self):
        script = generate_techdraw_script(
            document_name="Unnamed",
            callouts=SAMPLE_CALLOUTS,
            datum_scheme=SAMPLE_DATUM_SCHEME,
            features=SAMPLE_FEATURES,
        )
        assert "TechDraw::DrawViewPart" in script

    def test_script_includes_callout_annotations(self):
        script = generate_techdraw_script(
            document_name="Unnamed",
            callouts=SAMPLE_CALLOUTS,
            datum_scheme=SAMPLE_DATUM_SCHEME,
            features=SAMPLE_FEATURES,
        )
        assert "|flatness| 0.10 |" in script
        assert "|perpendicularity| 0.05 | A |" in script
        assert "TechDraw::DrawRichAnno" in script

    def test_script_includes_datum_symbols(self):
        script = generate_techdraw_script(
            document_name="Unnamed",
            callouts=SAMPLE_CALLOUTS,
            datum_scheme=SAMPLE_DATUM_SCHEME,
            features=SAMPLE_FEATURES,
        )
        # Datum calls pass the letter to _add_datum which constructs "Datum_" + letter at runtime
        assert "_add_datum(doc, page, 'A'" in script
        assert "_add_datum(doc, page, 'B'" in script

    def test_script_references_correct_document(self):
        script = generate_techdraw_script(
            document_name="MyPart",
            callouts=[],
            datum_scheme={"primary": None, "secondary": None, "tertiary": None},
            features={},
        )
        assert "FreeCAD.getDocument('MyPart')" in script

    def test_empty_callouts_produces_minimal_script(self):
        script = generate_techdraw_script(
            document_name="Unnamed",
            callouts=[],
            datum_scheme={"primary": None, "secondary": None, "tertiary": None},
            features={},
        )
        compile(script, "<techdraw_script>", "exec")
        assert "TechDraw::DrawPage" in script
        assert "TechDraw::DrawViewPart" in script
        # No callout annotations
        assert "GDT_Tabletop" not in script
        assert "GDT_Leg" not in script

    def test_script_calls_recompute(self):
        script = generate_techdraw_script(
            document_name="Unnamed",
            callouts=SAMPLE_CALLOUTS,
            datum_scheme=SAMPLE_DATUM_SCHEME,
            features=SAMPLE_FEATURES,
        )
        assert "doc.recompute()" in script

    def test_script_returns_result_dict(self):
        script = generate_techdraw_script(
            document_name="Unnamed",
            callouts=SAMPLE_CALLOUTS,
            datum_scheme=SAMPLE_DATUM_SCHEME,
            features=SAMPLE_FEATURES,
        )
        assert '"page_name"' in script
        assert '"annotation_count"' in script
