"""3-layer config loader.

Priority (low -> high): config/default.json < config/user.json < env (PB_*).
Secrets are read from env only (see .env.example); never from committed files.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

_ENV_MAP = {
    "PB_PROVIDER": ("provider",),
    "PB_DATA_DIR": ("data_dir",),
}


def _deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for key, value in over.items():
        if key.startswith("_"):
            continue
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _load_env_file() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def load_config() -> dict:
    _load_env_file()
    cfg: dict = {}
    default_path = ROOT / "config" / "default.json"
    if default_path.exists():
        cfg = json.loads(default_path.read_text(encoding="utf-8"))
    user_path = ROOT / "config" / "user.json"
    if user_path.exists():
        cfg = _deep_merge(cfg, json.loads(user_path.read_text(encoding="utf-8")))
    for env_key, path in _ENV_MAP.items():
        if env_key in os.environ:
            node = cfg
            for part in path[:-1]:
                node = node.setdefault(part, {})
            node[path[-1]] = os.environ[env_key]
    return cfg


def data_dir(cfg: dict) -> Path:
    path = Path(cfg.get("data_dir", "data"))
    if not path.is_absolute():
        path = ROOT / path
    path.mkdir(parents=True, exist_ok=True)
    return path
