"""Fast unit tests for the deterministic scheduler (no PowerContext needed)."""

from __future__ import annotations

from datetime import datetime

from app.domain import NoteRecord, PreferenceRecord, ReviewRecord, ReviewResult, WeakPointRecord
from app.scheduler import build_plan

NOW = datetime.fromisoformat("2026-11-15T12:00:00+09:00")


def _note(title: str) -> NoteRecord:
    return NoteRecord(title=title, body="b", origin="o", knowledge_points=[title], created_at="2026-11-01T00:00:00+09:00")


def _pref(minutes: int = 25) -> PreferenceRecord:
    return PreferenceRecord(daily_minutes=minutes, focus="", updated_at="2026-11-01T00:00:00+09:00")


def _wp(topic: str, sev: int) -> WeakPointRecord:
    return WeakPointRecord(topic=topic, severity=sev, updated_at="2026-11-01T00:00:00+09:00")


def test_no_inputs_yields_empty_plan() -> None:
    plan = build_plan(notes=[], preference=None, weak_points=[], reviews=[], now=NOW)
    assert plan.items == []
    assert plan.total_topics == 0
    assert plan.daily_minutes == 25  # documented default


def test_weaker_never_reviewed_topic_ranks_first() -> None:
    plan = build_plan(
        notes=[_note("事务隔离级别"), _note("索引选择")],
        preference=_pref(),
        weak_points=[_wp("事务隔离级别", 5), _wp("索引选择", 2)],
        reviews=[],
        now=NOW,
    )
    assert plan.items[0].topic == "事务隔离级别"


def test_determinism_same_inputs() -> None:
    args = dict(
        notes=[_note("a"), _note("b")],
        preference=_pref(),
        weak_points=[_wp("a", 3)],
        reviews=[ReviewRecord(topic="b", result=ReviewResult.FAIL, reviewed_at="2026-11-10T00:00:00+09:00")],
        now=NOW,
    )
    assert build_plan(**args).to_dict() == build_plan(**args).to_dict()


def test_budget_is_respected() -> None:
    notes = [_note(f"t{i}") for i in range(10)]
    plan = build_plan(notes=notes, preference=_pref(20), weak_points=[_wp("t0", 5)], reviews=[], now=NOW)
    assert plan.planned_minutes <= 20


def test_mastery_grows_interval_and_fail_resets_it() -> None:
    mastered = build_plan(
        notes=[_note("x")],
        preference=_pref(),
        weak_points=[],
        reviews=[
            ReviewRecord(topic="x", result=ReviewResult.MASTERED, reviewed_at="2026-11-01T00:00:00+09:00"),
            ReviewRecord(topic="x", result=ReviewResult.MASTERED, reviewed_at="2026-11-05T00:00:00+09:00"),
        ],
        now=NOW,
    )
    # two consecutive masters -> ladder index 2 == 4 days
    assert mastered.items == [] or mastered.items[0].next_interval_days >= 4

    failed = build_plan(
        notes=[_note("x")],
        preference=_pref(),
        weak_points=[],
        reviews=[ReviewRecord(topic="x", result=ReviewResult.FAIL, reviewed_at="2026-11-14T00:00:00+09:00")],
        now=NOW,
    )
    item = failed.items[0]
    assert item.next_interval_days == 1
    assert any("复习失败" in r for r in item.reasons)
