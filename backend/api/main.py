import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"

from .routes import router
from models.gemma import OllamaClient
from models.mlx_vlm_client import MlxVlmClient
from models.embedder import Embedder
from models.freecad_client import FreecadClient
from brain.database import Database
from brain.lookup import BrainLookup
from brain.manufacturing import ManufacturingLookup


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    app.state.ollama = OllamaClient()

    app.state.vlm = MlxVlmClient()
    try:
        print("Loading mlx-vlm model (gemma-3n-E4B-it-4bit)...")
        await asyncio.wait_for(
            asyncio.to_thread(app.state.vlm.load),
            timeout=120.0,
        )
        print("mlx-vlm loaded: gemma-3n-E4B-it-4bit")
    except asyncio.TimeoutError:
        print("WARNING: mlx-vlm load timed out (120s) -- running without VLM")
        app.state.vlm = None
    except Exception as e:
        print(f"WARNING: mlx-vlm failed to load: {e}")
        app.state.vlm = None

    app.state.embedder = Embedder()
    try:
        app.state.embedder.load(str(DATA_DIR / "embeddings" / "standards_embeddings.npz"))
    except Exception as e:
        print(f"WARNING: Embedder failed to load: {e}")
        app.state.embedder = None

    try:
        db = await Database.connect(str(DATA_DIR / "brain.db"))
        app.state.brain_lookup = BrainLookup(db)
        app.state.manufacturing_lookup = ManufacturingLookup(db)
        app.state.db = db
    except FileNotFoundError as e:
        print(f"WARNING: {e}")
        app.state.brain_lookup = None
        app.state.manufacturing_lookup = None
        app.state.db = None

    try:
        await app.state.ollama.health_check()
        print("Ollama connected, models available")
    except Exception as e:
        print(f"WARNING: Ollama not available: {e}")

    app.state.freecad = FreecadClient()
    try:
        connected = await app.state.freecad.health_check()
        if connected:
            print("FreeCAD RPC: connected")
        else:
            app.state.freecad._mock_mode = True
            print("FreeCAD RPC: using mock data (demo mode)")
    except Exception:
        app.state.freecad._mock_mode = True
        print("FreeCAD RPC: using mock data (demo mode)")

    yield

    # --- Shutdown ---
    await app.state.ollama.close()
    if getattr(app.state, "freecad", None):
        await app.state.freecad.close()
    if getattr(app.state, "db", None):
        await app.state.db.close()


app = FastAPI(
    title="ToleranceAI",
    description="AI-powered GD&T copilot for mechanical engineers",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
