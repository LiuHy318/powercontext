"""Thin, honest adapter over the real PowerContext HTTP API client.

Every persistent operation goes through :class:`powercontext.client.PowerContextClient`
against a live PowerContext Server. This layer encodes/decodes StudyRecall domain
records onto PowerContext Scopes (spaces), content Sources (notes) and Memory
entries (preferences, weak points, reviews), and converts any backend or transport
failure into :class:`PowerContextBackendError` so the API never reports a fake success.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx
from powercontext.client import PowerContextClient
from powercontext.client.errors import ClientError, ServerResponseError, TransportError
from powercontext.http import (
    CreateScopeRequest,
    CreateSourceRequest,
    ListMemoryEntriesRequest,
    ListSourcesRequest,
    MemoryEntry,
    MemorySearchMode,
    RememberMemoryRequest,
    ReviseMemoryEntryRequest,
    SearchMemoryRequest,
)

from app.domain import (
    KIND_PREFERENCE,
    KIND_REVIEW,
    KIND_WEAK_POINT,
    SPACE_EXTERNAL_REF_KIND,
    NoteRecord,
    PreferenceRecord,
    ReviewRecord,
    WeakPointRecord,
    encode_source_content,
    encode_text,
)

# PowerContext caps a list page at 100 items; we drain every page via ``next_cursor``.
_PAGE_LIMIT = 100


class PowerContextBackendError(RuntimeError):
    """A real PowerContext backend or transport failure that must be shown to the user."""

    def __init__(self, message: str, *, status: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def _decode_entry(entry: MemoryEntry, model: type[Any]) -> Any | None:
    try:
        return model.model_validate(json.loads(entry.text))
    except (ValueError, TypeError):
        return None


class PowerContextStore:
    def __init__(self, client: PowerContextClient) -> None:
        self._client = client

    # -- health ---------------------------------------------------------------
    async def health(self) -> dict[str, Any]:
        try:
            live = await self._client.get_liveness()
            ready = await self._client.get_readiness()
            return {"liveness": live.status, "readiness": ready.status}
        except (TransportError, httpx.HTTPError, ClientError) as exc:
            raise PowerContextBackendError(f"无法连接 PowerContext 服务：{exc}", status=503) from exc

    # -- spaces (Scopes) ------------------------------------------------------
    async def list_spaces(self) -> list[dict[str, Any]]:
        """Return EVERY StudyRecall space by following the SDK cursor to exhaustion.

        ``list_scopes`` returns a single default 50-item page; reading only the
        first page silently hides older spaces, so we follow ``next_cursor``.
        """
        spaces: list[dict[str, Any]] = []
        try:
            cursor: str | None = None
            while True:
                page = await self._client.list_scopes(
                    external_reference_kind=SPACE_EXTERNAL_REF_KIND,
                    limit=_PAGE_LIMIT,
                    cursor=cursor,
                )
                spaces.extend(
                    {
                        "scope_id": s.scope_id,
                        "title": s.title,
                        "summary": s.summary,
                        "version": s.version,
                    }
                    for s in page.items
                )
                cursor = page.next_cursor
                if not cursor:
                    return spaces
        except (TransportError, httpx.HTTPError, ClientError) as exc:
            raise self._translate(exc)

    async def create_space(self, title: str, summary: str) -> dict[str, Any]:
        try:
            descriptor = await self._client.create_scope(
                CreateScopeRequest(
                    title=title,
                    summary=(summary or title).strip(),
                    idempotency_key=f"study-recall-{uuid.uuid4()}",
                    external_references=[{"kind": SPACE_EXTERNAL_REF_KIND, "value": title}],
                )
            )
            return {"scope_id": descriptor.scope_id, "title": descriptor.title, "summary": descriptor.summary, "version": descriptor.version}
        except (TransportError, httpx.HTTPError, ClientError) as exc:
            raise self._translate(exc)

    async def get_space(self, scope_id: str) -> dict[str, Any] | None:
        try:
            descriptor = await self._client.get_scope(scope_id)
            return {"scope_id": descriptor.scope_id, "title": descriptor.title, "summary": descriptor.summary, "version": descriptor.version}
        except ServerResponseError as exc:
            if exc.status_code == 404:
                return None
            raise self._translate(exc)
        except (TransportError, httpx.HTTPError, ClientError) as exc:
            raise self._translate(exc)

    # -- notes (content Sources) ---------------------------------------------
    async def list_notes(self, scope_id: str) -> list[dict[str, Any]]:
        """Return every note Source in a scope, following the SDK cursor to exhaustion.

        A single ``list_sources`` page holds at most 100 records, so reading only
        the first page silently dropped the 101st persisted note. We keep paging
        until ``next_cursor`` is empty.
        """
        notes: list[dict[str, Any]] = []
        try:
            cursor: str | None = None
            while True:
                page = await self._client.list_sources(
                    scope_id, ListSourcesRequest(limit=_PAGE_LIMIT, cursor=cursor)
                )
                for record in page.items:
                    content = record.content if isinstance(record.content, dict) else {}
                    if content.get("record_kind") != "note":
                        continue
                    notes.append(
                        {
                            "source_id": record.source_id,
                            "content_digest": record.content_digest,
                            "note": NoteRecord.model_validate(content),
                        }
                    )
                cursor = page.next_cursor
                if not cursor:
                    return notes
        except (TransportError, httpx.HTTPError, ClientError) as exc:
            raise self._translate(exc)

    async def add_note(self, scope_id: str, note: NoteRecord) -> dict[str, Any]:
        try:
            record = await self._client.create_source(
                scope_id,
                CreateSourceRequest(source_type="content", content=encode_source_content(note)),
            )
            return {
                "source_id": record.source_id,
                "content_digest": record.content_digest,
                "note": NoteRecord.model_validate(record.content),
            }
        except (TransportError, httpx.HTTPError, ClientError) as exc:
            raise self._translate(exc)

    async def get_note(self, scope_id: str, source_id: str) -> dict[str, Any] | None:
        try:
            record = await self._client.get_source(scope_id, "content", source_id)
            content = record.content if isinstance(record.content, dict) else {}
            if content.get("record_kind") != "note":
                return None
            return {"source_id": record.source_id, "content_digest": record.content_digest, "note": NoteRecord.model_validate(content)}
        except ServerResponseError as exc:
            if exc.status_code == 404:
                return None
            raise self._translate(exc)
        except (TransportError, httpx.HTTPError, ClientError) as exc:
            raise self._translate(exc)

    # -- memory entries (preference / weak points / reviews) ------------------
    async def _entries(self, scope_id: str, kind: str) -> list[MemoryEntry]:
        resp = await self._client.list_memory_entries(ListMemoryEntriesRequest(scope_id=scope_id))
        return [e for e in resp.entries if e.kind == kind]

    async def get_preference(self, scope_id: str) -> PreferenceRecord | None:
        try:
            entries = await self._entries(scope_id, KIND_PREFERENCE)
        except (TransportError, httpx.HTTPError, ClientError) as exc:
            raise self._translate(exc)
        for entry in reversed(entries):
            rec = _decode_entry(entry, PreferenceRecord)
            if rec:
                return rec
        return None

    async def save_preference(self, scope_id: str, record: PreferenceRecord) -> PreferenceRecord:
        try:
            entries = await self._entries(scope_id, KIND_PREFERENCE)
            if entries:
                await self._client.revise_memory_entry(
                    ReviseMemoryEntryRequest(
                        scope_id=scope_id,
                        citation=entries[-1].citation,
                        kind=KIND_PREFERENCE,
                        text=encode_text(record),
                    )
                )
            else:
                await self._client.remember_memory(
                    RememberMemoryRequest(scope_id=scope_id, kind=KIND_PREFERENCE, text=encode_text(record))
                )
            return record
        except (TransportError, httpx.HTTPError, ClientError) as exc:
            raise self._translate(exc)

    async def list_weak_points(self, scope_id: str) -> list[WeakPointRecord]:
        try:
            entries = await self._entries(scope_id, KIND_WEAK_POINT)
        except (TransportError, httpx.HTTPError, ClientError) as exc:
            raise self._translate(exc)
        out = []
        for entry in entries:
            rec = _decode_entry(entry, WeakPointRecord)
            if rec:
                out.append(rec)
        return out

    async def upsert_weak_point(self, scope_id: str, record: WeakPointRecord) -> WeakPointRecord:
        try:
            entries = await self._entries(scope_id, KIND_WEAK_POINT)
            match = None
            for entry in reversed(entries):
                decoded = _decode_entry(entry, WeakPointRecord)
                if decoded and decoded.topic == record.topic:
                    match = entry
                    break
            if match:
                await self._client.revise_memory_entry(
                    ReviseMemoryEntryRequest(scope_id=scope_id, citation=match.citation, kind=KIND_WEAK_POINT, text=encode_text(record))
                )
            else:
                await self._client.remember_memory(
                    RememberMemoryRequest(scope_id=scope_id, kind=KIND_WEAK_POINT, text=encode_text(record))
                )
            return record
        except (TransportError, httpx.HTTPError, ClientError) as exc:
            raise self._translate(exc)

    async def list_reviews(self, scope_id: str) -> list[ReviewRecord]:
        try:
            entries = await self._entries(scope_id, KIND_REVIEW)
        except (TransportError, httpx.HTTPError, ClientError) as exc:
            raise self._translate(exc)
        out = []
        for entry in entries:
            rec = _decode_entry(entry, ReviewRecord)
            if rec:
                out.append(rec)
        return sorted(out, key=lambda r: r.reviewed_at)

    async def add_review(self, scope_id: str, record: ReviewRecord) -> ReviewRecord:
        try:
            await self._client.remember_memory(
                RememberMemoryRequest(scope_id=scope_id, kind=KIND_REVIEW, text=encode_text(record))
            )
            return record
        except (TransportError, httpx.HTTPError, ClientError) as exc:
            raise self._translate(exc)

    # -- retrieval with real citations ---------------------------------------
    async def search(self, scope_id: str, query: str, limit: int = 10) -> dict[str, Any]:
        """Keyword (FTS) retrieval over PowerContext Memory plus local note matching.

        Only full-text search is used and reported honestly as ``fts``; no vector or
        semantic claim is made because no embedding model is configured.
        """
        try:
            resp = await self._client.search_memory(
                SearchMemoryRequest(scope_id=scope_id, query=query, mode=MemorySearchMode.FTS, limit=limit)
            )
        except (TransportError, httpx.HTTPError, ClientError) as exc:
            raise self._translate(exc)
        memory_hits = [
            {
                "type": "memory",
                "text": hit.text,
                "score": hit.score,
                "matched_by": [m.value for m in hit.matched_by],
                "citation": {
                    "entry_id": hit.citation.entry_id,
                    "memory_ref": hit.citation.memory_ref.model_dump(mode="json"),
                },
            }
            for hit in resp.hits
        ]
        note_hits = []
        q = query.strip().lower()
        for item in await self.list_notes(scope_id):
            note: NoteRecord = item["note"]
            hay = f"{note.title} {note.body} {' '.join(note.knowledge_points)}".lower()
            if q and q in hay:
                note_hits.append(
                    {
                        "type": "note",
                        "title": note.title,
                        "snippet": note.body[:120],
                        "source_citation": {
                            "scope_id": scope_id,
                            "source_id": item["source_id"],
                            "content_digest": item["content_digest"],
                        },
                    }
                )
        return {"mode": resp.mode.value if resp.mode else "fts", "memory_hits": memory_hits, "note_hits": note_hits}

    @staticmethod
    def _translate(exc: Exception) -> PowerContextBackendError:
        if isinstance(exc, ServerResponseError):
            detail = exc.server_message or str(exc)
            code = f"（{exc.code}）" if exc.code else ""
            return PowerContextBackendError(
                f"PowerContext 返回错误 {exc.status_code}{code}：{detail}",
                status=502,
            )
        if isinstance(exc, TransportError):
            return PowerContextBackendError(
                f"无法访问 PowerContext 服务（请确认服务已启动）：{exc}",
                status=503,
            )
        return PowerContextBackendError(f"PowerContext 调用失败：{exc}", status=502)


__all__ = ["PowerContextBackendError", "PowerContextStore"]
