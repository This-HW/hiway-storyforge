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


class TestQueue(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        cfg = load_config()
        cfg["provider"] = "stub"
        self.pipe = Pipeline(cfg, Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def _complete_material(self):
        mat = self.pipe.register(image_bytes=_sample_jpg(), ext=".jpg",
                                 source="https://example.com/x", rights="확인됨",
                                 topic="동물")
        self.pipe.set_fact(mat.id, FACT)
        self.pipe.choose_copy(mat.id, FACT)
        self.pipe.render(mat.id)
        self.pipe.review(mat.id, MANUAL_CHECK_ITEMS)
        return mat

    def test_enqueue_requires_completed(self):
        mat = self.pipe.register(image_bytes=_sample_jpg(), ext=".jpg",
                                 source="https://example.com/x", rights="확인됨",
                                 topic="동물")
        with self.assertRaises(PermissionError):
            self.pipe.enqueue(mat.id)

    def test_enqueue_and_publish_flow(self):
        mat = self._complete_material()
        item = self.pipe.enqueue(mat.id)
        self.assertEqual(item.status, "대기")
        self.assertIn("ko", item.langs)
        # posting-time logic: random draw inside the 18:00-21:00 window
        from datetime import datetime
        target = datetime.fromisoformat(item.scheduled_for)
        self.assertGreaterEqual(target.hour, 18)
        self.assertLess(target.hour, 21)
        self.assertGreater(target, datetime.now())
        self.assertEqual(len(item.files), 1)
        with self.assertRaises(ValueError):  # duplicate waiting item
            self.pipe.enqueue(mat.id)
        item = self.pipe.record_publish_result(
            item.id, status="게시완료", post_url="https://instagram.com/p/xyz")
        self.assertEqual(item.status, "게시완료")
        self.assertTrue(item.published_at)
        mat = self.pipe.store.get(mat.id)
        self.assertEqual(mat.status, "게시완료")

    def test_publish_failure_recorded(self):
        mat = self._complete_material()
        item = self.pipe.enqueue(mat.id)
        item = self.pipe.record_publish_result(item.id, status="실패", error="한도 초과")
        self.assertEqual(item.error, "한도 초과")


if __name__ == "__main__":
    unittest.main()


class TestEnqueueOnDate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        cfg = load_config()
        cfg["provider"] = "stub"
        self.pipe = Pipeline(cfg, Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_scheduled_for_specific_date(self):
        img = _sample_jpg()
        mat = self.pipe.register(image_bytes=img, ext=".jpg", source="t",
                                 rights="확인됨", topic="동물")
        self.pipe.set_fact(mat.id, FACT, [])
        self.pipe.generate_copies(mat.id)
        mat = self.pipe.store.get(mat.id)
        self.pipe.choose_copy(mat.id, mat.copies[0]["text"])
        self.pipe.render(mat.id)
        self.pipe.review(mat.id, MANUAL_CHECK_ITEMS)
        item = self.pipe.enqueue(mat.id, on_date="2026-10-25")
        from datetime import datetime
        target = datetime.fromisoformat(item.scheduled_for)
        self.assertEqual(target.date().isoformat(), "2026-10-25")
        self.assertGreaterEqual(target.hour, 18)
        self.assertLess(target.hour, 21)
