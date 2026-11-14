"""Automated review gates for episode production.

Mechanical checks only: what can be decided from slide texts, captions,
image prompts, and continuity metadata alone. They encode the checkable
parts of STYLE_RULES §1.10 (scene-narrative match), §1.11 (logic review),
tone v2, and docs/CONTINUITY_SHEET.md.

What is intentionally NOT automated: visual judgments (§1.10's five items
need eyes on the rendered image) and semantic judgments (§1.11's "why?"
gate, subject-omission sense, emotional match). ``human_checklist()``
returns those as explicit items so a report never pretends they were
automated — a gate run must always surface them alongside findings.

Pure functions, no imports from other storyforge modules (same pattern as
rules.py). Thresholds are parameters, not hard-coded channel values:
callers pass them from channel config.

Finding shape: {"level": "error"|"warning", "gate": str,
                "slide": int|None, "detail": str}
"""
from __future__ import annotations

import re

# --- emoji detection ---------------------------------------------------------
# Broad ranges covering emoticons, pictographs, transport, symbols.
# Variation selectors / ZWJ are not matched; the base character is enough
# to flag the emoji.
_EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\u2600-\u26FF"
    "\u2700-\u27BF"
    "]",
    re.UNICODE,
)

# Formal endings banned by the haeyo-che rule (STYLE_RULES §1.1): a formal
# ending followed by sentence punctuation, whitespace, a quote, or end of
# text. Matching mid-word is avoided by the lookahead.
_FORMAL_ENDING_RE = re.compile(
    r"(습니다|입니다|합니다|됩니다|습니까|입니까)(?=[.!?…\s\"'’”)\]]|$)"
)

_URL_RE = re.compile(r"https?://|www\.")
_HASHTAG_RE = re.compile(r"#\S+")

# Age units -> weeks (approximate, for monotonicity only).
_AGE_UNIT_WEEKS = {"일": 1 / 7, "주": 1.0, "개월": 4.33, "살": 52.0, "세": 52.0, "년": 52.0}
_AGE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(일|주|개월|살|세|년)")
_ADULT_MARKERS = ("성묘", "성견", "성체", "어른", "노견", "노묘", "노령", "노년")
_ADULT_WEEKS = 10000.0  # orders after any kitten/puppy age
# Qualitative ages get ordinal values so "새끼 -> 어린 -> 성체" timelines
# order correctly without inventing false precision.
_YOUNG_MARKERS = (("새끼", 4.0), ("아기", 4.0), ("어린", 26.0), ("어릴", 26.0))


def _finding(level: str, gate: str, detail: str, slide: int | None = None) -> dict:
    return {"level": level, "gate": gate, "slide": slide, "detail": detail}


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _slides_of(slides: list) -> list[tuple[int, str]]:
    """Normalize slide inputs to (n, text) pairs.

    Accepts dicts with "n"/"text", dicts with "text" only, or plain strings.
    """
    out: list[tuple[int, str]] = []
    for i, sl in enumerate(slides or []):
        if isinstance(sl, dict):
            n = sl.get("n", i + 1)
            try:
                n = int(n)
            except (TypeError, ValueError):
                n = i + 1
            out.append((n, str(sl.get("text", "") or "")))
        else:
            out.append((i + 1, str(sl or "")))
    return out


# --- slide texts (§1.11 mechanical proxies + format rules) -------------------

def check_slide_texts(slides: list, *, hook_range: tuple[int, int] = (15, 25),
                      max_chars_no_space: int = 45,
                      max_lines: int = 2) -> list[dict]:
    """Check slide copy text for format and seam problems.

    - empty / duplicated / over-long texts (errors)
    - adjacent slides opening with the same words (error: seam/duplicate)
    - slide-1 hook length outside the configured range (warning)
    - 3+ consecutive slides ending with the same final word (warning:
      monotonous "~요 ~요 ~요" rhythm)
    """
    findings: list[dict] = []
    pairs = _slides_of(slides)
    seen: dict[str, int] = {}
    prev_norm = ""
    prev_n: int | None = None
    ending_run: list[int] = []
    prev_ending = ""
    for n, text in pairs:
        stripped = text.strip()
        if not stripped:
            findings.append(_finding("error", "slide_text_empty",
                                     "슬라이드 텍스트가 비어 있다", n))
            continue
        lines = stripped.split("\n")
        if len(lines) > max_lines:
            findings.append(_finding(
                "error", "slide_text_lines",
                f"줄 수 {len(lines)}줄 (최대 {max_lines}줄)", n))
        norm = _norm(stripped)
        if n == 1:
            lo, hi = hook_range
            if not lo <= len(norm) <= hi:
                findings.append(_finding(
                    "warning", "hook_length",
                    f"1장 후킹 {len(norm)}자 (권장 {lo}~{hi}자, 공백 제외)", n))
        elif len(norm) > max_chars_no_space:
            findings.append(_finding(
                "error", "slide_text_length",
                f"{len(norm)}자 (최대 {max_chars_no_space}자, 공백 제외)", n))
        if norm in seen:
            findings.append(_finding(
                "error", "slide_text_duplicate",
                f"{seen[norm]}장과 동일한 텍스트", n))
        else:
            seen[norm] = n
        if prev_n is not None and n == prev_n + 1 and len(norm) >= 8 and len(prev_norm) >= 8:
            if norm[:8] == prev_norm[:8]:
                findings.append(_finding(
                    "error", "adjacent_opening_duplicate",
                    f"{prev_n}장과 시작 8자가 동일: '{norm[:8]}'", n))
        # Monotone endings: same final word 3+ slides in a row.
        words = stripped.replace("\n", " ").split()
        ending = words[-1].rstrip(".!?…") if words else ""
        if ending and ending == prev_ending:
            ending_run.append(n)
        else:
            ending_run = [n]
        if len(ending_run) >= 3:
            findings.append(_finding(
                "warning", "monotone_endings",
                f"{ending_run[0]}~{n}장까지 같은 어미 반복: '{ending}'", n))
            ending_run = []
        prev_ending = ending
        prev_norm, prev_n = norm, n
    return findings


# --- captions (§1.7 / §1.9, emoji policy, haeyo-che) -------------------------

def check_caption(caption: str, *, channel_format: str = "animal_v2",
                  emoji_policy="none", require_source_line: bool | None = None,
                  hashtag_range: tuple[int, int] = (3, 5)) -> list[dict]:
    """Check a caption against the channel's caption rules.

    ``emoji_policy``: "none" (default, standing rule) bans every emoji;
    a list/set/tuple allows exactly those characters; "allow" skips the
    check. The policy value comes from channel config, not from here.
    """
    findings: list[dict] = []
    text = caption or ""
    if not text.strip():
        return [_finding("error", "caption_empty", "캡션이 비어 있다")]

    # Emoji policy.
    if emoji_policy != "allow":
        allowed = set(emoji_policy) if isinstance(emoji_policy, (list, tuple, set)) else set()
        for lineno, line in enumerate(text.split("\n"), 1):
            for ch in _EMOJI_RE.findall(line):
                if ch not in allowed:
                    findings.append(_finding(
                        "error", "emoji_policy",
                        f"{lineno}행에 이모지 '{ch}' (정책: {emoji_policy})"))

    # URLs: Instagram captions cannot carry clickable links (animal v2).
    if _URL_RE.search(text):
        level = "error" if channel_format == "animal_v2" else "warning"
        findings.append(_finding(level, "caption_url",
                                 "캡션에 URL이 있다 (인스타 캡션 URL은 클릭 불가)"))

    # Formal endings: haeyo-che required on both channels.
    for m in _FORMAL_ENDING_RE.finditer(text):
        start = max(0, m.start() - 12)
        snippet = text[start:m.end()].replace("\n", " ")
        findings.append(_finding(
            "error", "formal_ending",
            f"합니다체 어미 '{m.group(1)}' 발견: '...{snippet}'"))

    # Hook: first non-empty line, 15-25 chars excl. spaces (animal v2 §1.9).
    lines = [ln for ln in text.split("\n")]
    first = next((ln for ln in lines if ln.strip()), "")
    if channel_format == "animal_v2":
        hook_len = len(_norm(first))
        if not 15 <= hook_len <= 25:
            findings.append(_finding(
                "warning", "caption_hook",
                f"첫 줄 후킹 {hook_len}자 (권장 15~25자, 공백 제외)"))

    # Source line: required for animal v2 ("원본 출처:"), off for property.
    if require_source_line is None:
        require_source_line = channel_format == "animal_v2"
    if require_source_line and "원본 출처" not in text:
        findings.append(_finding("error", "source_line_missing",
                                 "'원본 출처:' 표기가 없다"))

    # Hashtags: count in range, and only in the trailing block.
    tags = _HASHTAG_RE.findall(text)
    lo, hi = hashtag_range
    if not lo <= len(tags) <= hi:
        findings.append(_finding(
            "warning", "hashtag_count",
            f"해시태그 {len(tags)}개 (권장 {lo}~{hi}개)"))
    nonempty = [ln for ln in lines if ln.strip()]
    trailing = 0
    for ln in reversed(nonempty):
        if _HASHTAG_RE.search(ln) and not re.sub(r"#\S+\s*", "", ln).strip():
            trailing += 1
        else:
            break
    body_lines = nonempty[:len(nonempty) - trailing] if trailing else nonempty
    if any(_HASHTAG_RE.search(ln) for ln in body_lines):
        findings.append(_finding("warning", "hashtag_position",
                                 "해시태그가 본문 중간에 있다 (끝 블록으로 이동)"))

    # Property CTA: at most one CTA-ish line (comment/save/share/follow ask).
    if channel_format == "property":
        cta_lines = [ln for ln in lines
                     if re.search(r"댓글|저장해|공유해|팔로우", ln)]
        if len(cta_lines) > 1:
            findings.append(_finding(
                "warning", "cta_duplicate",
                f"CTA성 문구가 {len(cta_lines)}줄 (1줄 권장)"))
    return findings


# --- image prompts (tone v2 + continuity tokens) -----------------------------

def check_prompts(story: dict, *,
                  tone_tokens: tuple[str, ...] = ("golden backlight", "bokeh"),
                  require_photoreal: bool = True,
                  require_no_text: bool = True,
                  framing_markers: tuple[str, ...] = (
                      "two-thirds", "looking at", "looking into",
                      "close-up", "close up", "face fills")) -> list[dict]:
    """Check per-slide image prompts for tone-v2 / continuity tokens.

    Identity itself is carried by the reference chain (scene_1 + previous
    scene), not by prompt wording, so this gate checks the checkable
    tokens — tone, photorealism, no-text, slide-1 framing — and warns when
    no reference-chain metadata is recorded in the story at all.
    """
    findings: list[dict] = []
    slides = story.get("slides") or []
    if not slides:
        return [_finding("error", "prompts_missing", "slides가 비어 있다")]
    ref_keys = ("refs", "references", "ref_images")
    any_ref_meta = False
    for i, sl in enumerate(slides):
        n = sl.get("n", i + 1) if isinstance(sl, dict) else i + 1
        if not isinstance(sl, dict):
            findings.append(_finding("error", "prompt_missing",
                                     "슬라이드 형식이 dict가 아니다", n))
            continue
        prompt = str(sl.get("image_prompt", "") or "")
        if any(k in sl for k in ref_keys):
            any_ref_meta = True
            refs = sl.get("refs", sl.get("references", sl.get("ref_images")))
            if n and n > 1 and isinstance(refs, list):
                if not refs:
                    findings.append(_finding(
                        "warning", "continuity_refs",
                        "직전 장면 참조가 비어 있다 (scene_1 + 직전 장면 참조 필요)", n))
                elif all(isinstance(r, int) for r in refs) and (n - 1) not in refs:
                    findings.append(_finding(
                        "warning", "continuity_refs",
                        f"직전 장면({n - 1}장) 참조가 refs에 없다: {refs}", n))
        if not prompt.strip():
            findings.append(_finding("error", "prompt_missing",
                                     "image_prompt가 비어 있다", n))
            continue
        lowered = prompt.lower()
        for token in tone_tokens:
            if token.lower() not in lowered:
                findings.append(_finding(
                    "error", "tone_token_missing",
                    f"톤 토큰 누락: '{token}'", n))
        if require_photoreal and "photoreal" not in lowered:
            findings.append(_finding("error", "photoreal_missing",
                                     "실사 토큰(photorealistic) 누락", n))
        if require_no_text and "no text" not in lowered:
            findings.append(_finding("error", "no_text_missing",
                                     "'no text' 토큰 누락 (이미지 내 텍스트 생성 방지)", n))
        if n == 1 and not any(m in lowered for m in framing_markers):
            findings.append(_finding(
                "error", "slide1_framing",
                "1장 프레이밍(얼굴 2/3+카메라 응시) 표현이 없다", n))
    if not any_ref_meta:
        findings.append(_finding(
            "warning", "continuity_refs",
            "참조 체인(scene_1 + 직전 장면) 메타데이터가 story에 기록되지 않음 — "
            "생성 시 참조가 실제로 사용됐는지 이 파일만으로는 확인 불가"))
    return findings


# --- continuity sheet ----------------------------------------------------------

def _parse_age_weeks(value: str) -> float | None:
    if not value:
        return None
    # First plausible age expression; skip 4-digit calendar years
    # ("2012년" is a year, not an age of 2012 years).
    for m in _AGE_RE.finditer(str(value)):
        number = m.group(1)
        if len(number.split(".")[0]) == 4:
            continue
        return float(number) * _AGE_UNIT_WEEKS[m.group(2)]
    if any(marker in str(value) for marker in _ADULT_MARKERS):
        return _ADULT_WEEKS
    for marker, weeks in _YOUNG_MARKERS:
        if marker in str(value):
            return weeks
    return None


def _timeline_entries(age_timeline) -> list[tuple[int, str, str]]:
    """Normalize age_timeline to (order, label, age_text) triples."""
    entries: list[tuple[int, str, str]] = []
    if isinstance(age_timeline, dict):
        for order, (key, val) in enumerate(age_timeline.items()):
            if isinstance(val, dict):
                age_text = str(val.get("age", val.get("text", "")) or "")
            else:
                age_text = str(val or "")
            m = re.search(r"\d+", str(key))
            slide_no = int(m.group()) if m else order + 1
            entries.append((slide_no, str(key), age_text))
    elif isinstance(age_timeline, list):
        for order, item in enumerate(age_timeline):
            if isinstance(item, dict):
                slide_no = item.get("slide", item.get("n", order + 1))
                try:
                    slide_no = int(slide_no)
                except (TypeError, ValueError):
                    slide_no = order + 1
                age_text = str(item.get("age", item.get("text", "")) or "")
                entries.append((slide_no, str(item.get("label", slide_no)), age_text))
            else:
                entries.append((order + 1, str(order + 1), str(item or "")))
    entries.sort(key=lambda e: e[0])
    return entries


def check_continuity(story: dict, *,
                     slide_range: tuple[int, int] = (8, 12)) -> list[dict]:
    """Check the continuity block and age-timeline monotonicity."""
    findings: list[dict] = []
    continuity = story.get("continuity")
    if not isinstance(continuity, dict):
        return [_finding("error", "continuity_missing",
                         "continuity 블록이 없다 (CONTINUITY_SHEET 필수)")]
    for field in ("identity", "env_markers", "props", "light_palette"):
        if field not in continuity:
            findings.append(_finding(
                "error", "continuity_field_missing",
                f"continuity.{field} 키가 없다"))
            continue
        val = continuity[field]
        if val is None or (isinstance(val, (str, list, dict)) and not val):
            if field in ("props", "env_markers"):
                # An explicit empty list is a legitimate production state
                # ("no recurring props"); it only deserves a nudge.
                findings.append(_finding(
                    "warning", "continuity_field_empty",
                    f"continuity.{field}가 비어 있다 (소품/장소 없음이 의도된 것인지 확인)"))
            else:
                findings.append(_finding(
                    "error", "continuity_field_missing",
                    f"continuity.{field}가 비어 있다"))
    timeline = continuity.get("age_timeline")
    if timeline is None:
        findings.append(_finding(
            "warning", "age_timeline_missing",
            "age_timeline이 없다 (성장 서사는 나이 단조성 확인 불가)"))
    else:
        prev_weeks: float | None = None
        prev_label = ""
        for slide_no, label, age_text in _timeline_entries(timeline):
            weeks = _parse_age_weeks(age_text)
            if weeks is None:
                findings.append(_finding(
                    "warning", "age_unparseable",
                    f"'{label}': 나이 파싱 불가 ('{age_text}')", slide_no))
                continue
            if prev_weeks is not None and weeks < prev_weeks:
                # Warning, not error: hook-then-flashback is a standard
                # structure here (story opens in the present, then rewinds),
                # so a decrease is a "confirm it's intentional" signal.
                findings.append(_finding(
                    "warning", "age_regression",
                    f"나이가 역행: '{prev_label}' 이후 '{label}' "
                    f"({age_text}) — 플래시백 구조라면 의도된 것인지 확인", slide_no))
            prev_weeks, prev_label = weeks, label
    slides = story.get("slides") or []
    lo, hi = slide_range
    if slides and not lo <= len(slides) <= hi:
        findings.append(_finding(
            "warning", "slide_count",
            f"슬라이드 {len(slides)}장 (기본형 {lo}~{hi}장)"))
    return findings


# --- human checklist: what automation must NOT claim to verify ----------------

def human_checklist() -> list[dict]:
    """Review items that need human eyes. Always surfaced with gate reports."""
    return [
        {"gate": "§1.10 피사체 완전성", "item": "핵심 피사체가 잘리거나 변형되지 않았는지 이미지로 확인했는가"},
        {"gate": "§1.10 행동 순간 일치", "item": "글의 행동·순간과 이미지의 동작이 같은 장면인가"},
        {"gate": "§1.10 감정 상태 일치", "item": "글의 감정과 동물의 표정·자세가 일치하는가"},
        {"gate": "§1.10 연속성", "item": "전 장과 외형·배경·소품·조명이 이어지는가 (참조 체인 확인)"},
        {"gate": "§1.10 환경 일치", "item": "글이 지시하는 장소·시간대와 이미지 배경이 맞는가"},
        {"gate": "§1.11 이음새", "item": "슬라이드 전환 시 '그래서?/왜 갑자기?'가 나오지 않는가 (브릿지 필요 여부)"},
        {"gate": "§1.11 풀어서 설명", "item": "축약 없이 풀어 썼는가, 어미 리듬이 자연스러운가"},
        {"gate": "§1.11 왜?에 답하기", "item": "독자가 물을 '왜 하필?'에 미리 답했는가"},
        {"gate": "톤 v2", "item": "1장 얼굴 2/3 이상 + 카메라 응시 + 하단 큰 자막인가, 귀여움 다이얼이 실사 범위인가, 황금빛 역광+보케가 통일되는가"},
        {"gate": "주어 명시", "item": "카피 문장의 주어가 생략되지 않고 명시됐는가"},
        {"gate": "한글 렌더링", "item": "합성 이미지에서 글자 깨짐·넘침·잘림이 없는가 (실제 파일로 확인)"},
    ]


# --- combined run --------------------------------------------------------------

def run_all(story: dict, caption: str | None = None, *,
            channel_format: str = "animal_v2", emoji_policy="none",
            **kwargs) -> dict:
    """Run every automated gate over one episode.

    ``caption`` defaults to ``story["caption"]``. Extra keyword arguments
    are forwarded to the individual check functions when they accept them.
    Returns {"findings": [...], "checklist": [...], "passed": bool,
    "errors": int, "warnings": int}.
    """
    slides = story.get("slides") or []
    text_kwargs = {k: kwargs[k] for k in
                   ("hook_range", "max_chars_no_space", "max_lines") if k in kwargs}
    caption_kwargs = {k: kwargs[k] for k in
                      ("require_source_line", "hashtag_range") if k in kwargs}
    prompt_kwargs = {k: kwargs[k] for k in
                     ("tone_tokens", "require_photoreal", "require_no_text",
                      "framing_markers") if k in kwargs}
    continuity_kwargs = {k: kwargs[k] for k in ("slide_range",) if k in kwargs}
    findings: list[dict] = []
    findings += check_slide_texts(slides, **text_kwargs)
    findings += check_caption(
        caption if caption is not None else str(story.get("caption", "") or ""),
        channel_format=channel_format, emoji_policy=emoji_policy, **caption_kwargs)
    findings += check_prompts(story, **prompt_kwargs)
    findings += check_continuity(story, **continuity_kwargs)
    errors = sum(1 for f in findings if f["level"] == "error")
    warnings = sum(1 for f in findings if f["level"] == "warning")
    return {
        "findings": findings,
        "checklist": human_checklist(),
        "passed": errors == 0,
        "errors": errors,
        "warnings": warnings,
    }
