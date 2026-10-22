import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from storyforge.config import load_config
from storyforge.rules import MANUAL_CHECK_ITEMS
from storyforge.services import Pipeline

FACT = "키 작고 뚱뚱해서 따돌림 당하던 아기 코끼리"


def _sample_jpg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (800, 800), (90, 120, 80)).save(buf, "JPEG")
    return buf.getvalue()


class TestAuditFixes(unittest.TestCase):
    """Regressions found in the 2026-10-21 full-logic audit."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        cfg = load_config()
        cfg["provider"] = "stub"
        self.pipe = Pipeline(cfg, Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def _material_with_copy(self):
        mat = self.pipe.register(image_bytes=_sample_jpg(), ext=".jpg",
                                 source="https://example.com/x", rights="확인됨",
                                 topic="동물")
        self.pipe.set_fact(mat.id, FACT)
        self.pipe.choose_copy(mat.id, FACT)
        return mat

    def test_review_without_render_cannot_complete(self):
        mat = self._material_with_copy()
        mat = self.pipe.review(mat.id, MANUAL_CHECK_ITEMS)
        self.assertNotEqual(mat.status, "완성")
        self.assertTrue(any("합성" in b for b in mat.review["blockers"]))

    def test_choose_new_copy_invalidates_render_and_review(self):
        mat = self._material_with_copy()
        self.pipe.render(mat.id)
        mat = self.pipe.review(mat.id, MANUAL_CHECK_ITEMS)
        self.assertEqual(mat.status, "완성")
        mat = self.pipe.choose_copy(mat.id, "매일 아침 5시에 일어나는 남자의 몸")
        self.assertEqual(mat.renders, {})
        self.assertNotEqual(mat.status, "완성")

    def test_record_views_requires_posted_state(self):
        mat = self._material_with_copy()
        with self.assertRaises(ValueError):
            self.pipe.record_views(mat.id, 1000)


if __name__ == "__main__":
    unittest.main()
