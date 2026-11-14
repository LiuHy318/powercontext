"""Application domain models and PowerContext record codecs.

The classes here are two things at once:
  * request/response shapes for the StudyRecall HTTP API, and
  * the payloads that get encoded into real PowerContext content Sources and
    Memory entries (``kind`` + JSON ``text``).

Nothing in this module performs storage itself; see :mod:`app.powercontext_store`.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# --- PowerContext classification constants -----------------------------------
# Notes are durable content Sources; every other record is a Memory entry whose
# ``kind`` groups it. These strings are what we send to the real PowerContext API.
SPACE_EXTERNAL_REF_KIND = "study-recall-space"
NOTE_RECORD_KIND = "note"
KIND_PREFERENCE = "preference"
KIND_WEAK_POINT = "weak-point"
KIND_REVIEW = "review"


def utc_now_iso() -> str:
    # Microsecond precision keeps ordering stable even for rapid successive reviews.
    return datetime.now(timezone.utc).isoformat()


class ReviewResult(str, Enum):
    FAIL = "fail"          # 忘记 / 未掌握
    PARTIAL = "partial"    # 部分掌握
    MASTERED = "mastered"  # 已掌握


# --- API request models ------------------------------------------------------
class SpaceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    summary: str = Field(default="", max_length=300)

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("空间标题不能为空")
        return v


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=20000)
    origin: str = Field(default="", max_length=300, description="来源标识，例如教材章节或自编说明")
    knowledge_points: list[str] = Field(default_factory=list, max_length=40)

    @field_validator("title", "body")
    @classmethod
    def _strip_nonempty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("标题与正文不能为空")
        return v

    @field_validator("knowledge_points")
    @classmethod
    def _clean_points(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for item in v:
            s = item.strip()
            if s and s not in out:
                out.append(s)
        return out


class PreferenceUpdate(BaseModel):
    daily_minutes: int = Field(ge=1, le=600, description="每天用于复习的分钟数")
    focus: str = Field(default="", max_length=200)

    @field_validator("focus")
    @classmethod
    def _clean_focus(cls, v: str) -> str:
        return v.strip()


class WeakPointUpdate(BaseModel):
    topic: str = Field(min_length=1, max_length=120)
    severity: int = Field(ge=1, le=5, description="薄弱程度 1-5")
    note: str = Field(default="", max_length=300)

    @field_validator("topic")
    @classmethod
    def _clean_topic(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("知识点不能为空")
        return v


class ReviewCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=120)
    result: ReviewResult
    score: int | None = Field(default=None, ge=0, le=5)
    note: str = Field(default="", max_length=300)

    @field_validator("topic")
    @classmethod
    def _clean_topic(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("知识点不能为空")
        return v


class PlanRequest(BaseModel):
    as_of: str | None = Field(default=None, description="ISO 时间，便于可复现演示；留空表示当前时间")

    @field_validator("as_of")
    @classmethod
    def _validate_as_of(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        datetime.fromisoformat(v.strip())  # raises ValueError on bad input
        return v.strip()


# --- Persisted record payloads (encoded into PowerContext) -------------------
class NoteRecord(BaseModel):
    record_kind: Literal["note"] = NOTE_RECORD_KIND
    title: str
    body: str
    origin: str = ""
    knowledge_points: list[str] = Field(default_factory=list)
    created_at: str


class PreferenceRecord(BaseModel):
    record_kind: Literal["preference"] = KIND_PREFERENCE
    daily_minutes: int
    focus: str = ""
    updated_at: str


class WeakPointRecord(BaseModel):
    record_kind: Literal["weak-point"] = KIND_WEAK_POINT
    topic: str
    severity: int
    note: str = ""
    updated_at: str


class ReviewRecord(BaseModel):
    record_kind: Literal["review"] = KIND_REVIEW
    topic: str
    result: ReviewResult
    score: int | None = None
    note: str = ""
    reviewed_at: str


def encode_text(record: BaseModel) -> str:
    """Encode a persisted record as the JSON ``text`` stored in a Memory entry."""
    return json.dumps(record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)


def encode_source_content(record: NoteRecord) -> dict[str, Any]:
    """Encode a note as the JSON ``content`` of a PowerContext content Source."""
    return record.model_dump(mode="json")


__all__ = [
    "KIND_PREFERENCE",
    "KIND_REVIEW",
    "KIND_WEAK_POINT",
    "NOTE_RECORD_KIND",
    "SPACE_EXTERNAL_REF_KIND",
    "NoteCreate",
    "NoteRecord",
    "PlanRequest",
    "PreferenceRecord",
    "PreferenceUpdate",
    "ReviewCreate",
    "ReviewRecord",
    "ReviewResult",
    "SpaceCreate",
    "WeakPointRecord",
    "WeakPointUpdate",
    "encode_source_content",
    "encode_text",
    "utc_now_iso",
]
