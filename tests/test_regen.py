import tempfile
import unittest
from pathlib import Path

from storyforge.config import load_config
from storyforge.services import Pipeline


class TestRegenerate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        cfg = load_config()
        cfg["provider"] = "stub"
        self.pipe = Pipeline(cfg, Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_regenerated_material_provenance(self):
        mat = self.pipe.register_regenerated(
            story_url="https://example.com/story",
            prompt="An elephant waiting by a fence",
            topic="동물", fact="친구를 3주간 기다린 코끼리")
        self.assertTrue(mat.source.startswith("AI 재생성"))
        self.assertIn("https://example.com/story", mat.source)
        self.assertEqual(mat.rights, "확인됨")
        self.assertEqual(mat.regen_prompt, "An elephant waiting by a fence")
        self.assertTrue((Path(self.tmp.name) / mat.image_rel).exists())

    def test_story_url_required(self):
        with self.assertRaises(ValueError):
            self.pipe.register_regenerated(
                story_url=" ", prompt="scene", topic="동물")


if __name__ == "__main__":
    unittest.main()
