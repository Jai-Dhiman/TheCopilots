from api.schemas import (
    AnalyzeRequest,
    CADContext,
    Geometry,
    FeatureRecord,
    GDTClassification,
    DatumLevel,
    DatumScheme,
    GDTCallout,
    AnalysisMetadata,
    WorkerResult,
)


def test_cad_context_defaults():
    ctx = CADContext()
    assert ctx.document_name is None
    assert ctx.objects == []
    assert ctx.sketches == []
    assert ctx.materials == []
    assert ctx.bounding_box is None
    assert ctx.source == "freecad_rpc"


def test_cad_context_full():
    ctx = CADContext(
        document_name="bracket",
        objects=[{"name": "Pad", "type": "PartDesign::Pad"}],
        materials=[{"body": "Body", "material": "AL6061-T6"}],
        bounding_box={"x_min": 0, "x_max": 50},
    )
    assert ctx.document_name == "bracket"
    assert len(ctx.objects) == 1


def test_analyze_request_with_cad_context():
    ctx = CADContext(document_name="test")
    req = AnalyzeRequest(description="boss", cad_context=ctx)
    assert req.cad_context is not None
    assert req.cad_context.document_name == "test"


def test_analyze_request_minimal():
    req = AnalyzeRequest(description="12mm boss on mounting face")
    assert req.description == "12mm boss on mounting face"
    assert req.image_base64 is None
    assert req.compare is False
    assert req.cad_context is None


def test_analyze_request_full():
    req = AnalyzeRequest(
        description="boss",
        image_base64="abc123",
        manufacturing_process="cnc_milling",
        material="AL6061-T6",
        compare=True,
    )
    assert req.compare is True
    assert req.manufacturing_process == "cnc_milling"


def test_geometry_defaults():
    g = Geometry()
    assert g.unit == "mm"
    assert g.diameter is None


def test_feature_record():
    rec = FeatureRecord(
        feature_type="boss",
        geometry=Geometry(diameter=12.0, height=8.0),
        material="AL6061-T6",
        manufacturing_process="cnc_milling",
    )
    assert rec.feature_type == "boss"
    assert rec.geometry.diameter == 12.0
    assert rec.mating_condition is None


def test_gdt_classification():
    cls = GDTClassification(
        primary_control="perpendicularity",
        symbol="\u22a5",
        symbol_name="perpendicularity",
        tolerance_class="tight",
        datum_required=True,
        modifier="MMC",
        reasoning_key="bearing_alignment",
        confidence=0.92,
    )
    assert cls.datum_required is True
    assert cls.symbol == "\u22a5"


def test_datum_scheme_no_tertiary():
    scheme = DatumScheme(
        primary=DatumLevel(datum="A", surface="mounting_face", reasoning="largest flat"),
        secondary=DatumLevel(datum="B", surface="locating_hole", reasoning="perpendicular"),
    )
    assert scheme.tertiary is None


def test_gdt_callout():
    callout = GDTCallout(
        feature="boss",
        symbol="\u22a5",
        symbol_name="perpendicularity",
        tolerance_value="\u23000.05",
        unit="mm",
        modifier="MMC",
        modifier_symbol="\u24c2",
        datum_references=["A"],
        feature_control_frame="|\u22a5| \u23000.05 \u24c2 | A |",
        reasoning="Bearing alignment requires perpendicularity",
    )
    assert callout.datum_references == ["A"]


def test_analysis_metadata_defaults():
    meta = AnalysisMetadata(
        total_latency_ms=847,
        student_latency_ms=290,
        classifier_latency_ms=78,
        matcher_latency_ms=42,
        brain_latency_ms=12,
        worker_latency_ms=425,
    )
    assert meta.cloud_calls == 0
    assert meta.connectivity_required is False
