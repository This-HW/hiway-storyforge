"""JSON index store under the data dir. Relative paths only."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from .models import Material


class Store:
    def __init__(self, data_dir: Path):
        self.dir = data_dir
        self.index_path = data_dir / "index.json"
        (data_dir / "materials").mkdir(parents=True, exist_ok=True)
        (data_dir / "outputs").mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self._save({})

    def _load(self) -> dict:
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def _save(self, index: dict) -> None:
        self.index_path.write_text(
            json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")

    def new_id(self) -> str:
        return uuid.uuid4().hex[:12]

    def add(self, material: Material) -> Material:
        index = self._load()
        index[material.id] = material.to_dict()
        self._save(index)
        return material

    def get(self, material_id: str) -> Material | None:
        item = self._load().get(material_id)
        return Material.from_dict(item) if item else None

    def update(self, material: Material) -> None:
        index = self._load()
        index[material.id] = material.to_dict()
        self._save(index)

    def list(self) -> list[Material]:
        return [Material.from_dict(v) for v in self._load().values()]

    def save_image(self, material_id: str, ext: str, data: bytes) -> str:
        rel = f"materials/{material_id}{ext}"
        (self.dir / rel).write_bytes(data)
        return rel

    def output_dir(self, material_id: str) -> Path:
        path = self.dir / "outputs" / material_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    # -- sourcing candidates (FR-9) ------------------------------------------
    @property
    def _cand_path(self) -> Path:
        return self.dir / "candidates.json"

    def _load_candidates(self) -> dict:
        if not self._cand_path.exists():
            return {}
        return json.loads(self._cand_path.read_text(encoding="utf-8"))

    def _save_candidates(self, data: dict) -> None:
        self._cand_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    def add_candidate(self, cand) -> object:
        data = self._load_candidates()
        data[cand.id] = cand.to_dict()
        self._save_candidates(data)
        return cand

    def list_candidates(self) -> list:
        from .models import SourcingCandidate
        return [SourcingCandidate.from_dict(v)
                for v in self._load_candidates().values()]

    def update_candidate(self, cand) -> None:
        data = self._load_candidates()
        data[cand.id] = cand.to_dict()
        self._save_candidates(data)

    # -- publishing queue (P3) -------------------------------------------------
    @property
    def _queue_path(self) -> Path:
        return self.dir / "queue.json"

    def _load_queue(self) -> dict:
        if not self._queue_path.exists():
            return {}
        return json.loads(self._queue_path.read_text(encoding="utf-8"))

    def _save_queue(self, data: dict) -> None:
        self._queue_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    def add_queue_item(self, item) -> object:
        data = self._load_queue()
        data[item.id] = item.to_dict()
        self._save_queue(data)
        return item

    def list_queue(self) -> list:
        from .models import QueueItem
        return [QueueItem.from_dict(v) for v in self._load_queue().values()]

    def get_queue_item(self, queue_id: str):
        item = self._load_queue().get(queue_id)
        if item is None:
            return None
        from .models import QueueItem
        return QueueItem.from_dict(item)

    def update_queue_item(self, item) -> None:
        data = self._load_queue()
        data[item.id] = item.to_dict()
        self._save_queue(data)

    # -- approved copy patterns (SPEC §9-2, P1) --------------------------------
    @property
    def _patterns_path(self) -> Path:
        return self.dir / "patterns.json"

    def list_patterns(self) -> list[dict]:
        if not self._patterns_path.exists():
            return []
        return json.loads(self._patterns_path.read_text(encoding="utf-8"))

    def add_pattern(self, text: str, topic: str = "") -> list[dict]:
        patterns = self.list_patterns()
        if any(p["text"] == text for p in patterns):
            return patterns
        patterns.append({"text": text, "topic": topic})
        self._patterns_path.write_text(
            json.dumps(patterns, ensure_ascii=False, indent=1), encoding="utf-8")
        return patterns
