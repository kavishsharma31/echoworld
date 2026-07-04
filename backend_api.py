"""FastAPI host for EchoWorld's server-side memory engine and web build."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend_adapter import DirectBackendAdapter


load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent
WEB_DIST = ROOT_DIR / "web_dist"

app = FastAPI(title="EchoWorld", version="2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8787",
        "http://localhost:8787",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

backend = DirectBackendAdapter()


class TalkRequest(BaseModel):
    npc_key: str = Field(min_length=1, max_length=40)
    message: str = Field(min_length=1, max_length=220)
    session_id: str = Field(min_length=1, max_length=160)
    allow_hearsay: bool = True
    is_first_meeting: bool = False
    verified_memory: str | list[str] | None = None
    memory_forbidden: bool = False
    attitude: str = "neutral"
    hearsay_session_id: str | None = None
    promise_context: str = ""
    forced_callout: str = ""
    day: int = Field(default=1, ge=1, le=9999)


class BribeRequest(BaseModel):
    npc_key: str = Field(min_length=1, max_length=40)


class EndDayRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=160)
    run_id: str = Field(min_length=1, max_length=120)


class PromiseRequest(BaseModel):
    day: int = Field(ge=1, le=9999)
    session_id: str = Field(min_length=1, max_length=160)


def _payload(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "service": "EchoWorld"}


@app.post("/api/talk")
async def talk(request: TalkRequest) -> dict[str, Any]:
    try:
        result = await backend.talk(_payload(request))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Talk failed: {exc}") from exc
    return result


@app.post("/api/bribe")
async def bribe(request: BribeRequest) -> dict[str, Any]:
    try:
        return await backend.bribe(request.npc_key)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Bribe failed: {exc}") from exc


@app.post("/api/endday")
async def endday(request: EndDayRequest) -> dict[str, Any]:
    try:
        return await backend.endday(request.session_id, request.run_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"End Day failed: {exc}") from exc


@app.post("/api/reset")
async def reset() -> dict[str, Any]:
    try:
        return await backend.reset()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Reset failed: {exc}") from exc


@app.post("/api/promise/mira-no-trouble")
async def make_mira_promise(request: PromiseRequest) -> dict[str, Any]:
    try:
        return await backend.make_promise(request.day, request.session_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Promise failed: {exc}") from exc


@app.get("/api/promises")
async def promises() -> dict[str, Any]:
    return await backend.get_promises()


@app.get("/api/events")
async def events() -> dict[str, Any]:
    """Return compact structured summaries, never prompts, keys, or secrets."""
    return await backend.get_events()


@app.get("/api/attitudes")
async def attitudes() -> dict[str, Any]:
    return await backend.get_attitudes()


if WEB_DIST.is_dir() and (WEB_DIST / "index.html").is_file():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web-game")
else:

    @app.get("/", response_class=HTMLResponse)
    async def missing_web_build() -> str:
        return (
            "<!doctype html><html><head><title>EchoWorld</title></head>"
            "<body style='background:#05080d;color:#e9f8f5;font-family:monospace;"
            "padding:3rem'><h1>EchoWorld</h1><p>Web build missing. "
            "Run scripts/build_web.ps1 first.</p></body></html>"
        )
