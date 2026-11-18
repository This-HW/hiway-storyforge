#!/usr/bin/env python3
"""Preflight check for production runs (weekly batch / daily produce jobs).

Verifies the environment and inputs a production worker needs BEFORE it
starts generating, so a broken run fails fast with a clear report instead
of dying mid-batch — or worse, starting late and reporting "incomplete"
with no evidence of what went wrong (2026-11-09 weekly prep failure).

Checks (each opt-in via flags; environment checks always run):
  - queue files parse as JSON (--queue, repeatable)
  - candidates file parses as JSON, with a status breakdown
    (--candidates; --min-candidates N + --candidate-status S optionally
    enforce a minimum staged pool — off by default, because this pipeline
    sources fresh stories each run instead of pre-staging candidates)
  - endcard files exist (--endcard, repeatable)
  - output directory is writable (--outdir, repeatable)
  - font file exists (--font)
  - Pillow + RAQM layout engine available, kiwipiepy importable,
    PyYAML importable, instagram-cli on PATH (always)

Usage:
  python3 scripts/preflight.py --queue data/queue.json \\
      --candidates data/candidates.json \\
      --endcard /path/to/endcard.jpg --outdir data/work/batchXXXX \\
      --font /usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc

Prints a JSON report; exit 0 = all checks passed, 1 = any check failed.
A failed preflight means: do not start production; fix the environment
first. This script never writes queue state or publishes anything.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def _check(name: str, ok: bool, detail: str = "") -> dict:
    return {"check": name, "ok": ok, "detail": detail}


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, "file not found"
    except json.JSONDecodeError as exc:
        return None, f"unparseable JSON: {exc}"
    except OSError as exc:
        return None, f"unreadable: {exc}"


def check_queue(path_str: str) -> dict:
    path = Path(path_str)
    data, err = _load_json(path)
    if err:
        return _check(f"queue:{path_str}", False, err)
    if isinstance(data, dict):
        entries = data.get("items", data)
        if not isinstance(entries, (list, dict)):
            return _check(f"queue:{path_str}", False, "unexpected items shape")
        count = len(entries)
    elif isinstance(data, list):
        count = len(data)
    else:
        return _check(f"queue:{path_str}", False, f"unexpected shape: {type(data).__name__}")
    return _check(f"queue:{path_str}", True, f"parses OK, {count} entries")


def check_candidates(path_str: str, minimum: int, status: str) -> dict:
    path = Path(path_str)
    data, err = _load_json(path)
    if err:
        return _check(f"candidates:{path_str}", False, err)
    if isinstance(data, dict):
        items = data.get("candidates", data)
        items = list(items.values()) if isinstance(items, dict) else items
    elif isinstance(data, list):
        items = data
    else:
        return _check(f"candidates:{path_str}", False, "unexpected shape")
    if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        return _check(f"candidates:{path_str}", False, "unexpected candidates shape")
    from collections import Counter
    breakdown = Counter(
        it.get("status", "?") for it in items if isinstance(it, dict))
    detail = f"{len(items)} entries: {dict(breakdown)}"
    if minimum <= 0:
        return _check(f"candidates:{path_str}", True, detail + " (no pool minimum enforced)")
    ready = sum(1 for it in items if isinstance(it, dict) and it.get("status") == status)
    ok = ready >= minimum
    return _check(f"candidates:{path_str}", ok,
                  f"{detail}; {ready} '{status}' items (need >= {minimum})")


def check_file(path_str: str, label: str) -> dict:
    path = Path(path_str)
    if not path.is_file():
        return _check(f"{label}:{path_str}", False, "file not found")
    if path.stat().st_size == 0:
        return _check(f"{label}:{path_str}", False, "file is empty")
    return _check(f"{label}:{path_str}", True, "exists")


def check_outdir(path_str: str) -> dict:
    path = Path(path_str)
    if not path.exists():
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return _check(f"outdir:{path_str}", False, f"cannot create: {exc}")
    if not os.access(path, os.W_OK):
        return _check(f"outdir:{path_str}", False, "not writable")
    try:
        fd, tmp = tempfile.mkstemp(dir=path, prefix=".preflight-")
        os.close(fd)
        os.unlink(tmp)
    except OSError as exc:
        return _check(f"outdir:{path_str}", False, f"write test failed: {exc}")
    return _check(f"outdir:{path_str}", True, "writable")


def check_environment() -> list[dict]:
    results: list[dict] = []
    try:
        from PIL import features
        available = bool(features.check_feature("raqm"))
        results.append(_check("pillow+raqm", available,
                              "RAQM available" if available else "RAQM unavailable"))
    except ImportError:
        results.append(_check("pillow+raqm", False, "Pillow not installed"))
    try:
        from storyforge.korean_text import word_boundary_engine
        engine = word_boundary_engine()
    except Exception:
        engine = "unknown"
    results.append(_check(
        "kiwipiepy", engine == "kiwipiepy",
        f"word-boundary engine: {engine}"
        + ("" if engine == "kiwipiepy"
           else " (space-split fallback: wrapping quality degraded; pip install kiwipiepy)")))
    try:
        import yaml  # noqa: F401
        results.append(_check("pyyaml", True, "importable"))
    except ImportError:
        results.append(_check("pyyaml", False, "not installed"))
    cli = shutil.which("instagram-cli") or "/opt/hatch/bin/instagram-cli"
    results.append(_check(
        "instagram-cli", Path(cli).exists(), cli))
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description="Preflight check for production runs.")
    ap.add_argument("--queue", action="append", default=[])
    ap.add_argument("--candidates", default="")
    ap.add_argument("--min-candidates", type=int, default=0,
                    help="enforce a minimum staged pool (0 = off; pipeline sources fresh)")
    ap.add_argument("--candidate-status", default="후보",
                    help="status counted toward --min-candidates")
    ap.add_argument("--endcard", action="append", default=[])
    ap.add_argument("--outdir", action="append", default=[])
    ap.add_argument("--font", default="")
    ap.add_argument("--warn-only", action="append", default=[],
                    help="check name prefix treated as warning, not failure (repeatable)")
    args = ap.parse_args()

    results: list[dict] = []
    results += check_environment()
    for q in args.queue:
        results.append(check_queue(q))
    if args.candidates:
        results.append(check_candidates(args.candidates, args.min_candidates,
                                        args.candidate_status))
    for e in args.endcard:
        results.append(check_file(e, "endcard"))
    for d in args.outdir:
        results.append(check_outdir(d))
    if args.font:
        results.append(check_file(args.font, "font"))

    failures = []
    for r in results:
        if r["ok"]:
            continue
        if any(r["check"].startswith(prefix) for prefix in args.warn_only):
            r["warning_only"] = True
        else:
            failures.append(r)
    report = {
        "passed": not failures,
        "failures": len(failures),
        "checks": results,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"preflight: {'PASS' if not failures else 'FAIL'} "
          f"({len(failures)} failures / {len(results)} checks)", file=sys.stderr)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
