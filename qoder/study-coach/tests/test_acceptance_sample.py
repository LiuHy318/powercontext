"""End-to-end run of the brief's acceptance sample against real PowerContext.

Synthetic learner: preparing a database exam, 25 min/day, weak points 事务隔离级别
and 索引选择. Import the two notes, record one failure, generate a plan (failure is
prioritised and PowerContext memory + source citations are shown), then record
mastery and regenerate to see the ordering/interval change.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_acceptance_walkthrough(client: TestClient) -> None:
    seed = client.post("/api/seed-sample")
    assert seed.status_code == 200, seed.text
    scope_id = seed.json()["space"]["scope_id"]
    assert len(seed.json()["note_source_ids"]) == 2

    # Preference reflects 25 minutes/day.
    pref = client.get(f"/api/spaces/{scope_id}/preference").json()["preference"]
    assert pref["daily_minutes"] == 25

    # Record ONE failed review of a weak point.
    fail = client.post(
        f"/api/spaces/{scope_id}/reviews",
        json={"topic": "事务隔离级别", "result": "fail", "score": 1, "note": "把 RC 和 RR 记混了"},
    )
    assert fail.status_code == 201

    horizon = "2027-01-01T00:00:00+00:00"
    plan1 = client.post(f"/api/spaces/{scope_id}/plan", json={"as_of": horizon}).json()
    top = next(i for i in plan1["items"] if i["topic"] == "事务隔离级别")
    assert any("复习失败" in r for r in top["reasons"])
    base_interval = top["next_interval_days"]
    # the plan is drawn from real PowerContext state (notes link back to Sources)
    assert top["related_note_sources"], "expected the plan item to reference a PowerContext note Source"

    # Retrieval shows the memory entry and the note with a real citation.
    search = client.get(f"/api/spaces/{scope_id}/search", params={"q": "事务隔离级别"}).json()
    assert search["mode"] == "fts"
    assert search["note_hits"] and search["note_hits"][0]["source_citation"]["content_digest"].startswith("sha256:")

    # Read the note straight back out of PowerContext Sources (real provenance).
    notes = client.get(f"/api/spaces/{scope_id}/notes").json()
    isolation_note = next(n for n in notes if n["note"]["title"] == "事务隔离级别")
    assert any(n["source_id"] == isolation_note["source_id"] for n in notes)

    # Now record MASTERY and regenerate: the next interval grows from the failed baseline.
    client.post(f"/api/spaces/{scope_id}/reviews", json={"topic": "事务隔离级别", "result": "mastered", "score": 5})
    plan2 = client.post(f"/api/spaces/{scope_id}/plan", json={"as_of": horizon}).json()
    mastered = next(i for i in plan2["items"] if i["topic"] == "事务隔离级别")
    assert mastered["last_result"] == "mastered"
    assert mastered["next_interval_days"] > base_interval
    assert any("已掌握" in r for r in mastered["reasons"])
