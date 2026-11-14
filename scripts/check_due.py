#!/usr/bin/env python3
"""Canonical due-item checker for the post-dispatcher (10-min cron).

Why this exists (2026-11-08 fix): dispatcher workers kept inventing ad-hoc
queue-parsing scripts each run and failing with AttributeError
(`list.get`, list/dict handling mismatches) plus path probes
(/root/..., /home/user/...) before recovering with /home/hatch/... paths.
The queue shapes are fixed, so the check is fixed code now:

  - animal queue: ~/workspace/hiway-storyforge/data/queue.json is a DICT
    keyed by queue-item id. Each value has scheduled_for + status.
    NOTE: animal items have NO `on_date` field — match by scheduled_for date.
  - property queue: ~/workspace/property-account/queue.json is a DICT with
    an `items` LIST. Each item has on_date + scheduled_for + status.

All scheduled_for values are KST (Asia/Seoul). Naive strings are KST,
never UTC. `scheduled_for <= now (KST)` and status == "컨펌됨" means due.

Usage: python3 check_due.py [--json]
Prints a JSON report; exit code is 0 when both queues were read, 2 when
a queue file is missing or unparseable (callers must treat that as
"unknown", never as "nothing due" — a traceback must never be the
signal). The success report shape is unchanged.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
HOME = Path.home()  # never hard-code a username: this runs as the deploy user
ANIMAL_QUEUE = HOME / "workspace/hiway-storyforge/data/queue.json"
PROPERTY_QUEUE = HOME / "workspace/property-account/queue.json"


def parse_kst(raw: str) -> datetime | None:
    """Parse a scheduled_for string as KST. Returns None when unparseable."""
    if not raw:
        return None
    text = str(raw).strip().replace(" ", "T", 1)
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KST)
    return dt.astimezone(KST)


def load_queue_json(path: Path) -> tuple[object, str | None]:
    """Read + parse a queue file. Returns (data, error); error is None on success."""
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"queue file missing: {path}"
    except json.JSONDecodeError as exc:
        return None, f"queue file unparseable: {path}: {exc}"
    except OSError as exc:
        return None, f"queue file unreadable: {path}: {exc}"


def load_animal() -> tuple[list[dict], str | None]:
    data, err = load_queue_json(ANIMAL_QUEUE)
    if err:
        return [], err
    # dict keyed by id — NOT a list; do not call .get on a list.
    if isinstance(data, dict):
        items = data.values()
    elif isinstance(data, list):
        items = data
    else:
        return [], f"animal queue unexpected shape: {type(data).__name__}"
    out = []
    for v in items:
        if not isinstance(v, dict):
            continue
        out.append(
            {
                "channel": "animal",
                "id": v.get("id") or v.get("queue_id") or "",
                "scheduled_for": v.get("scheduled_for"),
                "status": v.get("status"),
            }
        )
    return out, None


def load_property() -> tuple[list[dict], str | None]:
    data, err = load_queue_json(PROPERTY_QUEUE)
    if err:
        return [], err
    # dict with an `items` LIST — iterate the list, do not call .get on it.
    if isinstance(data, dict):
        raw_items = data.get("items", [])
    elif isinstance(data, list):
        raw_items = data
    else:
        return [], f"property queue unexpected shape: {type(data).__name__}"
    if not isinstance(raw_items, list):
        return [], "property queue 'items' is not a list"
    out = []
    for v in raw_items:
        if not isinstance(v, dict):
            continue
        out.append(
            {
                "channel": "property",
                "id": v.get("topic") or v.get("id") or "",
                "on_date": v.get("on_date"),
                "scheduled_for": v.get("scheduled_for"),
                "status": v.get("status"),
            }
        )
    return out, None


def main() -> int:
    now = datetime.now(KST)
    animal_items, animal_err = load_animal()
    property_items, property_err = load_property()
    errors = [e for e in (animal_err, property_err) if e]
    if errors:
        print(json.dumps({
            "now_kst": now.isoformat(timespec="seconds"),
            "error": "queue_load_failed",
            "details": errors,
        }, ensure_ascii=False, indent=2))
        return 2
    items = animal_items + property_items
    due, waiting_past_due = [], []
    for it in items:
        sched = parse_kst(it.get("scheduled_for") or "")
        it["scheduled_for_kst"] = sched.isoformat() if sched else None
        it["is_due"] = bool(sched and sched <= now)
        if it.get("status") == "컨펌됨" and it["is_due"]:
            due.append(it)
        elif it.get("status") == "대기" and it["is_due"]:
            waiting_past_due.append(it)
    due.sort(key=lambda x: x["scheduled_for_kst"] or "")
    waiting_past_due.sort(key=lambda x: x["scheduled_for_kst"] or "")
    report = {
        "now_kst": now.isoformat(timespec="seconds"),
        "due_confirmed": due,
        "waiting_past_due": waiting_past_due,
        "counts": {
            "animal": sum(1 for i in items if i["channel"] == "animal"),
            "property": sum(1 for i in items if i["channel"] == "property"),
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
