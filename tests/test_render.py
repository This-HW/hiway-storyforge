import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from storyforge import render
from storyforge.korean_text import word_boundary_engine


class TestRender(unittest.TestCase):
    def test_render_produces_4x5_jpeg(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.jpg"
            Image.new("RGB", (600, 900), (80, 100, 140)).save(src)
            out = Path(tmp) / "out.jpg"
            render.render(str(src), "10년째 이것만 먹은 남자의 몸", str(out),
                          highlight="이것만")
            with Image.open(out) as img:
                self.assertEqual(img.size, (1080, 1350))

    def test_find_font(self):
        # VM/CI dependent: at minimum the function must not crash.
        self.assertIsInstance(render.find_font(), str)

    def test_wrap_breaks_at_word_boundaries(self):
        # Regression guard for PLAYBOOK §6.2: wrapping must not split a
        # word mid-word (the old char-by-char wrap did).
        font_file = render.find_font()
        if not font_file:
            self.skipTest("no CJK font available")
        from storyforge.korean_text import load_korean_font
        font = load_korean_font(font_file, 64)
        draw = ImageDraw.Draw(Image.new("RGB", (1080, 1350)))
        text = "비 오는 날 길에서 만난 작은 강아지가 따뜻한 집을 찾았어요"
        lines = render._wrap(draw, text, font, 500)
        self.assertGreater(len(lines), 1)
        words = text.split()
        seen: list[str] = []
        for line in lines:
            self.assertLessEqual(draw.textlength(line, font=font), 500)
            seen.extend(line.split())
        self.assertEqual(seen, words)
        # Each line must be whole words from the original, in order.
        joined = " ".join(lines)
        self.assertEqual(joined.split(), words)

    def test_render_strict_raises_on_broken_text(self):
        # Isolated jamo attached to other text must fail loudly in strict mode.
        if not render.find_font():
            self.skipTest("no CJK font available")
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.jpg"
            Image.new("RGB", (600, 900), (80, 100, 140)).save(src)
            out = Path(tmp) / "out.jpg"
            with self.assertRaises(ValueError):
                render.render(str(src), "가ㄱ나 테스트", str(out), strict=True)

    def test_word_boundary_engine_reported(self):
        self.assertIn(word_boundary_engine(), ("kiwipiepy", "space-split"))


if __name__ == "__main__":
    unittest.main()
