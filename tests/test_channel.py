"""Tests for channel config loader."""
import os
import tempfile
from pathlib import Path

import pytest
import yaml

from storyforge.channel import find_channel_file, list_channels, load_channel


@pytest.fixture
def channel_dir(monkeypatch, tmp_path):
    d = tmp_path / "channels"
    d.mkdir()
    monkeypatch.setenv("STORYFORGE_CHANNELS_DIR", str(d))
    # isolate from real ~/workspace/channels
    monkeypatch.setattr("storyforge.channel._candidate_dirs", lambda: [d])
    return d


def _write(d: Path, name: str, cfg: dict) -> Path:
    p = d / f"{name}.yaml"
    p.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    return p


def _valid_cfg():
    return {
        "channel_name": "test",
        "instagram": {"account_id": "12345"},
        "tone": "테스트 톤",
        "caption": {"format": "test_format"},
    }


def test_load_valid(channel_dir):
    _write(channel_dir, "test", _valid_cfg())
    cfg = load_channel("test")
    assert cfg["instagram"]["account_id"] == "12345"
    assert cfg["tone"] == "테스트 톤"


def test_missing_file(channel_dir):
    with pytest.raises(FileNotFoundError, match="not found"):
        load_channel("nonexistent")


def test_missing_required_field(channel_dir):
    cfg = _valid_cfg()
    del cfg["tone"]
    _write(channel_dir, "bad", cfg)
    with pytest.raises(ValueError, match="missing required fields"):
        load_channel("bad")


def test_placeholder_account_id_rejected(channel_dir):
    cfg = _valid_cfg()
    cfg["instagram"]["account_id"] = "REPLACE_WITH_YOUR_ACCOUNT_ID"
    _write(channel_dir, "placeholder", cfg)
    with pytest.raises(ValueError, match="placeholder"):
        load_channel("placeholder")


def test_list_channels(channel_dir):
    _write(channel_dir, "a", _valid_cfg())
    _write(channel_dir, "b", _valid_cfg())
    assert set(list_channels()) == {"a", "b"}


def test_find_channel_file(channel_dir):
    p = _write(channel_dir, "found", _valid_cfg())
    assert find_channel_file("found") == p
    assert find_channel_file("missing") is None
