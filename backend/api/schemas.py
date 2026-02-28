from pydantic import BaseModel


class CADContext(BaseModel):
    document_name: str | None = None
    objects: list[dict] = []
    sketches: list[dict] = []
    materials: list[dict] = []
    bounding_box: dict | None = None
    source: str = "freecad_rpc"


class AnalyzeRequest(BaseModel):
    description: str
    image_base64: str | None = None
    manufacturing_process: str | None = None
    material: str | None = None
    compare: bool = False
    cad_context: CADContext | None = None


class Geometry(BaseModel):
    diameter: float | None = None
    length: float | None = None
    width: float | None = None
    height: float | None = None
    depth: float | None = None
    angle: float | None = None
    count: int | None = None
    pcd: float | None = None
    unit: str = "mm"


class FeatureRecord(BaseModel):
    feature_type: str
    geometry: Geometry
    material: str
    manufacturing_process: str
    mating_condition: str | None = None
    parent_surface: str | None = None


class GDTClassification(BaseModel):
    primary_control: str
    symbol: str
    symbol_name: str
    tolerance_class: str
    datum_required: bool
    modifier: str | None = None
    reasoning_key: str
    confidence: float


class DatumLevel(BaseModel):
    datum: str
    surface: str
    reasoning: str


class DatumScheme(BaseModel):
    primary: DatumLevel | None = None
    secondary: DatumLevel | None = None
    tertiary: DatumLevel | None = None


class GDTCallout(BaseModel):
    feature: str
    symbol: str
    symbol_name: str
    tolerance_value: str
    unit: str = "mm"
    modifier: str | None = None
    modifier_symbol: str | None = None
    datum_references: list[str] = []
    feature_control_frame: str
    reasoning: str


class AnalysisMetadata(BaseModel):
    inference_device: str = "local"
    total_latency_ms: int
    student_latency_ms: int
    classifier_latency_ms: int
    matcher_latency_ms: int
    brain_latency_ms: int
    worker_latency_ms: int
    cloud_calls: int = 0
    connectivity_required: bool = False


class WorkerResult(BaseModel):
    callouts: list[GDTCallout] = []
    summary: str = ""
    manufacturing_notes: str = ""
    standards_references: list[str] = []
    warnings: list[str] = []
