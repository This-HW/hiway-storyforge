import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from storyforge.config import load_config
from storyforge.rules import MANUAL_CHECK_ITEMS
from storyforge.services import Pipeline


def _sample_jpg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (800, 800), (90, 120, 80)).save(buf, "JPEG")
    return buf.getvalue()


FACT = "키 작고 뚱뚱해서 따돌림 당하던 아기 코끼리"


class TestP1P2(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        cfg = load_config()
        cfg["provider"] = "stub"
        cfg["languages"] = {"base": "ko", "targets": ["en", "ja", "es", "pt", "id", "tr"]}
        self.pipe = Pipeline(cfg, Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def _ready_material(self):
        mat = self.pipe.register(image_bytes=_sample_jpg(), ext=".jpg",
                                 source="https://example.com/x", rights="확인됨",
                                 topic="동물")
        self.pipe.set_fact(mat.id, FACT)
        return mat

    def test_localize_all_six_targets(self):
        mat = self._ready_material()
        self.pipe.choose_copy(mat.id, FACT)
        mat = self.pipe.localize_all(mat.id)
        for lang in ["en", "ja", "es", "pt", "id", "tr"]:
            self.assertIn(lang, mat.renders)
            self.assertTrue((Path(self.tmp.name) / mat.renders[lang]).exists())

    def test_approved_pattern_saved_on_choose(self):
        mat = self._ready_material()
        self.pipe.choose_copy(mat.id, FACT)
        patterns = self.pipe.store.list_patterns()
        self.assertTrue(any(p["text"] == FACT for p in patterns))
        # duplicates are not stacked
        mat2 = self._ready_material()
        self.pipe.choose_copy(mat2.id, FACT)
        self.assertEqual(len([p for p in self.pipe.store.list_patterns()
                              if p["text"] == FACT]), 1)

    def test_batch_copies_and_render(self):
        m1 = self._ready_material()
        m2 = self._ready_material()
        results = self.pipe.batch([m1.id, m2.id], "copies")
        self.assertTrue(all(r["ok"] for r in results))
        self.pipe.choose_copy(m1.id, FACT)
        self.pipe.choose_copy(m2.id, FACT)
        results = self.pipe.batch([m1.id, m2.id], "render")
        self.assertTrue(all(r["ok"] for r in results))

    def test_batch_partial_failure_isolated(self):
        m1 = self._ready_material()
        results = self.pipe.batch([m1.id, "does-not-exist"], "copies")
        self.assertTrue(results[0]["ok"])
        self.assertFalse(results[1]["ok"])

    def test_sourcing_candidates(self):
        cand = self.pipe.add_candidate(topic="동물", url="https://example.com/v")
        self.assertEqual(cand.status, "후보")
        cand = self.pipe.set_candidate_status(cand.id, "채택")
        self.assertEqual(cand.status, "채택")
        with self.assertRaises(ValueError):
            self.pipe.add_candidate(topic="동물", url="  ")

    def test_sourcing_queries(self):
        queries = self.pipe.sourcing_queries("동물")
        self.assertEqual(len(queries), 5)
        self.assertTrue(all(q["query"] for q in queries))

    def test_analytics(self):
        mat = self._ready_material()
        self.pipe.choose_copy(mat.id, FACT)
        self.pipe.render(mat.id)
        self.pipe.review(mat.id, MANUAL_CHECK_ITEMS)
        self.pipe.record_views(mat.id, 1234567, "2026-10-21")
        stats = self.pipe.analytics()
        self.assertEqual(stats["posted"], 1)
        self.assertEqual(stats["total_views"], 1234567)
        self.assertEqual(stats["by_topic"]["동물"]["count"], 1)
        self.assertEqual(stats["top"][0]["views"], 1234567)


if __name__ == "__main__":
    unittest.main()
