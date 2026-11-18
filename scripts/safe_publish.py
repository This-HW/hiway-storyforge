#!/usr/bin/env python3
"""Safe Instagram feed publisher with duplicate prevention.

Why this exists: `instagram-cli post-feed` rejects any `--retries` value other
than 0, so an ambiguous failure (HTTP 500, timeout, dropped connection) leaves
the worker unsure whether the post landed. Re-running post-feed blindly has
caused duplicate carousels five times (2026-10-26, 10-30, 11-01, 11-03, 11-04).
This script enforces the check-first rule in code:

  1. Pre-publish check: if the account already has a post whose caption matches
     the intended one, do NOT publish again (exit 2).
  2. Publish once with --retries 0 and a timeout.
  3. Post-ambiguous-failure check: after any uncertain outcome (non-zero exit,
     timeout), read the account's recent posts and compare captions. If a fresh
     matching post exists, treat it as already published (exit 2). Only if no
     match is found may the caller consider retrying manually (exit 1).

Exit codes
  0  published successfully
  1  failed and no matching post found on the account (outcome uncertain only
     in the sense of the publish call; the account check found nothing to
     reuse). A human should review before any retry.
  2  already published (pre-check or post-check found a matching post on the
     account). Do NOT publish again; record the returned URL as the publish
     result.

Caption matching: captions are compared after whitespace normalization. A
post is a match when its normalized caption equals the intended one, or when
its first 200 normalized characters equal the intended caption's first 200
(normalized) characters AND its length is within 10 characters. Both the
pre-check and the post-failure check scan the last N posts regardless of age:
orphan writes have landed hours before the ambiguous attempt (e.g. 2026-11-04
밀라 was posted 12:14 KST but only detected at the 20:12 KST attempt), so a
recency window on the post-failure check would miss them and invite a
duplicate-creating retry. When any identical caption is already on the
account, not publishing again is always the right call.

Only standard-library modules. Works for the storyforge channels (animal /
property) and any other account passed via --account-id.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

CLI = shutil.which("instagram-cli") or "/opt/hatch/bin/instagram-cli"
# 2026-11-16: 8 -> 20. 계정 게시물이 20건을 넘어서, 8건 윈도우로는
# 며칠 전 orphan-write/중복을 놓칠 수 있다. 캡션 비교 범위를 넓힌다.
CHECK_LIMIT = 20


def run_cli(args: list[str], timeout: int) -> tuple[int, str, str]:
    """Run instagram-cli; return (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(
            [CLI, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except OSError as exc:
        return 1, "", str(exc)
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        return 124, out, f"command timed out after {timeout}s"


def normalize_caption(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def parse_created_at(post: dict) -> datetime | None:
    """Parse a post's creation time as UTC.

    Real CLI shape (verified 2026-11-08): posts carry a FLAT
    ``created_at`` string, e.g. "2026-11-07 05:47:42", in UTC-8
    (Pacific) — NOT UTC and NOT a ``post_created_at`` dict. The old
    ``parse_utc`` read ``post_created_at.utc``, a field the CLI never
    returns, so sorting by creation time was silently dead code.
    A dict-shaped ``post_created_at`` with a ``utc`` key is still
    accepted for forward compatibility.
    """
    raw = post.get("created_at")
    if isinstance(raw, str) and raw.strip():
        try:
            dt = datetime.fromisoformat(raw.strip())
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone(timedelta(hours=-8)))
        return dt.astimezone(timezone.utc)
    created_at = post.get("post_created_at")
    if isinstance(created_at, dict):
        raw = created_at.get("utc")
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return None


def fetch_posts(account_id: str) -> list[dict]:
    rc, out, err = run_cli(
        ["posts", "--account-id", account_id, "--limit", str(CHECK_LIMIT)],
        timeout=60,
    )
    if rc != 0:
        raise RuntimeError(f"posts read failed (rc={rc}): {err[:300] or out[:300]}")
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"posts read returned non-JSON: {out[:200]}") from exc
    posts = data.get("posts") if isinstance(data, dict) else None
    if not isinstance(posts, list) or not all(isinstance(p, dict) and
            isinstance(p.get("post_caption"), (str, type(None))) and "post_caption" in p
            for p in posts):
        raise RuntimeError("posts read returned an unexpected response shape")
    return posts


def caption_match(post_caption: str, intended: str) -> bool:
    a = normalize_caption(post_caption)
    b = normalize_caption(intended)
    if not a or not b:
        return False
    if a == b:
        return True
    return a[:200] == b[:200] and abs(len(a) - len(b)) <= 10


def find_matching_post(posts: list[dict], intended: str, since: datetime | None) -> dict | None:
    """Return the newest matching post; respect recency window when `since` given."""
    for post in sorted(
        posts,
        key=lambda p: parse_created_at(p) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    ):
        if not caption_match(post.get("post_caption", ""), intended):
            continue
        created = parse_created_at(post)
        if since is not None:
            if created is None or created < since:
                continue
        return post
    return None


def report(code: int, message: str, payload: dict | None = None) -> int:
    result = {"exit_code": code, "status": message, **(payload or {})}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


def main() -> int:
    ap = argparse.ArgumentParser(description="Publish an Instagram feed post with duplicate prevention.")
    ap.add_argument("--account-id", required=True)
    ap.add_argument("--file", action="append", default=[], help="media file; repeat for carousel order")
    ap.add_argument("--cover", action="append", default=[], help="cover for each video, in video order")
    ap.add_argument("--caption", default="")
    ap.add_argument("--caption-file", default="", help="read caption from file (preferred for long captions)")
    ap.add_argument("--publish-at", default="", help="optional RFC3339 publish time (schedule)")
    ap.add_argument("--publish-timeout", type=int, default=120, help="seconds to wait for post-feed")
    args = ap.parse_args()

    if not args.file:
        return report(1, "no files given")
    # Fail fast on missing inputs, before any account reads or publish
    # attempts: a missing caption/media file must be a clean report,
    # never a traceback or a wasted publish call.
    missing = [f for f in args.file + args.cover if not os.path.isfile(f)]
    if missing:
        return report(1, "media file not found", {"missing": missing})
    caption = args.caption
    if args.caption_file:
        try:
            with open(args.caption_file, "r", encoding="utf-8") as fh:
                caption = fh.read()
        except OSError as exc:
            return report(1, "caption file unreadable",
                          {"path": args.caption_file, "error": str(exc)})

    if not normalize_caption(caption):
        return report(1, "caption required for duplicate check")

    # 1. Pre-publish duplicate check: never re-post a caption already on the account.
    try:
        posts = fetch_posts(args.account_id)
    except RuntimeError as exc:
        return report(1, f"pre-publish account check failed; refusing to publish blind: {exc}")
    match = find_matching_post(posts, caption, since=None)
    if match:
        return report(
            2,
            "already_published",
            {"url": match.get("url"), "post_id": match.get("post_id"),
             "created_at": match.get("created_at")},
        )

    # 2. Publish once, no retries (instagram-cli rejects --retries != 0 anyway).
    cmd = ["post-feed", "--account-id", args.account_id, "--retries", "0"]
    for f in args.file:
        cmd += ["--file", f]
    for c in args.cover:
        cmd += ["--cover", c]
    if caption:
        cmd += ["--caption", caption]
    if args.publish_at:
        cmd += ["--publish-at", args.publish_at]

    rc, out, err = run_cli(cmd, timeout=args.publish_timeout)

    if rc == 0:
        url = ""
        media_id = ""
        try:
            data = json.loads(out)
            data = data if isinstance(data, dict) else {}
            url = data.get("url") or ""
            media_id = data.get("media_id") or data.get("post_id") or ""
        except json.JSONDecodeError:
            pass
        # Best-effort verification: confirm the post actually landed and
        # enrich the report with the verified URL. A failed verification
        # fetch must NOT flip a successful publish into a failure — the
        # publish call already returned 0; verification only adds evidence.
        payload: dict = {"url": url, "media_id": media_id, "raw": out[:500]}
        try:
            posts = fetch_posts(args.account_id)
            match = find_matching_post(posts, caption, since=None)
            if match:
                payload["verified_url"] = match.get("url")
                payload["verified_post_id"] = match.get("post_id")
                if not url:
                    payload["url"] = match.get("url")
            else:
                payload["verify"] = "no matching post found in follow-up read"
        except Exception as exc:  # noqa: BLE001 — verification is advisory
            payload["verify"] = f"follow-up read failed (publish rc=0 stands): {exc}"
        return report(0, "published", payload)

    # 3. Ambiguous failure: could be a 500/timeout after the server accepted the
    #    write (the known "orphan write" pattern). Check the account BEFORE any
    #    retry decision.
    try:
        posts = fetch_posts(args.account_id)
    except RuntimeError as exc:
        return report(
            1,
            f"publish returned rc={rc}; follow-up account check also failed: {exc}. "
            "Do NOT retry blindly — verify the post in the Instagram app first.",
            {"needs_reconciliation": True},
        )
    # Post-failure check uses the same rule as the pre-check: any matching
    # caption already on the account means "already published", regardless of
    # when it landed. (Orphan writes have landed hours before the ambiguous
    # attempt — 2026-11-04 밀라 posted 12:14 KST, detected 20:12 KST — so a
    # recency window here would miss them and invite a duplicate retry.)
    match = find_matching_post(posts, caption, since=None)
    if match:
        return report(
            2,
            "already_published",
            {"url": match.get("url"), "post_id": match.get("post_id"),
             "note": f"publish call failed (rc={rc}) but the post landed on the account",
             "stderr": err[:300]},
        )
    return report(
        1,
        "failed_no_match",
        {"rc": rc, "stderr": err[:500], "stdout": out[:500],
         "needs_reconciliation": True,
         "note": "no matching fresh post on the account; manual review before any retry"},
    )


if __name__ == "__main__":
    sys.exit(main())
