import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from storyforge.config import load_config
from storyforge.services import Pipeline


def _sample_jpg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (800, 800), (90, 120, 80)).save(buf, "JPEG")
    return buf.getvalue()


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        cfg = load_config()
        cfg["provider"] = "stub"
        self.pipe = Pipeline(cfg, Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def _register(self, rights="확인됨"):
        return self.pipe.register(
            image_bytes=_sample_jpg(), ext=".jpg",
            source="https://example.com/original", rights=rights, topic="동물")

    def test_source_required(self):
        with self.assertRaises(ValueError):
            self.pipe.register(image_bytes=_sample_jpg(), ext=".jpg",
                               source="  ", rights="확인됨", topic="동물")

    def test_full_flow_to_export(self):
        mat = self._register()
        self.pipe.set_fact(mat.id, "키 작고 뚱뚱해서 따돌림 당하던 아기 코끼리")
        mat = self.pipe.generate_copies(mat.id)
        self.assertTrue(mat.copies)
        self.pipe.choose_copy(mat.id, "키 작고 뚱뚱해서\n따돌림 당하던 아기 코끼리",
                              highlight="따돌림")
        mat = self.pipe.render(mat.id)
        self.assertIn("ko", mat.renders)
        self.assertTrue((Path(self.tmp.name) / mat.renders["ko"]).exists())
        from storyforge.rules import MANUAL_CHECK_ITEMS
        mat = self.pipe.review(mat.id, MANUAL_CHECK_ITEMS)
        self.assertEqual(mat.status, "완성")
        result = self.pipe.export(mat.id)
        self.assertTrue((Path(self.tmp.name) / result["zip"]).exists())

    def test_export_blocked_before_review(self):
        mat = self._register()
        self.pipe.set_fact(mat.id, "키 작고 뚱뚱해서 따돌림 당하던 아기 코끼리")
        self.pipe.choose_copy(mat.id, "키 작고 뚱뚱해서 따돌림 당하던 아기 코끼리")
        self.pipe.render(mat.id)
        with self.assertRaises(PermissionError):
            self.pipe.export(mat.id)

    def test_unusable_rights_blocked(self):
        mat = self._register(rights="사용불가")
        with self.assertRaises(PermissionError):
            self.pipe.set_fact(mat.id, "아무 사실")

    def test_copy_requires_fact(self):
        mat = self._register()
        with self.assertRaises(ValueError):
            self.pipe.generate_copies(mat.id)


if __name__ == "__main__":
    unittest.main()
