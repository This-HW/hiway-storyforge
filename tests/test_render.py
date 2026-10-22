import tempfile
import unittest
from pathlib import Path

from PIL import Image

from storyforge import render


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


if __name__ == "__main__":
    unittest.main()
