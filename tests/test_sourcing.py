"""Tests for sourcing strategies."""
import tempfile
from pathlib import Path

import pytest
import yaml

from storyforge.sourcing import (
    Candidate,
    KnowledgeQueueSourcing,
    ViralSourcing,
    create_strategy,
)


@pytest.fixture
def queue_file(tmp_path):
    p = tmp_path / "queue.md"
    p.write_text(
        "# Queue\n\n1. **NOI** (순영업소득)\n2. **NOC**\n3. **수도광열비**\n",
        encoding="utf-8",
    )
    return p


class TestViralSourcing:
    def setup_method(self):
        self.s = ViralSourcing({"min_views": 1000000, "exclude_keywords": ["충격"]})

    def test_valid_candidate_passes(self):
        c = self.s.add_manual_candidate("감동 이야기", "https://x.com", {"views": 2000000})
        ok, _ = self.s.validate(c)
        assert ok

    def test_no_metrics_rejected(self):
        ok, reason = self.s.validate(Candidate(title="지표 없음"))
        assert not ok and "지표 없음" in reason

    def test_low_views_rejected(self):
        c = self.s.add_manual_candidate("낮음", "https://x.com", {"views": 100})
        ok, reason = self.s.validate(c)
        assert not ok and "미달" in reason

    def test_excluded_keyword_rejected(self):
        c = self.s.add_manual_candidate("충격 이야기", "https://x.com", {"views": 2000000})
        ok, reason = self.s.validate(c)
        assert not ok and "제외 키워드" in reason

    def test_find_returns_empty(self):
        # automated discovery not yet implemented
        assert self.s.find_candidates() == []


class TestKnowledgeQueueSourcing:
    def test_parses_queue_in_order(self, queue_file):
        s = KnowledgeQueueSourcing({"queue_path": str(queue_file), "completed": []})
        cands = s.find_candidates(count=3)
        assert [c.topic for c in cands] == ["NOI", "NOC", "수도광열비"]

    def test_skips_completed(self, queue_file):
        s = KnowledgeQueueSourcing(
            {"queue_path": str(queue_file), "completed": ["NOI"]}
        )
        cands = s.find_candidates(count=2)
        assert cands[0].topic == "NOC"

    def test_validate_rejects_completed(self, queue_file):
        s = KnowledgeQueueSourcing(
            {"queue_path": str(queue_file), "completed": ["NOI"]}
        )
        ok, _ = s.validate(Candidate(title="NOI", topic="NOI"))
        assert not ok

    def test_missing_file_returns_empty(self, tmp_path):
        s = KnowledgeQueueSourcing({"queue_path": str(tmp_path / "nope.md")})
        assert s.find_candidates() == []


class TestFactory:
    def test_create_viral(self):
        assert isinstance(create_strategy("viral", {}), ViralSourcing)

    def test_create_knowledge_queue(self):
        assert isinstance(create_strategy("knowledge_queue", {}), KnowledgeQueueSourcing)

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown sourcing strategy"):
            create_strategy("nope")
