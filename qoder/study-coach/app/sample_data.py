"""Synthetic sample data for the StudyRecall acceptance walkthrough.

Everything here is invented demo content for a fictional learner preparing a
database exam. It is used to seed a real PowerContext space; the notes themselves
are stored as PowerContext content Sources, and the preference / weak points /
reviews as Memory entries.
"""

from __future__ import annotations

from dataclasses import dataclass

SAMPLE_SPACE_TITLE = "数据库考试冲刺"
SAMPLE_SPACE_SUMMARY = "合成学习者：准备数据库考试，每天 25 分钟复习。"
SAMPLE_DAILY_MINUTES = 25


@dataclass(frozen=True)
class SampleNote:
    title: str
    body: str
    origin: str
    knowledge_points: list[str]


SAMPLE_NOTES: list[SampleNote] = [
    SampleNote(
        title="事务隔离级别",
        body=(
            "四种标准隔离级别：读未提交、读已提交（RC）、可重复读（RR）、串行化。"
            "RC 允许不可重复读，RR 通过快照读避免不可重复读但可能出现幻读，"
            "InnoDB 在 RR 级别用间隙锁（Gap Lock）缓解幻读。"
        ),
        origin="自编合成笔记 · 数据库原理 第 3 章",
        knowledge_points=["事务隔离级别", "不可重复读", "幻读"],
    ),
    SampleNote(
        title="索引选择",
        body=(
            "聚簇索引按主键组织数据；二级索引存储主键并需回表。"
            "最左前缀原则决定复合索引可用性；覆盖索引可避免回表。"
            "选择性（cardinality）高的列更适合建索引，低基数列选择性差收益有限。"
        ),
        origin="自编合成笔记 · 数据库原理 第 5 章",
        knowledge_points=["索引选择", "覆盖索引", "最左前缀"],
    ),
]

# Initial self-declared weak points (程度 1-5).
SAMPLE_WEAK_POINTS: list[tuple[str, int]] = [
    ("事务隔离级别", 5),
    ("索引选择", 4),
]


__all__ = [
    "SAMPLE_DAILY_MINUTES",
    "SAMPLE_NOTES",
    "SAMPLE_SPACE_SUMMARY",
    "SAMPLE_SPACE_TITLE",
    "SampleNote",
]
