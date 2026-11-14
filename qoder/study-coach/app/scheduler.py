"""Deterministic, explainable review scheduler.

This module performs no I/O and calls no external model. Given the notes,
preferences, weak points and review history that were read back from PowerContext,
it produces an ordered, budgeted study plan where every item carries a
human-readable Chinese explanation of *why* it was scheduled and the computed
next review interval. The same inputs and ``now`` always yield the same output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.domain import (
    NoteRecord,
    PreferenceRecord,
    ReviewRecord,
    ReviewResult,
    WeakPointRecord,
)

# Leitner-style interval ladder (days) advanced on each successful review.
_INTERVAL_LADDER_DAYS = (1, 2, 4, 7, 15, 30, 60)
_MIN_STEP_MINUTES = 5  # smallest allocation granularity, keeps the plan readable.


def _parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=datetime.now().astimezone().tzinfo)


@dataclass
class PlanFactor:
    name: str
    detail: str
    contribution: float


@dataclass
class PlanItem:
    topic: str
    priority_score: float
    allocated_minutes: int
    next_interval_days: int
    overdue: bool
    ever_reviewed: bool
    days_since_last_review: int | None
    last_result: str | None
    reasons: list[str] = field(default_factory=list)
    factors: list[PlanFactor] = field(default_factory=list)
    related_note_sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "priority_score": round(self.priority_score, 3),
            "allocated_minutes": self.allocated_minutes,
            "next_interval_days": self.next_interval_days,
            "overdue": self.overdue,
            "ever_reviewed": self.ever_reviewed,
            "days_since_last_review": self.days_since_last_review,
            "last_result": self.last_result,
            "reasons": self.reasons,
            "factors": [
                {"name": f.name, "detail": f.detail, "contribution": round(f.contribution, 3)} for f in self.factors
            ],
            "related_note_sources": self.related_note_sources,
        }


@dataclass
class StudyPlan:
    as_of: str
    daily_minutes: int
    total_topics: int
    planned_minutes: int
    items: list[PlanItem]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of,
            "daily_minutes": self.daily_minutes,
            "total_topics": self.total_topics,
            "planned_minutes": self.planned_minutes,
            "items": [i.to_dict() for i in self.items],
            "notes": self.notes,
        }


def _interval_after(last_result: ReviewResult | None, consecutive_masters: int) -> int:
    if last_result is ReviewResult.MASTERED:
        idx = min(consecutive_masters, len(_INTERVAL_LADDER_DAYS) - 1)
        return _INTERVAL_LADDER_DAYS[idx]
    if last_result is ReviewResult.PARTIAL:
        # Stay short on partial success: repeat within two days.
        return 2
    # Never reviewed or last attempt failed → revisit tomorrow.
    return 1


def build_plan(
    *,
    notes: list[NoteRecord],
    preference: PreferenceRecord | None,
    weak_points: list[WeakPointRecord],
    reviews: list[ReviewRecord],
    note_source_map: dict[str, list[str]] | None = None,
    now: datetime,
) -> StudyPlan:
    daily_minutes = preference.daily_minutes if preference else 25
    focus = (preference.focus if preference else "") or ""

    # 1. Assemble the topic universe and link each topic to its source notes.
    note_sources_by_topic = note_source_map or {}
    topics: set[str] = set()
    for note in notes:
        for kp in note.knowledge_points:
            topics.add(kp)
    for wp in weak_points:
        topics.add(wp.topic)
    for rv in reviews:
        topics.add(rv.topic)

    # 2. Fold per-topic history.
    reviews_by_topic: dict[str, list[ReviewRecord]] = {}
    for rv in reviews:
        reviews_by_topic.setdefault(rv.topic, []).append(rv)
    weak_severity: dict[str, int] = {}
    for wp in weak_points:
        weak_severity[wp.topic] = max(weak_severity.get(wp.topic, 0), wp.severity)

    scored: list[PlanItem] = []
    for topic in sorted(topics):
        history = sorted(reviews_by_topic.get(topic, []), key=lambda r: r.reviewed_at)
        last = history[-1] if history else None
        fails = sum(1 for r in history if r.result is ReviewResult.FAIL)
        masters = sum(1 for r in history if r.result is ReviewResult.MASTERED)
        # consecutive mastered streak counted from the most recent review backwards
        streak = 0
        for r in reversed(history):
            if r.result is ReviewResult.MASTERED:
                streak += 1
            else:
                break

        last_dt = _parse_dt(last.reviewed_at) if last else None
        days_since = (now - last_dt).days if last_dt else None
        last_result = last.result if last else None
        next_interval = _interval_after(last_result, streak)
        # A failed item is treated as due immediately (got it wrong -> revisit first);
        # otherwise it becomes due once the Leitner interval has elapsed, or it is new.
        overdue = (
            last is None
            or last_result is ReviewResult.FAIL
            or (days_since is not None and days_since >= next_interval)
        )
        sev = weak_severity.get(topic, 0)

        factors: list[PlanFactor] = []
        reasons: list[str] = []

        score = 0.0
        if last is None:
            score += 5.0
            factors.append(PlanFactor("从未复习", "该知识点尚无复习记录，优先安排首次复习", 5.0))
            reasons.append("从未复习，需要排入首轮复习")
        else:
            forgetting = min(days_since or 0, 30) * 0.3
            if forgetting:
                score += forgetting
                factors.append(PlanFactor("记忆衰减", f"距上次复习 {days_since} 天，按遗忘曲线加权 +{forgetting:.1f}", forgetting))
                reasons.append(f"距上次复习已 {days_since} 天")

        if sev:
            w = 3.0 * sev
            score += w
            factors.append(PlanFactor("薄弱标记", f"被标记为薄弱知识点（程度 {sev}/5），+{w:.1f}", w))
            reasons.append(f"薄弱知识点（程度 {sev}/5）")

        if fails:
            w = 2.0 * fails
            score += w
            factors.append(PlanFactor("历史失败", f"累计复习失败 {fails} 次，+{w:.1f}", w))
            reasons.append(f"复习失败 {fails} 次")

        if masters:
            w = -1.5 * masters
            score += w
            factors.append(PlanFactor("已掌握记录", f"累计掌握 {masters} 次，{-w:.1f} 分以降低优先级", w))
            if last_result is ReviewResult.MASTERED:
                reasons.append(f"最近一次已掌握，间隔延长至 {next_interval} 天")

        if overdue:
            score += 2.0
            factors.append(PlanFactor("已到期", "按当前间隔今天应复习，+2.0", 2.0))

        # Focus alignment nudges matching topics slightly up (still deterministic).
        if focus and focus in topic:
            score += 1.0
            factors.append(PlanFactor("目标聚焦", f"命中偏好聚焦关键词“{focus}”，+1.0", 1.0))
            reasons.append("命中聚焦目标")

        if not reasons:
            reasons.append("常规复习节奏")

        scored.append(
            PlanItem(
                topic=topic,
                priority_score=score,
                allocated_minutes=0,
                next_interval_days=next_interval,
                overdue=overdue,
                ever_reviewed=last is not None,
                days_since_last_review=days_since,
                last_result=last_result.value if last_result else None,
                reasons=reasons,
                factors=factors,
                related_note_sources=[s for s in note_sources_by_topic.get(topic, []) if s],
            )
        )

    # 3. Order: overdue first, then by descending priority, then stable by topic.
    scored.sort(key=lambda i: (not i.overdue, -i.priority_score, i.topic))

    # 4. Allocate the daily budget in 5-minute steps, strongest need first, never
    #    exceeding ``daily_minutes``: at most ``budget // step`` topics are scheduled.
    notes_footer: list[str] = []
    due_items = [i for i in scored if i.overdue]
    if not due_items and scored:
        notes_footer.append("当前没有到期或新增的知识点，以下为最近的常规巩固建议。")

    capacity = daily_minutes // _MIN_STEP_MINUTES
    selected_pool = due_items if due_items else scored
    selected = selected_pool[:capacity]
    if selected:
        for it in selected:
            it.allocated_minutes = _MIN_STEP_MINUTES
        remaining = daily_minutes - _MIN_STEP_MINUTES * len(selected)
        # Distribute the leftover in step-sized rounds by descending priority.
        positive = sorted(selected, key=lambda i: (-i.priority_score, i.topic))
        while remaining >= _MIN_STEP_MINUTES:
            progressed = False
            for it in positive:
                if remaining < _MIN_STEP_MINUTES:
                    break
                it.allocated_minutes += _MIN_STEP_MINUTES
                remaining -= _MIN_STEP_MINUTES
                progressed = True
            if not progressed:
                break
    planned = sum(i.allocated_minutes for i in scored)

    return StudyPlan(
        as_of=now.isoformat(timespec="seconds"),
        daily_minutes=daily_minutes,
        total_topics=len(scored),
        planned_minutes=planned,
        items=[i for i in scored if i.allocated_minutes > 0],
        notes=notes_footer,
    )


__all__ = ["PlanItem", "StudyPlan", "build_plan"]
