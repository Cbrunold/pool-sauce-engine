"""Pool Sauce Engine — FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import cue_options, detect, debrief, plan

app = FastAPI(
    title="Pool Sauce Engine",
    description="Rō — shot intelligence API for The Way of the Pool Player.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # PWA on same LAN; tighten for production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(plan.router, prefix="/api")
app.include_router(debrief.router, prefix="/api")
app.include_router(detect.router, prefix="/api")
app.include_router(cue_options.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}
