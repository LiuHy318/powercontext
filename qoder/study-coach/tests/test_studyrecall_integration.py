"""Real integration tests against a live PowerContext Server.

Covers the checks required by the brief: PowerContext write/read, plan using past
memory, scope isolation, restart recovery, empty-state experience, invalid input and
backend unavailability. Nothing here mocks the backend.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from scripts.pc_server import PowerContextServer
from tests.conftest import unique


def _make_space(client: TestClient, title: str = "空间") -> str:
    resp = client.post("/api/spaces", json={"title": unique(title), "summary": "集成测试空间"})
    assert resp.status_code == 201, resp.text
    return resp.json()["scope_id"]


def _add_note(client: TestClient, scope_id: str, title: str, points: list[str], body: str = "内容") -> str:
    resp = client.post(
        f"/api/spaces/{scope_id}/notes",
        json={"title": title, "body": body, "origin": "集成测试", "knowledge_points": points},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["source_id"]


def test_health_reports_real_backend(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["liveness"] == "ok"
    assert body["readiness"] == "ready"
    assert body["powercontext_url"].startswith("http://127.0.0.1:")


def test_powercontext_write_and_read_roundtrip(client: TestClient) -> None:
    scope_id = _make_space(client, "读写")
    src = _add_note(client, scope_id, "事务隔离级别", ["事务隔离级别", "幻读"], body="RC 与 RR")
    # read back from PowerContext Sources
    notes = client.get(f"/api/spaces/{scope_id}/notes").json()
    assert len(notes) == 1
    assert notes[0]["source_id"] == src
    assert notes[0]["content_digest"].startswith("sha256:")
    assert notes[0]["note"]["knowledge_points"] == ["事务隔离级别", "幻读"]
    # read back a Memory entry
    rev = client.post(
        f"/api/spaces/{scope_id}/reviews",
        json={"topic": "事务隔离级别", "result": "fail", "score": 1, "note": "没记住"},
    )
    assert rev.status_code == 201
    reviews = client.get(f"/api/spaces/{scope_id}/reviews").json()
    assert reviews[0]["topic"] == "事务隔离级别"
    assert reviews[0]["result"] == "fail"


def test_preference_persisted_and_reused(client: TestClient) -> None:
    scope_id = _make_space(client, "偏好")
    assert client.get(f"/api/spaces/{scope_id}/preference").json()["preference"] is None
    put = client.put(f"/api/spaces/{scope_id}/preference", json={"daily_minutes": 25, "focus": "数据库"})
    assert put.status_code == 200 and put.json()["preference"]["daily_minutes"] == 25
    # update the same preference entry (revise), not accumulate duplicates
    client.put(f"/api/spaces/{scope_id}/preference", json={"daily_minutes": 40, "focus": "索引"})
    pref = client.get(f"/api/spaces/{scope_id}/preference").json()["preference"]
    assert pref["daily_minutes"] == 40


def test_empty_space_initial_experience(client: TestClient) -> None:
    scope_id = _make_space(client, "空空间")
    plan = client.post(f"/api/spaces/{scope_id}/plan", json={})
    assert plan.status_code == 200
    body = plan.json()
    assert body["items"] == []
    assert body["total_topics"] == 0
    assert body["daily_minutes"] == 25  # documented default when no preference saved


def test_plan_uses_past_memory_and_shifts_on_mastery(client: TestClient) -> None:
    scope_id = _make_space(client, "计划")
    client.put(f"/api/spaces/{scope_id}/preference", json={"daily_minutes": 25, "focus": ""})
    _add_note(client, scope_id, "事务隔离级别", ["事务隔离级别"])
    _add_note(client, scope_id, "索引选择", ["索引选择"])
    client.post(f"/api/spaces/{scope_id}/weak-points", json={"topic": "事务隔离级别", "severity": 5})
    client.post(f"/api/spaces/{scope_id}/weak-points", json={"topic": "索引选择", "severity": 4})

    # A fixed far-future horizon makes every topic overdue regardless of wall-clock,
    # so the ordering/interval assertions are deterministic.
    horizon = "2027-01-01T00:00:00+00:00"
    plan1 = client.post(f"/api/spaces/{scope_id}/plan", json={"as_of": horizon}).json()
    assert plan1["items"][0]["topic"] == "事务隔离级别"  # weakest, never reviewed -> scheduled first
    assert plan1["items"][0]["allocated_minutes"] >= plan1["items"][1]["allocated_minutes"]
    base_interval = next(i for i in plan1["items"] if i["topic"] == "事务隔离级别")["next_interval_days"]

    # Record a FAILURE on 索引选择 and regenerate: past memory raises its priority.
    client.post(f"/api/spaces/{scope_id}/reviews", json={"topic": "索引选择", "result": "fail", "score": 1})
    plan2 = client.post(f"/api/spaces/{scope_id}/plan", json={"as_of": horizon}).json()
    failed = next(i for i in plan2["items"] if i["topic"] == "索引选择")
    assert any("复习失败" in r for r in failed["reasons"])
    assert failed["priority_score"] > plan1["items"][0]["priority_score"]  # failure now outranks it

    # Record MASTERY on 事务隔离级别: its next interval must grow.
    client.post(f"/api/spaces/{scope_id}/reviews", json={"topic": "事务隔离级别", "result": "mastered", "score": 5})
    plan3 = client.post(f"/api/spaces/{scope_id}/plan", json={"as_of": horizon}).json()
    mastered = next(i for i in plan3["items"] if i["topic"] == "事务隔离级别")
    assert mastered["next_interval_days"] > base_interval
    assert any("已掌握" in r for r in mastered["reasons"])


def test_plan_is_deterministic_for_same_inputs(client: TestClient) -> None:
    scope_id = _make_space(client, "确定性")
    client.put(f"/api/spaces/{scope_id}/preference", json={"daily_minutes": 25, "focus": ""})
    _add_note(client, scope_id, "覆盖索引", ["覆盖索引"])
    _add_note(client, scope_id, "最左前缀", ["最左前缀"])
    as_of = "2027-01-01T08:00:00+00:00"
    a = client.post(f"/api/spaces/{scope_id}/plan", json={"as_of": as_of}).json()
    b = client.post(f"/api/spaces/{scope_id}/plan", json={"as_of": as_of}).json()
    assert a["items"] == b["items"]


def test_scope_isolation(client: TestClient) -> None:
    scope_a = _make_space(client, "隔离A")
    scope_b = _make_space(client, "隔离B")
    _add_note(client, scope_a, "锁机制", ["锁机制"])
    client.post(f"/api/spaces/{scope_a}/reviews", json={"topic": "锁机制", "result": "fail"})

    notes_b = client.get(f"/api/spaces/{scope_b}/notes").json()
    reviews_b = client.get(f"/api/spaces/{scope_b}/reviews").json()
    plan_b = client.post(f"/api/spaces/{scope_b}/plan", json={}).json()
    assert notes_b == []
    assert reviews_b == []
    assert all(i["topic"] != "锁机制" for i in plan_b["items"])
    # and it is present for A
    assert any(n["note"]["title"] == "锁机制" for n in client.get(f"/api/spaces/{scope_a}/notes").json())


def test_search_returns_real_citations(client: TestClient) -> None:
    scope_id = _make_space(client, "检索")
    src = _add_note(client, scope_id, "间隙锁", ["幻读"], body="间隙锁缓解幻读")
    client.post(f"/api/spaces/{scope_id}/reviews", json={"topic": "幻读", "result": "fail"})
    resp = client.get(f"/api/spaces/{scope_id}/search", params={"q": "幻读"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "fts"  # honest full-text mode, never a fabricated semantic claim
    assert any(h["source_citation"]["source_id"] == src for h in body["note_hits"])
    assert all(h["matched_by"] == ["fts"] for h in body["memory_hits"])


def test_invalid_inputs_are_visible(client: TestClient) -> None:
    scope_id = _make_space(client, "非法")
    # pydantic validation (FastAPI 422), not a fake success
    assert client.put(f"/api/spaces/{scope_id}/preference", json={"daily_minutes": 0}).status_code == 422
    assert client.put(f"/api/spaces/{scope_id}/preference", json={"daily_minutes": 99999}).status_code == 422
    assert client.post(f"/api/spaces/{scope_id}/notes", json={"title": "  ", "body": "x", "knowledge_points": []}).status_code == 422
    assert client.post(f"/api/spaces/{scope_id}/reviews", json={"topic": "x", "result": "not-a-result"}).status_code == 422
    # blank search keyword -> explicit 400 error
    bad = client.get(f"/api/spaces/{scope_id}/search", params={"q": "   "})
    assert bad.status_code == 400
    assert "不能为空" in bad.json()["error"]


def test_backend_unavailable_is_not_faked(pc_server: PowerContextServer) -> None:
    # Point the app at a dead port; the failure must surface, never be masked.
    dead = create_app("http://127.0.0.1:1")
    with TestClient(dead) as client:
        resp = client.get("/api/health")
    assert resp.status_code in (502, 503)
    assert "PowerContext" in resp.json()["error"]


def test_restart_recovery(pc_server: PowerContextServer) -> None:
    title = unique("重启")
    with TestClient(create_app(pc_server.base_url)) as before:
        scope_id = before.post("/api/spaces", json={"title": title, "summary": "重启恢复"}).json()["scope_id"]
        before.post(
            f"/api/spaces/{scope_id}/notes",
            json={"title": "MVCC", "body": "多版本并发控制", "origin": "测试", "knowledge_points": ["MVCC"]},
        )
        before.post(f"/api/spaces/{scope_id}/reviews", json={"topic": "MVCC", "result": "fail"})
        before.put(f"/api/spaces/{scope_id}/preference", json={"daily_minutes": 30, "focus": "并发"})

    # Fully restart the PowerContext process (same on-disk SQLite home).
    pc_server.restart()

    with TestClient(create_app(pc_server.base_url)) as after:
        space = after.get(f"/api/spaces/{scope_id}").json()
        assert space["scope_id"] == scope_id
        notes = after.get(f"/api/spaces/{scope_id}/notes").json()
        assert any(n["note"]["title"] == "MVCC" for n in notes)
        reviews = after.get(f"/api/spaces/{scope_id}/reviews").json()
        assert reviews and reviews[0]["result"] == "fail"
        pref = after.get(f"/api/spaces/{scope_id}/preference").json()["preference"]
        assert pref["daily_minutes"] == 30


def test_notes_pagination_beyond_one_page(client: TestClient) -> None:
    """Regression for the confirmed 101-saved / 100-listed loss.

    A ``list_sources`` page caps at 100, so a single page silently dropped the
    101st persisted note. Persist more than one page and require the app to follow
    the SDK cursor until every note is listed AND reaches the plan.
    """
    scope_id = _make_space(client, "分页")
    total = 101
    topics = [f"知识点{i:03d}" for i in range(total)]
    for i, kp in enumerate(topics):
        _add_note(client, scope_id, f"笔记{i:03d}", [kp], body=f"正文{i}")

    notes = client.get(f"/api/spaces/{scope_id}/notes").json()
    # Exactly the number we saved — no page-truncation loss.
    assert len(notes) == total, f"expected {total} notes, got {len(notes)}"
    listed = {n["note"]["knowledge_points"][0] for n in notes}
    assert listed == set(topics)
    # The final (101st) note is not the first page's tail; confirm a late one is present.
    assert topics[-1] in listed and topics[100] in listed

    # The plan is fed every note, not just the first page.
    plan = client.post(f"/api/spaces/{scope_id}/plan", json={"as_of": "2027-01-01T00:00:00+00:00"}).json()
    assert plan["total_topics"] == total


def test_spaces_pagination_beyond_one_page(client: TestClient) -> None:
    """Regression proving ``list_spaces`` traverses the SDK cursor, not just its limit.

    We now request ``limit=100`` per page, so more than 100 spaces require a second
    page fetched via ``next_cursor``. Create 101 spaces and assert every one is listed.
    """
    total = 101
    titles = [unique(f"空间{i:03d}") for i in range(total)]
    created = []
    for title in titles:
        resp = client.post("/api/spaces", json={"title": title, "summary": "分页测试"})
        assert resp.status_code == 201, resp.text
        created.append(resp.json()["scope_id"])

    listed = client.get("/api/spaces").json()
    listed_ids = {s["scope_id"] for s in listed}
    # Every one of the 101 spaces (> single 100-item page) must be reachable via the cursor.
    assert all(cid in listed_ids for cid in created), "some spaces were lost to page truncation"
    assert len(listed) >= total


