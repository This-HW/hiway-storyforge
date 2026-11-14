"""Prompt assembly: continuity + tone enforcement at build time.

``build_slide_prompt`` assembles one slide's image prompt from the
continuity sheet and the channel's tone values, so producers do not have
to remember every token by hand. It complements ``gates.check_prompts``,
which verifies already-written prompts.

Design notes (CONTINUITY_SHEET + ADR-0011 §4):
- Identity is carried by the reference chain (scene_1 + previous scene),
  not by re-describing appearance in every prompt. The identity anchor is
  therefore included only on the establishing slide by default
  (``anchor_on="first"``); pass ``anchor_on="all"`` only when the
  generator has no reference input.
- Environment markers and the light/palette line go on every slide: they
  are short and they are what keeps the background and light unified.
- Tone values come from the caller (channel config), never from
  hard-coded channel data in this module.

Pure functions, no imports from other storyforge modules.
"""
from __future__ import annotations


def _first_clause(text: str, max_chars: int = 140) -> str:
    """First clause of a continuity value (identity anchor)."""
    for sep in (" — ", " – ", ". ", ", ", "，"):
        if sep in text:
            text = text.split(sep, 1)[0]
            break
    text = text.strip().rstrip(",.")
    return text[:max_chars].strip()


def _join(values) -> str:
    if isinstance(values, str):
        return values.strip()
    return ", ".join(str(v).strip() for v in values if str(v).strip())


def build_slide_prompt(*, action: str, continuity: dict | None = None,
                       tone: dict | None = None, slide_n: int = 1,
                       total_slides: int = 8,
                       anchor_on: str = "first") -> str:
    """Assemble a slide image prompt from continuity + tone values.

    Args:
        action: what happens in this slide (the scene-specific part).
        continuity: {"identity", "env_markers", "props", "light_palette"}.
        tone: {"tokens": [...], "photoreal": str, "no_text": str,
               "framing_slide1": str}. Missing keys are skipped.
        slide_n: 1-based slide number.
        anchor_on: "first" (identity anchor on slide 1 only), "all", or
            "none".
    """
    continuity = continuity or {}
    tone = tone or {}
    parts: list[str] = []

    def _add(part: str) -> None:
        part = (part or "").strip().rstrip(",")
        if not part:
            return
        lowered = ", ".join(parts).lower()
        if part.lower() in lowered:
            return
        parts.append(part)

    include_anchor = (
        anchor_on == "all"
        or (anchor_on == "first" and slide_n == 1)
    )
    if include_anchor:
        _add(_first_clause(str(continuity.get("identity", "") or "")))
    _add(action)
    _add(_join(continuity.get("env_markers", "")))
    _add(_join(continuity.get("light_palette", "")))
    if slide_n == 1:
        _add(_join(continuity.get("props", "")))
        _add(str(tone.get("framing_slide1", "") or ""))
    for token in tone.get("tokens", []) or []:
        _add(str(token))
    _add(str(tone.get("photoreal", "") or ""))
    _add(str(tone.get("no_text", "") or ""))
    return ", ".join(parts)
