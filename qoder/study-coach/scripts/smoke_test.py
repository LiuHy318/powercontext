import asyncio
import json
import uuid

from powercontext.client import PowerContextClient
from powercontext.http import (
    CreateScopeRequest,
    CreateSourceRequest,
    ListMemoryEntriesRequest,
    ListSourcesRequest,
    MemorySearchMode,
    RememberMemoryRequest,
    SearchMemoryRequest,
)

BASE = "http://127.0.0.1:8777"


async def main():
    async with PowerContextClient(BASE) as c:
        print("live:", (await c.get_liveness()).model_dump())
        scope = await c.create_scope(
            CreateScopeRequest(
                title="冒烟测试空间",
                summary="verify roundtrip",
                idempotency_key=f"smoke-{uuid.uuid4()}",
                external_references=[{"kind": "study-recall", "value": "space"}],
            )
        )
        sid = scope.scope_id
        print("scope_id:", sid)

        src = await c.create_source(
            sid,
            CreateSourceRequest(
                source_type="content",
                content={"record_kind": "note", "title": "事务隔离级别", "body": "RR 与 RC", "knowledge_points": ["事务隔离级别"]},
            ),
        )
        print("source_id:", src.source_id, "digest:", src.content_digest[:18])

        read_back = await c.get_source(sid, "content", src.source_id)
        print("source content:", json.dumps(read_back.content, ensure_ascii=False)[:120])

        mem = await c.remember_memory(
            RememberMemoryRequest(
                scope_id=sid,
                kind="review",
                text=json.dumps({"topic": "事务隔离级别", "result": "fail"}, ensure_ascii=False),
            )
        )
        print("memory entry:", mem.entry.citation.entry_id if mem.entry else None, "kind:", mem.entry.kind if mem.entry else None)

        listing = await c.list_memory_entries(ListMemoryEntriesRequest(scope_id=sid))
        print("memory entries:", len(listing.entries))

        hits = await c.search_memory(
            SearchMemoryRequest(scope_id=sid, query="事务隔离级别", mode=MemorySearchMode.FTS, limit=10)
        )
        print("search mode:", hits.mode, "hits:", len(hits.hits))
        for h in hits.hits:
            print("  hit score", round(h.score, 3), "matched_by", h.matched_by, "text", h.text[:40])

        sources = await c.list_sources(sid, ListSourcesRequest())
        print("sources in scope:", len(sources.items))


if __name__ == "__main__":
    asyncio.run(main())
