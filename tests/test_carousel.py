"""FR-12 story carousel: slides gate rendering, review and queue files."""
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from storyforge.config import load_config
from storyforge.rules import MANUAL_CHECK_ITEMS
from storyforge.services import Pipeline

MANUAL_ALL = MANUAL_CHECK_ITEMS


class CarouselTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        cfg = load_config()
        cfg["provider"] = "stub"
        self.pipe = Pipeline(cfg, Path(self.tmp.name))
        src = Path(self.tmp.name) / "src.jpg"
        Image.new("RGB", (800, 1000), (180, 140, 90)).save(src)
        self.mat = self.pipe.register(
            image_bytes=src.read_bytes(), ext=".jpg",
            source="test", rights="확인됨", topic="동물")
        self.pipe.set_fact(self.mat.id, "코끼리가 다친 개 친구를 3주간 지킨 이야기")
        self.pipe.generate_copies(self.mat.id)
        hook = "다친 친구를 3주 내내\n한자리에서 기다린 코끼리"
        self.pipe.choose_copy(self.mat.id, hook, highlight="3주 내내")

    def tearDown(self):
        self.tmp.cleanup()

    def test_slides_render_review_enqueue(self):
        slides = [
            {"text": "다친 친구를 3주 내내\n한자리에서 기다린 코끼리", "prompt": "p1"},
            {"text": "척추를 다쳐 걷지 못하는 벨라 곁을\n타라는 떠나지 않았어요", "prompt": "p2"},
            {"text": "3주 뒤 벨라는 다시 걷기 시작했고\n두 친구는 나란히 걸었어요", "prompt": "p3"},
        ]
        mat = self.pipe.set_slides(self.mat.id, slides)
        for i in range(3):
            mat = self.pipe.generate_slide_image(self.mat.id, i)
        mat = self.pipe.render(self.mat.id)
        self.assertEqual(len(mat.slide_renders), 3)
        for rel in mat.slide_renders:
            self.assertTrue((self.pipe.dir / rel).exists())
        mat = self.pipe.review(self.mat.id, MANUAL_ALL)
        self.assertEqual(mat.status, "완성")
        item = self.pipe.enqueue(self.mat.id)
        self.assertEqual(len(item.files), 3)
        self.assertEqual(item.files, mat.slide_renders)

    def test_first_slide_must_be_hook(self):
        with self.assertRaises(ValueError):
            self.pipe.set_slides(self.mat.id, [
                {"text": "다른 문장입니다"}, {"text": "둘째"}])

    def test_slide_count_bounds(self):
        with self.assertRaises(ValueError):
            self.pipe.set_slides(self.mat.id, [{"text": "하나뿐"}])

    def test_render_blocked_until_all_slide_images_exist(self):
        self.pipe.set_slides(self.mat.id, [
            {"text": "다친 친구를 3주 내내\n한자리에서 기다린 코끼리", "prompt": "p1"},
            {"text": "둘째 장 문장", "prompt": "p2"}])
        self.pipe.generate_slide_image(self.mat.id, 0)
        with self.assertRaises(ValueError):
            self.pipe.render(self.mat.id)


if __name__ == "__main__":
    unittest.main()
