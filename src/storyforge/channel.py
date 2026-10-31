"""Channel configuration loader.

Loads per-channel settings from YAML files OUTSIDE the OSS repo.
Actual channel configs (with real account IDs) must never be committed.

Search order for channels/<name>.yaml:
  1. ./channels/<name>.yaml (current directory)
  2. ~/workspace/channels/<name>.yaml
  3. Path from STORYFORGE_CHANNELS_DIR env var

The OSS repo ships only config/channel.example.yaml (template with placeholder values).
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


def _candidate_dirs() -> list[Path]:
    dirs = []
    env_dir = os.environ.get("STORYFORGE_CHANNELS_DIR")
    if env_dir:
        dirs.append(Path(env_dir))
    dirs.append(Path.cwd() / "channels")
    dirs.append(Path.home() / "workspace" / "channels")
    return dirs


def find_channel_file(name: str) -> Path | None:
    """Return the path to channels/<name>.yaml, or None if not found."""
    filename = f"{name}.yaml"
    for d in _candidate_dirs():
        p = d / filename
        if p.is_file():
            return p
    return None


def list_channels() -> list[str]:
    """Return names of all available channel configs."""
    seen: set[str] = set()
    for d in _candidate_dirs():
        if d.is_dir():
            for p in d.glob("*.yaml"):
                seen.add(p.stem)
    return sorted(seen)


def load_channel(name: str) -> dict:
    """Load and validate a channel config. Raises FileNotFoundError / ValueError."""
    if not _HAS_YAML:
        raise ImportError("PyYAML is required for channel configs: pip install pyyaml")

    path = find_channel_file(name)
    if path is None:
        searched = [str(d) for d in _candidate_dirs()]
        raise FileNotFoundError(
            f"Channel '{name}' not found. Searched: {searched}\n"
            f"Copy config/channel.example.yaml to channels/{name}.yaml and fill in your values."
        )

    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    # Validate required fields
    required = [
        ("channel_name",),
        ("instagram", "account_id"),
        ("tone",),
        ("caption", "format"),
    ]
    missing = []
    for keys in required:
        node = cfg
        for k in keys:
            if isinstance(node, dict) and k in node:
                node = node[k]
            else:
                missing.append(".".join(keys))
                break
    if missing:
        raise ValueError(f"Channel '{name}' is missing required fields: {missing}")

    # Refuse placeholder values
    account_id = cfg["instagram"]["account_id"]
    if "REPLACE_WITH" in str(account_id) or "YOUR_" in str(account_id):
        raise ValueError(
            f"Channel '{name}': instagram.account_id still has a placeholder value. "
            f"Fill in your real account ID in {path}"
        )

    cfg["_source"] = str(path)
    return cfg
