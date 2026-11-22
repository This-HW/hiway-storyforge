#!/usr/bin/env python3
"""Runnable review gate for one episode (animal story.json / property ep JSON).

Runs the automated gates from storyforge.gates over slide texts, caption,
image prompts, and continuity metadata, and — when given an images
directory — verifies the rendered slide files exist and parse as images.
Optionally validates Korean text rendering (isolated jamo / zero-width
characters) with a real font.

Usage:
  python3 scripts/check_episode.py --story data/work/batch1115/tama/story.json
      [--caption caption.txt | --caption-text "..."]
      [--channel ~/workspace/channels/animal_stories.yaml]
      [--format animal_v2] [--emoji-policy none]
      [--images data/work/batch1115/output/tama] [--font /path/to/Bold.ttc]

Prints a JSON report to stdout; exit 0 = passed (no errors), 1 = gate
errors found, 2 = input/usage error (unreadable story, channel, caption).
Warnings never fail the run. The human checklist (§1.10/§1.11 visual and
semantic items) is always included in the report — it is not automated.

Channel config (YAML) supplies caption.format and caption.emoji_policy;
CLI flags override the YAML. When no policy is configured anywhere, the
standing rule applies: emoji_policy defaults to "none".
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from storyforge import gates  # noqa: E402
from storyforge.korean_text import (  # noqa: E402
    load_korean_font, validate_korean_text, word_boundary_engine, wrap_korean_text,
)

DEFAULT_FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
DEFAULT_WRAP_WIDTH = 952  # Standard 1080-pixel slide with 64-pixel side margins.


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"file not found: {path}"
    except json.JSONDecodeError as exc:
        return None, f"unparseable JSON: {path}: {exc}"
    except OSError as exc:
        return None, f"unreadable: {path}: {exc}"


def _load_channel(path: Path):
    try:
        import yaml
    except ImportError:
        return None, "PyYAML not installed; cannot read channel config"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        return None, f"channel file not found: {path}"
    except OSError as exc:
        return None, f"channel file unreadable: {path}: {exc}"
    except Exception as exc:  # yaml.YAMLError and friends
        return None, f"channel file unparseable: {path}: {exc}"
    return data, None


def _normalize_slides(raw_slides: list) -> list[dict]:
    """Accept animal shape ({n, text, image_prompt}) and property shape
    ({num, head, body[], cover_sub, visual}). Returns dicts with n/text
    (+ image_prompt when present)."""
    out: list[dict] = []
    for i, sl in enumerate(raw_slides or []):
        if isinstance(sl, str):
            out.append({"n": i + 1, "text": sl})
            continue
        if not isinstance(sl, dict):
            continue
        n = sl.get("n", sl.get("num", i + 1))
        try:
            n = int(n)
        except (TypeError, ValueError):
            n = i + 1
        text = sl.get("text")
        if text is None:
            parts = []
            if sl.get("head"):
                parts.append(str(sl["head"]))
            if sl.get("cover_sub"):
                parts.append(str(sl["cover_sub"]))
            for line in sl.get("body") or []:
                parts.append(str(line))
            text = "\n".join(parts)
        item = {"n": n, "text": str(text or "")}
        if sl.get("image_prompt"):
            item["image_prompt"] = str(sl["image_prompt"])
        for key in ("refs", "references", "ref_images"):
            if key in sl:
                item[key] = sl[key]
        out.append(item)
    return out


def _check_images(images_dir: Path, slide_count: int) -> list[dict]:
    """Verify slide_1..slide_N (+ endcard slide_{N+1}) exist and parse."""
    findings: list[dict] = []
    try:
        from PIL import Image
    except ImportError:
        Image = None
    for n in range(1, slide_count + 2):  # +1: endcard is the last slide
        candidates = [images_dir / f"slide_{n}{ext}" for ext in (".jpg", ".jpeg", ".png")]
        candidates += [images_dir / f"slide_{n:02d}{ext}" for ext in (".jpg", ".jpeg", ".png")]
        found = next((p for p in candidates if p.exists()), None)
        label = "endcard" if n == slide_count + 1 else f"slide {n}"
        if found is None:
            findings.append({"level": "error", "gate": "image_missing",
                             "slide": n, "detail": f"{label} 파일 없음 ({images_dir})"})
            continue
        if found.stat().st_size == 0:
            findings.append({"level": "error", "gate": "image_empty",
                             "slide": n, "detail": f"{label} 파일이 비어 있음: {found}"})
        elif Image is not None:
            try:
                with Image.open(found) as img:
                    img.verify()
            except Exception as exc:
                findings.append({"level": "error", "gate": "image_unparseable",
                                 "slide": n, "detail": f"{label} 파싱 실패: {found}: {exc}"})
    return findings


def _check_korean_rendering(texts: list[tuple[int | None, str]], font_path: Path,
                            findings: list[dict], *, wrap_width: int) -> str | None:
    """Check glyphs and whether the slide layout preserves the original text."""
    if not font_path.exists():
        return f"font not found, Korean rendering check skipped: {font_path}"
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return "Pillow not installed, Korean rendering check skipped"
    try:
        font = load_korean_font(str(font_path), 64)
    except Exception as exc:
        return f"font load failed, Korean rendering check skipped: {exc}"
    draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    for slide_no, text in texts:
        for issue_type, detail in validate_korean_text(text, font, draw):
            level = "error" if issue_type == "tofu" else "warning"
            findings.append({"level": level, "gate": f"korean_{issue_type}",
                             "slide": slide_no, "detail": detail})
        if slide_no is not None:
            lines = wrap_korean_text(text, font, wrap_width, draw)
            if "".join("".join(lines).split()) != "".join(text.split()):
                findings.append({"level": "error", "gate": "korean_wrap_text_changed",
                                 "slide": slide_no, "detail": "줄바꿈 결과에서 원문 문자가 달라졌어요"})
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Run automated review gates over one episode.")
    ap.add_argument("--story", required=True, help="story.json / episode JSON path")
    ap.add_argument("--caption", default="", help="caption text file (overrides story caption)")
    ap.add_argument("--caption-text", default="", help="caption text inline (overrides story caption)")
    ap.add_argument("--channel", default="", help="channel YAML (caption.format, caption.emoji_policy)")
    ap.add_argument("--format", default="", dest="fmt", help="caption format override (e.g. animal_v2, property)")
    ap.add_argument("--emoji-policy", default="",
                    help="'none' (default), 'allow', or comma-separated allowed emoji")
    ap.add_argument("--images", default="", help="rendered slides directory to verify")
    ap.add_argument("--font", default=DEFAULT_FONT, help="font for Korean rendering check")
    ap.add_argument("--wrap-width", type=int, default=DEFAULT_WRAP_WIDTH,
                    help="text width in pixels for the Korean slide wrapping check (default: 952)")
    ap.add_argument("--no-font-check", action="store_true", help="skip Korean rendering check")
    args = ap.parse_args()
    if args.wrap_width < 1:
        ap.error("--wrap-width must be positive")

    story, err = _read_json(Path(args.story))
    if err:
        print(json.dumps({"error": err}, ensure_ascii=False, indent=2))
        return 2
    if not isinstance(story, dict):
        print(json.dumps({"error": f"story JSON is not an object: {args.story}"},
                         ensure_ascii=False, indent=2))
        return 2

    channel_format = args.fmt
    emoji_policy: object = args.emoji_policy
    if args.channel:
        channel, err = _load_channel(Path(args.channel))
        if err:
            print(json.dumps({"error": err}, ensure_ascii=False, indent=2))
            return 2
        caption_cfg = channel.get("caption") or {}
        if not channel_format:
            channel_format = str(caption_cfg.get("format", "") or "")
        if not emoji_policy:
            emoji_policy = caption_cfg.get("emoji_policy", "none")
    if not channel_format:
        channel_format = "animal_v2"
    if not emoji_policy:
        emoji_policy = "none"
    if isinstance(emoji_policy, str) and emoji_policy not in ("none", "allow"):
        emoji_policy = [e for e in emoji_policy.split(",") if e]

    slides = _normalize_slides(story.get("slides"))
    caption = args.caption_text
    if args.caption:
        try:
            caption = Path(args.caption).read_text(encoding="utf-8")
        except OSError as exc:
            print(json.dumps({"error": f"caption file unreadable: {args.caption}: {exc}"},
                             ensure_ascii=False, indent=2))
            return 2
    if not caption and not args.caption and not args.caption_text:
        caption = str(story.get("caption", "") or "")

    checks_run: list[str] = []
    checks_skipped: list[str] = []
    findings: list[dict] = []

    # Slide texts (property headlines use relaxed length limits: the format
    # is headline + support lines, not one 15-28 char copy line).
    if channel_format == "property":
        findings += gates.check_slide_texts(
            slides, hook_range=(0, 10 ** 6), max_chars_no_space=10 ** 6, max_lines=10)
    else:
        findings += gates.check_slide_texts(slides)
    checks_run.append("slide_texts")

    # Caption (skipped only when no caption text is available anywhere).
    if caption.strip():
        findings += gates.check_caption(
            caption, channel_format=channel_format, emoji_policy=emoji_policy)
        checks_run.append("caption")
    else:
        checks_skipped.append("caption (no caption text found)")

    # Image prompts: only for generated-photo episodes (slides carry them).
    if any("image_prompt" in s for s in slides):
        findings += gates.check_prompts({**story, "slides": slides})
        checks_run.append("prompts")
    else:
        checks_skipped.append("prompts (no image_prompt fields)")

    # Continuity: required for animal stories; property episodes have none.
    if "continuity" in story or channel_format == "animal_v2":
        findings += gates.check_continuity({**story, "slides": slides})
        checks_run.append("continuity")
    else:
        checks_skipped.append("continuity (no continuity block)")

    if args.images:
        findings += _check_images(Path(args.images), len(slides))
        checks_run.append("images")

    if not args.no_font_check:
        texts = [(s["n"], s["text"]) for s in slides]
        if caption.strip():
            texts.append((None, caption))
        note = _check_korean_rendering(texts, Path(args.font), findings,
                                       wrap_width=args.wrap_width)
        if note:
            checks_skipped.append(note)
        else:
            checks_run.append("korean_rendering")

    errors = sum(1 for f in findings if f["level"] == "error")
    warnings = sum(1 for f in findings if f["level"] == "warning")
    report = {
        "story": args.story,
        "channel_format": channel_format,
        "emoji_policy": emoji_policy,
        "checks_run": checks_run,
        "checks_skipped": checks_skipped,
        "engine": {"word_boundaries": word_boundary_engine()},
        "passed": errors == 0,
        "errors": errors,
        "warnings": warnings,
        "findings": findings,
        "checklist": gates.human_checklist(),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"check_episode: {'PASS' if errors == 0 else 'FAIL'} "
          f"({errors} errors, {warnings} warnings)", file=sys.stderr)
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
