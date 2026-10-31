"""Sourcing strategies for content candidates.

OSS functionality: the strategies (how to source) live here.
Channel-specific settings (thresholds, queue paths, keywords) come from
channel config files (private, never committed).

Two built-in strategies:
- ViralSourcing: for entertainment channels — finds already-viral content
  with recorded metrics (views, shares). "이미 대박난 것만 다룬다."
- KnowledgeQueueSourcing: for educational channels — pulls topics from
  a curated knowledge queue in priority order.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Candidate:
    """A single content candidate from sourcing."""

    title: str
    source_url: str = ""
    metrics: dict = field(default_factory=dict)  # e.g. {"views": 1500000, "shares": 3200}
    notes: str = ""
    topic: str = ""  # for knowledge-queue sourcing
    metadata: dict = field(default_factory=dict)

    def has_metrics(self) -> bool:
        """True if the candidate has recorded performance metrics."""
        return bool(self.metrics)


class SourcingStrategy(ABC):
    """Base interface for all sourcing strategies."""

    @abstractmethod
    def find_candidates(self, count: int = 5) -> list[Candidate]:
        """Return up to `count` candidates."""
        ...

    @abstractmethod
    def validate(self, candidate: Candidate) -> tuple[bool, str]:
        """Check if a candidate meets this strategy's criteria.
        Returns (is_valid, reason)."""
        ...


class ViralSourcing(SourcingStrategy):
    """Sources already-viral content with verified metrics.

    Principle: "이미 대박난 것만 다룬다" — only handle what's already proven.
    Candidates without recorded metrics are rejected.

    Config (from channel yaml `sourcing` section):
      min_views: minimum view count to qualify
      exclude_keywords: list of keywords to filter out
    """

    def __init__(self, config: dict | None = None):
        cfg = config or {}
        self.min_views: int = cfg.get("min_views", 0)
        self.exclude_keywords: list[str] = cfg.get("exclude_keywords", [])

    def find_candidates(self, count: int = 5) -> list[Candidate]:
        # Automated viral discovery is not yet implemented.
        # Candidates are added manually via web research with metrics recorded.
        # This method returns an empty list; use add_manual_candidate() instead.
        return []

    def add_manual_candidate(
        self,
        title: str,
        source_url: str,
        metrics: dict,
        notes: str = "",
    ) -> Candidate:
        """Register a manually-researched candidate with its metrics."""
        return Candidate(
            title=title,
            source_url=source_url,
            metrics=metrics,
            notes=notes,
        )

    def validate(self, candidate: Candidate) -> tuple[bool, str]:
        if not candidate.has_metrics():
            return False, "지표 없음 — 원본 조회수/공유 수를 기록해야 함"
        views = candidate.metrics.get("views", 0)
        if views < self.min_views:
            return False, f"조회수 미달 ({views} < {self.min_views})"
        title_lower = candidate.title.lower()
        for kw in self.exclude_keywords:
            if kw.lower() in title_lower:
                return False, f"제외 키워드 포함: {kw}"
        return True, "통과"


class KnowledgeQueueSourcing(SourcingStrategy):
    """Sources topics from a curated knowledge queue in priority order.

    For educational channels: topics are pre-planned in a queue file
    (e.g. publish-queue.md), and sourcing pulls them in order.

    Config (from channel yaml `sourcing` section):
      queue_path: path to the queue file (markdown with topic list)
      completed: list of already-published topic names to skip
    """

    def __init__(self, config: dict | None = None):
        cfg = config or {}
        self.queue_path: str = cfg.get("queue_path", "")
        self.completed: list[str] = cfg.get("completed", [])

    def _parse_queue(self) -> list[str]:
        """Extract topic names from the queue markdown file."""
        if not self.queue_path:
            return []
        p = Path(self.queue_path)
        if not p.is_file():
            return []
        topics = []
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            # Match numbered list items: "1. **NOI** (순영업소득)"
            if line and line[0].isdigit() and "." in line:
                # Extract bold text or first phrase
                if "**" in line:
                    start = line.index("**") + 2
                    end = line.index("**", start)
                    topics.append(line[start:end])
                else:
                    # fallback: text after "N. "
                    dot = line.index(".")
                    topics.append(line[dot + 1 :].strip().split("(")[0].strip())
        return topics

    def find_candidates(self, count: int = 5) -> list[Candidate]:
        topics = self._parse_queue()
        candidates = []
        for topic in topics:
            if topic in self.completed:
                continue
            candidates.append(
                Candidate(
                    title=topic,
                    topic=topic,
                    notes=f"지식 큐에서 추출 (순서: {len(candidates) + 1})",
                )
            )
            if len(candidates) >= count:
                break
        return candidates

    def validate(self, candidate: Candidate) -> tuple[bool, str]:
        if not candidate.topic:
            return False, "주제 없음"
        if candidate.topic in self.completed:
            return False, f"이미 발행됨: {candidate.topic}"
        return True, "통과"


def create_strategy(name: str, config: dict | None = None) -> SourcingStrategy:
    """Factory: create a sourcing strategy by name."""
    strategies = {
        "viral": ViralSourcing,
        "knowledge_queue": KnowledgeQueueSourcing,
    }
    if name not in strategies:
        raise ValueError(
            f"Unknown sourcing strategy: {name}. Available: {list(strategies.keys())}"
        )
    return strategies[name](config)
