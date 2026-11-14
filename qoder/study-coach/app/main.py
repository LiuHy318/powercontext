"""StudyRecall FastAPI application.

Serves a lightweight Chinese web UI plus a JSON API. All persistent state is stored
in a real PowerContext Server via :class:`app.powercontext_store.PowerContextStore`:
spaces are Scopes, notes are content Sources, and preferences / weak points / reviews
are Memory entries. If PowerContext is unreachable the API returns a visible error
instead of a fabricated success.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import AppConfig, create_client
from app.domain import (
    NoteCreate,
    NoteRecord,
    PlanRequest,
    PreferenceRecord,
    PreferenceUpdate,
    ReviewCreate,
    ReviewRecord,
    SpaceCreate,
    WeakPointRecord,
    WeakPointUpdate,
    utc_now_iso,
)
from app.powercontext_store import PowerContextBackendError, PowerContextStore
from app.sample_data import (
    SAMPLE_DAILY_MINUTES,
    SAMPLE_NOTES,
    SAMPLE_SPACE_SUMMARY,
    SAMPLE_SPACE_TITLE,
    SAMPLE_WEAK_POINTS,
)
from app.scheduler import build_plan

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def create_app(server_url: str | None = None) -> FastAPI:
    config = AppConfig.from_env() if server_url is None else AppConfig(server_url=server_url.rstrip("/"), request_timeout=20.0)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        client, http_client = create_client(config)
        app.state.store = PowerContextStore(client)
        app.state.server_url = config.server_url
        try:
            yield
        finally:
            await client.__aexit__(None, None, None)
            await http_client.aclose()

    app = FastAPI(title="StudyRecall 研学记忆教练", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(PowerContextBackendError)
    async def _backend_error_handler(_: Request, exc: PowerContextBackendError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content={"error": exc.message, "backend": "powercontext"})

    def _store(request: Request) -> PowerContextStore:
        return request.app.state.store

    # -- health / meta --------------------------------------------------------
    @app.get("/api/health")
    async def health(request: Request) -> dict[str, Any]:
        return {"powercontext_url": request.app.state.server_url, **(await _store(request).health())}

    # -- spaces ---------------------------------------------------------------
    @app.get("/api/spaces")
    async def list_spaces(request: Request) -> list[dict[str, Any]]:
        return await _store(request).list_spaces()

    @app.post("/api/spaces", status_code=201)
    async def create_space(payload: SpaceCreate, request: Request) -> dict[str, Any]:
        return await _store(request).create_space(payload.title, payload.summary)

    @app.get("/api/spaces/{scope_id}")
    async def get_space(scope_id: str, request: Request) -> dict[str, Any]:
        space = await _store(request).get_space(scope_id)
        if space is None:
            raise PowerContextBackendError(f"未找到学习空间：{scope_id}", status=404)
        return space

    # -- notes ----------------------------------------------------------------
    @app.get("/api/spaces/{scope_id}/notes")
    async def list_notes(scope_id: str, request: Request) -> list[dict[str, Any]]:
        items = await _store(request).list_notes(scope_id)
        return [
            {
                "source_id": it["source_id"],
                "content_digest": it["content_digest"],
                "note": it["note"].model_dump(mode="json"),
            }
            for it in items
        ]

    @app.post("/api/spaces/{scope_id}/notes", status_code=201)
    async def add_note(scope_id: str, payload: NoteCreate, request: Request) -> dict[str, Any]:
        record = NoteRecord(
            title=payload.title,
            body=payload.body,
            origin=payload.origin or "自编笔记",
            knowledge_points=payload.knowledge_points,
            created_at=utc_now_iso(),
        )
        created = await _store(request).add_note(scope_id, record)
        return {"source_id": created["source_id"], "content_digest": created["content_digest"], "note": created["note"].model_dump(mode="json")}

    # -- preferences ----------------------------------------------------------
    @app.get("/api/spaces/{scope_id}/preference")
    async def get_preference(scope_id: str, request: Request) -> dict[str, Any]:
        pref = await _store(request).get_preference(scope_id)
        return {"preference": pref.model_dump(mode="json") if pref else None}

    @app.put("/api/spaces/{scope_id}/preference")
    async def put_preference(scope_id: str, payload: PreferenceUpdate, request: Request) -> dict[str, Any]:
        record = PreferenceRecord(
            daily_minutes=payload.daily_minutes,
            focus=payload.focus,
            updated_at=utc_now_iso(),
        )
        saved = await _store(request).save_preference(scope_id, record)
        return {"preference": saved.model_dump(mode="json")}

    # -- weak points ----------------------------------------------------------
    @app.get("/api/spaces/{scope_id}/weak-points")
    async def list_weak_points(scope_id: str, request: Request) -> list[dict[str, Any]]:
        items = await _store(request).list_weak_points(scope_id)
        return [w.model_dump(mode="json") for w in items]

    @app.post("/api/spaces/{scope_id}/weak-points", status_code=201)
    async def upsert_weak_point(scope_id: str, payload: WeakPointUpdate, request: Request) -> dict[str, Any]:
        record = WeakPointRecord(topic=payload.topic, severity=payload.severity, note=payload.note, updated_at=utc_now_iso())
        saved = await _store(request).upsert_weak_point(scope_id, record)
        return saved.model_dump(mode="json")

    # -- reviews --------------------------------------------------------------
    @app.get("/api/spaces/{scope_id}/reviews")
    async def list_reviews(scope_id: str, request: Request) -> list[dict[str, Any]]:
        items = await _store(request).list_reviews(scope_id)
        return [r.model_dump(mode="json") for r in items]

    @app.post("/api/spaces/{scope_id}/reviews", status_code=201)
    async def add_review(scope_id: str, payload: ReviewCreate, request: Request) -> dict[str, Any]:
        record = ReviewRecord(
            topic=payload.topic,
            result=payload.result,
            score=payload.score,
            note=payload.note,
            reviewed_at=utc_now_iso(),
        )
        saved = await _store(request).add_review(scope_id, record)
        return saved.model_dump(mode="json")

    # -- plan (memory-based, deterministic, explainable) ----------------------
    @app.post("/api/spaces/{scope_id}/plan")
    async def make_plan(scope_id: str, payload: PlanRequest, request: Request) -> dict[str, Any]:
        store = _store(request)
        note_items = await store.list_notes(scope_id)
        notes = [it["note"] for it in note_items]
        note_source_map: dict[str, list[str]] = {}
        for it in note_items:
            for kp in it["note"].knowledge_points:
                note_source_map.setdefault(kp, []).append(it["source_id"])
        preference = await store.get_preference(scope_id)
        weak_points = await store.list_weak_points(scope_id)
        reviews = await store.list_reviews(scope_id)
        now = datetime.fromisoformat(payload.as_of) if payload.as_of else datetime.now().astimezone()
        if now.tzinfo is None:
            now = now.replace(tzinfo=datetime.now().astimezone().tzinfo)
        plan = build_plan(
            notes=notes,
            preference=preference,
            weak_points=weak_points,
            reviews=reviews,
            note_source_map=note_source_map,
            now=now,
        )
        return plan.to_dict()

    # -- retrieval with real citations ---------------------------------------
    @app.get("/api/spaces/{scope_id}/search")
    async def search(scope_id: str, request: Request, q: str = "", limit: int = 10) -> dict[str, Any]:
        if not q.strip():
            raise PowerContextBackendError("检索关键词不能为空", status=400)
        return await _store(request).search(scope_id, q, limit=max(1, min(limit, 50)))

    # -- seed helper (synthetic sample) --------------------------------------
    @app.post("/api/seed-sample")
    async def seed_sample(request: Request) -> dict[str, Any]:
        store = _store(request)
        space = await store.create_space(SAMPLE_SPACE_TITLE, SAMPLE_SPACE_SUMMARY)
        sid = space["scope_id"]
        await store.save_preference(
            sid,
            PreferenceRecord(daily_minutes=SAMPLE_DAILY_MINUTES, focus="数据库", updated_at=utc_now_iso()),
        )
        created_notes = []
        for note in SAMPLE_NOTES:
            created = await store.add_note(
                sid,
                NoteRecord(
                    title=note.title,
                    body=note.body,
                    origin=note.origin,
                    knowledge_points=list(note.knowledge_points),
                    created_at=utc_now_iso(),
                ),
            )
            created_notes.append(created["source_id"])
        for topic, severity in SAMPLE_WEAK_POINTS:
            await store.upsert_weak_point(sid, WeakPointRecord(topic=topic, severity=severity, note="合成自评薄弱点", updated_at=utc_now_iso()))
        return {"space": space, "note_source_ids": created_notes, "daily_minutes": SAMPLE_DAILY_MINUTES}

    # -- static UI ------------------------------------------------------------
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))

    return app


app = create_app()


__all__ = ["create_app"]
