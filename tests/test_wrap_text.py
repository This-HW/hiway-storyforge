from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw

from scripts import check_episode
from storyforge import korean_text, render


@pytest.mark.parametrize(
    "text",
    [
        "어릴 때부터 함께 자란 셋은 가족이 됐어요",
        "태어날 때부터 듣지도 보지도 못했어요",
        "태어났을 때 몸무게는 1파운드도 안 됐어요",
    ],
)
def test_wrapping_preserves_inflected_words(text):
    font_path = render.find_font()
    if not font_path:
        pytest.skip("no CJK font available")
    font = korean_text.load_korean_font(font_path, 64)
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines = render._wrap(draw, text, font, 700)
    assert len(lines) > 1
    assert " ".join(lines).split() == text.split()
    assert all(draw.textlength(line, font=font) <= 700 for line in lines)


def test_word_boundaries_fall_back_if_tokens_omit_source_text(monkeypatch):
    text = "어릴\t때부터"
    incomplete = SimpleNamespace(tokenize=lambda _: [SimpleNamespace(start=3, len=3, tag="NNG")])
    monkeypatch.setattr(korean_text, "_kiwi", incomplete)
    monkeypatch.setattr(korean_text, "_HAS_KIWI", True)
    assert [text[start:end] for start, end in korean_text.get_word_boundaries(text)] == [
        "어릴", "때부터",
    ]


def test_episode_gate_rejects_changed_wrap(monkeypatch, tmp_path):
    font_path = tmp_path / "fixture.ttf"
    font_path.touch()
    monkeypatch.setattr(check_episode, "load_korean_font", lambda *_: object())
    monkeypatch.setattr(check_episode, "validate_korean_text", lambda *_: [])
    monkeypatch.setattr(check_episode, "wrap_korean_text", lambda *_: ["때부터"])
    findings = []
    assert check_episode._check_korean_rendering(
        [(4, "어릴 때부터")], font_path, findings, wrap_width=952,
    ) is None
    assert [(issue["level"], issue["gate"], issue["slide"]) for issue in findings] == [
        ("error", "korean_wrap_text_changed", 4),
    ]
