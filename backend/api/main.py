from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router
from models.gemma import OllamaClient
from models.embedder import Embedder
from brain.database import Database
from brain.lookup import BrainLookup
from brain.manufacturing import ManufacturingLookup


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    app.state.ollama = OllamaClient()

    app.state.embedder = Embedder()
    try:
        app.state.embedder.load()
    except Exception as e:
        print(f"WARNING: Embedder failed to load: {e}")
        app.state.embedder = None

    try:
        db = await Database.connect("data/brain.db")
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

    yield

    # --- Shutdown ---
    await app.state.ollama.close()
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
