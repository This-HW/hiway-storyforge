"""PIL template compositing (SPEC FR-4). Pure function module.

Template v1: cover-crop to 4:5, dark gradient at the bottom, bold text with
one optional highlighted word in the accent color.

Korean text goes through :mod:`storyforge.korean_text` (PLAYBOOK §6.2):
RAQM font loading, morphological word-boundary wrapping, and a
post-render validation check. The old character-by-character wrap is kept
only as a safety net for single words longer than the line width.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .korean_text import load_korean_font, validate_korean_text, wrap_korean_text

_FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/Library/Fonts/NotoSansCJK-Bold.ttc",
]


def find_font(configured: str = "") -> str:
    if configured and Path(configured).exists():
        return configured
    for cand in _FONT_CANDIDATES:
        if Path(cand).exists():
            return cand
    return ""


def _cover_crop(img: Image.Image, width: int, height: int) -> Image.Image:
    src_ratio = img.width / img.height
    dst_ratio = width / height
    if src_ratio > dst_ratio:
        new_h = img.height
        new_w = int(new_h * dst_ratio)
    else:
        new_w = img.width
        new_h = int(new_w / dst_ratio)
    left = (img.width - new_w) // 2
    top = (img.height - new_h) // 2
    return img.crop((left, top, left + new_w, top + new_h)).resize((width, height))


def _gradient_overlay(img: Image.Image, ratio: float = 0.45) -> Image.Image:
    width, height = img.size
    grad_h = int(height * ratio)
    gradient = Image.new("L", (1, grad_h))
    for y in range(grad_h):
        gradient.putpixel((0, y), int(200 * (y / max(grad_h - 1, 1)) ** 1.5))
    gradient = gradient.resize((width, grad_h))
    black = Image.new("RGB", (width, grad_h), (0, 0, 0))
    out = img.convert("RGB")
    out.paste(black, (0, height - grad_h), gradient)
    return out


def _hard_split(draw: ImageDraw.ImageDraw, line: str, font, max_width: int) -> list[str]:
    """Character-by-character split; safety net for over-wide single words."""
    out: list[str] = []
    current = ""
    for ch in line:
        trial = current + ch
        if draw.textlength(trial, font=font) <= max_width or not current:
            current = trial
        else:
            out.append(current)
            current = ch
    if current:
        out.append(current)
    return out


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    """Word-boundary wrap via korean_text; hard-split any line still too wide."""
    lines = [ln for ln in wrap_korean_text(text, font, max_width, draw) if ln.strip()]
    out: list[str] = []
    for line in lines:
        if draw.textlength(line, font=font) <= max_width:
            out.append(line)
        else:
            out.extend(_hard_split(draw, line, font, max_width))
    return out


def render(image_path: str, text: str, out_path: str, *,
           highlight: str = "", width: int = 1080, height: int = 1350,
           font_path: str = "", font_size: int = 64,
           text_color: str = "#FFFFFF", accent_color: str = "#FFE600",
           strict: bool = False) -> str:
    """Composite caption text onto an image (4:5 JPEG).

    With a real font file, the font is loaded with the RAQM layout engine
    and the text is validated after wrapping (isolated jamo / zero-width
    characters). ``strict=True`` raises ValueError on validation issues
    instead of rendering anyway; the default keeps the old lenient
    behaviour for callers that validate separately.
    """
    img = Image.open(image_path).convert("RGB")
    img = _cover_crop(img, width, height)
    img = _gradient_overlay(img)
    draw = ImageDraw.Draw(img)
    font_file = find_font(font_path)
    if font_file:
        font = load_korean_font(font_file, font_size)
    else:
        font = ImageFont.load_default()
    margin = int(width * 0.06)
    max_w = width - margin * 2
    lines = _wrap(draw, text, font, max_w)
    if font_file:
        issues = validate_korean_text(text, font, draw)
        if issues and strict:
            raise ValueError(f"한국어 렌더링 문제: {issues}")
    line_h = int(font_size * 1.35)
    y = height - margin - line_h * len(lines)
    for line in lines:
        x = margin
        if highlight and highlight in line:
            before, _, after = line.partition(highlight)
            if before:
                draw.text((x, y), before, font=font, fill=text_color)
                x += draw.textlength(before, font=font)
            draw.text((x, y), highlight, font=font, fill=accent_color)
            x += draw.textlength(highlight, font=font)
            if after:
                draw.text((x, y), after, font=font, fill=text_color)
        else:
            draw.text((x, y), line, font=font, fill=text_color)
        y += line_h
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "JPEG", quality=92)
    return out_path
