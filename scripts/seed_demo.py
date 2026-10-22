"""Seed one synthetic demo material so `make demo` shows the full flow.

The sample image is generated locally (no external assets, no rights issues).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PIL import Image, ImageDraw  # noqa: E402

from photobonus.config import data_dir, load_config  # noqa: E402
from photobonus.services import Pipeline  # noqa: E402


def make_sample_image() -> bytes:
    img = Image.new("RGB", (900, 900), (70, 130, 90))
    draw = ImageDraw.Draw(img)
    draw.ellipse([250, 300, 650, 700], fill=(150, 150, 150))   # "elephant" blob
    draw.ellipse([380, 200, 520, 340], fill=(150, 150, 150))
    draw.rectangle([0, 780, 900, 900], fill=(60, 90, 50))      # ground
    import io
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    return buf.getvalue()


def main() -> None:
    cfg = load_config()
    pipe = Pipeline(cfg, data_dir(cfg))
    if any(m.topic == "동물" and "DEMO" in m.source for m in pipe.store.list()):
        print("demo material already seeded")
        return
    mat = pipe.register(
        image_bytes=make_sample_image(), ext=".jpg",
        source="DEMO synthetic sample (generated locally)",
        rights="확인됨", topic="동물", origin_lang="en")
    pipe.set_fact(mat.id, "키 작고 뚱뚱해서 따돌림 당하던 아기 코끼리")
    pipe.generate_copies(mat.id)
    print(f"seeded demo material: {mat.id}")


if __name__ == "__main__":
    main()
