"""
Korean text rendering utilities for storyforge.

Provides:
- Font loading with RAQM layout engine for proper Hangul shaping
- Natural Korean line breaking using kiwipiepy morphological analysis
- Text validation (detect broken characters, unsupported glyphs)

Usage:
    from storyforge.korean_text import load_korean_font, wrap_korean_text

    font = load_korean_font("/path/to/NotoSansCJK-Bold.ttc", 58)
    lines = wrap_korean_text("긴 한국어 텍스트입니다", font, max_width=900, draw=draw)
"""

from PIL import ImageFont, features

try:
    from kiwipiepy import Kiwi
    _kiwi = Kiwi()
    _HAS_KIWI = True
except ImportError:
    _kiwi = None
    _HAS_KIWI = False


def word_boundary_engine() -> str:
    """Which word-boundary engine is active.

    Returns "kiwipiepy" when morphological analysis is available, else
    "space-split". Callers (preflight, gate reports) use this to surface
    the silent fallback: without kiwipiepy, wrapping degrades to
    space-based splitting and mid-phrase breaks become more likely.
    """
    return "kiwipiepy" if _HAS_KIWI else "space-split"


def load_korean_font(path, size, index=0):
    """Load a font with RAQM layout engine for proper Korean rendering.

    RAQM (via libraqm) handles complex text layout including proper
    Hangul syllable composition and spacing.
    """
    if not features.check_feature("raqm"):
        return ImageFont.truetype(path, size, index=index, layout_engine=ImageFont.Layout.BASIC)
    try:
        return ImageFont.truetype(
            path, size, index=index,
            layout_engine=ImageFont.Layout.RAQM,
        )
    except Exception:
        # Fallback: try without index, then without RAQM
        try:
            return ImageFont.truetype(
                path, size,
                layout_engine=ImageFont.Layout.RAQM,
            )
        except Exception:
            return ImageFont.truetype(path, size)


def get_word_boundaries(text):
    """Get natural word break positions for Korean text.

    Uses kiwipiepy morphological analysis when available.
    Falls back to space-based splitting.
    Returns list of (start, end) character indices for each word unit.
    """
    if not _HAS_KIWI:
        # Fallback: split on spaces, keep spaces attached to previous word
        words = []
        start = 0
        for i, ch in enumerate(text):
            if ch == ' ':
                if i > start:
                    words.append((start, i))
                start = i + 1
        if start < len(text):
            words.append((start, len(text)))
        return words

    tokens = _kiwi.tokenize(text)
    words = []
    pos = 0
    for token in tokens:
        form = token.form
        # Find token position in text (skip spaces)
        idx = text.find(form, pos)
        if idx == -1:
            continue
        # Merge particles/endings with previous word for natural breaks
        # Tags that attach to previous: J* (particles), E* (endings)
        if words and (token.tag.startswith('J') or token.tag.startswith('E')):
            prev_start, _ = words[-1]
            words[-1] = (prev_start, idx + len(form))
        else:
            words.append((idx, idx + len(form)))
        pos = idx + len(form)

    return words


def wrap_korean_text(text, font, max_width, draw):
    """Wrap Korean text to fit max_width, breaking at natural word boundaries.

    Args:
        text: Korean text to wrap
        font: PIL font (loaded with load_korean_font)
        max_width: maximum pixel width per line
        draw: ImageDraw object for measuring text

    Returns:
        List of lines, each fitting within max_width
    """
    # Respect existing manual line breaks first
    paragraphs = text.split('\n')
    result = []

    for para in paragraphs:
        if not para.strip():
            result.append('')
            continue

        # Check if whole paragraph fits
        if draw.textlength(para, font=font) <= max_width:
            result.append(para)
            continue

        # Break at word boundaries
        boundaries = get_word_boundaries(para)
        if not boundaries:
            result.append(para)
            continue

        lines = []
        current_start = boundaries[0][0]

        for i, (wstart, wend) in enumerate(boundaries):
            # Try adding this word to current line
            test_end = wend
            # Include trailing space if not last word
            if i + 1 < len(boundaries):
                next_start = boundaries[i + 1][0]
                test_text = para[current_start:next_start].rstrip()
            else:
                test_text = para[current_start:test_end]

            if draw.textlength(test_text, font=font) <= max_width:
                continue
            else:
                # Current line is full, break before this word
                line_text = para[current_start:wstart].rstrip()
                if line_text:
                    lines.append(line_text)
                current_start = wstart

        # Add remaining
        remaining = para[current_start:].strip()
        if remaining:
            lines.append(remaining)

        result.extend(lines)

    return result


def validate_korean_text(text, font, draw):
    """Check text for rendering issues.

    Returns list of (issue_type, detail) tuples.
    - 'tofu': characters that may not render (zero width)
    - 'jamo': isolated jamo that should be composed
    """
    issues = []

    # Check for isolated jamo (U+3131-U+318E) that aren't part of syllables
    import re
    jamo_pattern = re.compile(r'[\u3131-\u318E]')
    for m in jamo_pattern.finditer(text):
        # Check if surrounded by spaces or at word boundary (likely intentional)
        # Otherwise flag as potential issue
        ch = m.group()
        pos = m.start()
        before = text[pos - 1] if pos > 0 else ' '
        after = text[pos + 1] if pos + 1 < len(text) else ' '
        # Single jamo between spaces is likely intentional (e.g., "ㄱ" as label)
        # Jamo attached to other text without spaces is suspicious
        if before != ' ' and after != ' ':
            issues.append(('jamo', f"위치 {pos}: '{ch}' (자모 분리 가능)"))

    # Check for zero-width characters (potential tofu)
    for i, ch in enumerate(text):
        if ch in (' ', '\n', '\t'):
            continue
        try:
            w = draw.textlength(ch, font=font)
            if w == 0:
                issues.append(('tofu', f"위치 {i}: '{ch}' (U+{ord(ch):04X}) 렌더링 안 될 수 있음"))
        except Exception:
            issues.append(('tofu', f"위치 {i}: '{ch}' 측정 실패"))

    return issues
