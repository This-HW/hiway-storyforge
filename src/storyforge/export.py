"""Export a posting package (SPEC FR-7): images + caption draft + metadata."""
from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

from .models import Material

LANG_NAMES = {"ko": "한국어", "en": "English", "ja": "日本語"}


def build_package(material: Material, data_dir: Path) -> dict:
    pkg_dir = data_dir / "outputs" / material.id / "package"
    if pkg_dir.exists():
        shutil.rmtree(pkg_dir)
    pkg_dir.mkdir(parents=True)
    files: list[str] = []
    for lang, rel in sorted(material.renders.items()):
        src = data_dir / rel
        if src.exists():
            name = f"image_{lang}{src.suffix}"
            shutil.copy(src, pkg_dir / name)
            files.append(name)
    for i, rel in enumerate(material.slide_renders):
        src = data_dir / rel
        if src.exists():
            name = f"slide_{i + 1}{src.suffix}"
            shutil.copy(src, pkg_dir / name)
            files.append(name)
    caption = (
        f"{material.chosen_copy}\n\n"
        f"(캡션 초안 — 사실 보충 1~2줄을 직접 채워 넣으세요)\n"
        f"#{material.topic.replace('·', '')} #사진이야기\n")
    (pkg_dir / "caption.txt").write_text(caption, encoding="utf-8")
    files.append("caption.txt")
    meta = {
        "id": material.id, "topic": material.topic, "source": material.source,
        "rights": material.rights, "fact": material.fact,
        "chosen_copy": material.chosen_copy, "renders": material.renders,
    }
    (pkg_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    files.append("meta.json")
    zip_path = pkg_dir.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in files:
            zf.write(pkg_dir / name, arcname=name)
    rel_zip = str(zip_path.relative_to(data_dir))
    return {"dir": str(pkg_dir.relative_to(data_dir)), "zip": rel_zip, "files": files}
