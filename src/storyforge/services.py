"""Pipeline orchestration: register -> analyze -> generate -> render ->
review -> export. (SPEC §5)"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from . import export as export_mod
from . import render as render_mod
from . import rules
from .models import CopyCandidate, Material
from .providers import get_provider
from .store import Store


class Pipeline:
    def __init__(self, cfg: dict, data_dir: Path):
        self.cfg = cfg
        self.dir = data_dir
        self.store = Store(data_dir)
        self.provider = get_provider(cfg)

    # FR-1 -----------------------------------------------------------------
    def register(self, *, image_bytes: bytes, ext: str, source: str,
                 rights: str, topic: str, origin_lang: str = "") -> Material:
        if not source.strip():
            raise ValueError("출처는 필수입니다")
        if rights not in ("확인됨", "불명확", "사용불가"):
            raise ValueError("권리 상태가 올바르지 않습니다")
        mid = self.store.new_id()
        rel = self.store.save_image(mid, ext, image_bytes)
        material = Material(id=mid, image_rel=rel, source=source.strip(),
                            rights=rights, topic=topic, origin_lang=origin_lang)
        return self.store.add(material)

    # FR-11 ------------------------------------------------------------------
    def register_regenerated(self, *, story_url: str, prompt: str, topic: str,
                             fact: str = "") -> Material:
        """Regenerate a story's scene as a new AI image and register it as a
        material. Provenance is forced into the source field."""
        if not story_url.strip():
            raise ValueError("원본 스토리 URL은 필수입니다 (출처 강제 기록)")
        if not prompt.strip():
            raise ValueError("재생성 프롬프트는 필수입니다")
        from .providers import get_image_provider
        image_bytes = get_image_provider(self.cfg).generate(prompt.strip())
        material = self.register(
            image_bytes=image_bytes, ext=".jpg",
            source=f"AI 재생성 (원본 스토리: {story_url.strip()})",
            rights="확인됨", topic=topic)
        material.regen_prompt = prompt.strip()
        if fact.strip():
            material.fact = fact.strip()
        self.store.update(material)
        return material

    def _get(self, material_id: str) -> Material:
        material = self.store.get(material_id)
        if material is None:
            raise KeyError(f"소재를 찾을 수 없음: {material_id}")
        if material.rights == "사용불가":
            raise PermissionError("권리 상태가 '사용불가'인 소재는 진행할 수 없습니다")
        return material

    # FR-2 -----------------------------------------------------------------
    def analyze(self, material_id: str) -> Material:
        material = self._get(material_id)
        result = self.provider.analyze(str(self.dir / material.image_rel))
        material.fact_candidates = result.fact_candidates
        material.visible_info = result.visible_info
        material.status = "분석완료"
        self.store.update(material)
        return material

    def set_fact(self, material_id: str, fact: str,
                 visible_info: list[str] | None = None) -> Material:
        material = self._get(material_id)
        if not fact.strip():
            raise ValueError("핵심 사실은 비어 있을 수 없습니다")
        material.fact = fact.strip()
        if visible_info is not None:
            material.visible_info = visible_info
        self.store.update(material)
        return material

    # FR-3 -----------------------------------------------------------------
    def generate_copies(self, material_id: str, *, humor: bool = False) -> Material:
        material = self._get(material_id)
        if not material.fact:
            raise ValueError("핵심 사실이 확정되어야 카피를 만들 수 있습니다 (FR-2)")
        copy_cfg = self.cfg.get("copy", {})
        examples = [p["text"] for p in self.store.list_patterns()
                    if not material.topic or p.get("topic") in ("", material.topic)]
        candidates = self.provider.generate(
            material.fact, visible_info=material.visible_info,
            topic=material.topic, humor=humor,
            count=int(copy_cfg.get("candidate_count", 5)),
            examples=examples)
        serialized = []
        for cand in candidates:
            issues = rules.validate_copy_format(
                cand.text,
                min_chars=int(copy_cfg.get("min_chars", 15)),
                max_chars=int(copy_cfg.get("max_chars", 28)),
                max_lines=int(copy_cfg.get("max_lines", 2)))
            cand.valid = not issues
            cand.issues = issues
            serialized.append(asdict(cand))
        material.copies = serialized
        material.status = "카피완료"
        self.store.update(material)
        return material

    def _blockers(self, material: Material) -> list[str]:
        has_render = bool(material.renders.get("ko")) or (
            bool(material.slides)
            and len(material.slide_renders) == len(material.slides))
        return rules.export_blockers(
            material.rights, material.review, material.manual_checks,
            has_render=has_render)

    def choose_copy(self, material_id: str, text: str, highlight: str = "") -> Material:
        material = self._get(material_id)
        copy_cfg = self.cfg.get("copy", {})
        issues = rules.validate_copy_format(
            text,
            min_chars=int(copy_cfg.get("min_chars", 15)),
            max_chars=int(copy_cfg.get("max_chars", 28)),
            max_lines=int(copy_cfg.get("max_lines", 2)))
        if issues:
            raise ValueError("카피 형식 오류: " + "; ".join(issues))
        material.chosen_copy = text
        material.highlight = highlight
        if material.slides:
            material.slides[0]["text"] = text   # FR-12: slide 1 is the hook
        # A new copy invalidates earlier renders and any passed review:
        # they were made for the previous text.
        if material.renders or material.slide_renders or material.status in ("완성", "게시완료"):
            material.renders = {}
            material.slide_renders = []
            material.review = {}
            material.manual_checks = []
            if material.status != "게시완료":
                material.status = "카피완료"
        self.store.update(material)
        # Approved patterns: every confirmed copy becomes a reusable pattern
        # for future generation (SPEC §9 item 2, P1).
        self.store.add_pattern(text, material.topic)
        return material

    # FR-5 (P0: en/ja via provider) -----------------------------------------
    def localize(self, material_id: str, target_lang: str) -> Material:
        material = self._get(material_id)
        if not material.chosen_copy:
            raise ValueError("먼저 한국어 카피를 확정하세요")
        results = self.provider.localize(
            material.chosen_copy, fact=material.fact, target_lang=target_lang)
        if results:
            best = results[0]
            out_rel = f"outputs/{material.id}/render_{target_lang}.jpg"
            render_mod.render(str(self.dir / material.image_rel), best.text,
                              str(self.dir / out_rel),
                              highlight="", **self._render_kwargs())
            material.renders[target_lang] = out_rel
            material.copies.extend(asdict(c) for c in results)
            self.store.update(material)
        return material

    def localize_all(self, material_id: str) -> Material:
        """Render every configured target language (FR-5, P1 full set)."""
        material = self._get(material_id)
        targets = self.cfg.get("languages", {}).get("targets", ["en", "ja"])
        for lang in targets:
            if lang == "ko":
                continue
            self.localize(material_id, lang)
        return self._get(material_id)

    # FR-8: batch ------------------------------------------------------------
    def batch(self, material_ids: list[str], action: str) -> list[dict]:
        results: list[dict] = []
        for mid in material_ids:
            try:
                if action == "copies":
                    self.generate_copies(mid)
                elif action == "render":
                    self.render(mid)
                elif action == "localize":
                    self.localize_all(mid)
                else:
                    raise ValueError(f"알 수 없는 배치 작업: {action}")
                results.append({"id": mid, "ok": True})
            except Exception as exc:  # per-item failure must not stop the batch
                results.append({"id": mid, "ok": False, "error": str(exc)})
        return results

    # FR-9: sourcing assist ----------------------------------------------------
    def add_candidate(self, *, topic: str, url: str, note: str = "",
                      origin_lang: str = ""):
        from datetime import date

        from .models import SourcingCandidate
        if not url.strip():
            raise ValueError("후보 URL은 필수입니다")
        cand = SourcingCandidate(
            id=self.store.new_id(), topic=topic, url=url.strip(), note=note,
            origin_lang=origin_lang, created_at=date.today().isoformat())
        return self.store.add_candidate(cand)

    def set_candidate_status(self, candidate_id: str, status: str):
        for cand in self.store.list_candidates():
            if cand.id == candidate_id:
                if status not in ("후보", "채택", "버림"):
                    raise ValueError("후보 상태가 올바르지 않습니다")
                cand.status = status
                self.store.update_candidate(cand)
                return cand
        raise KeyError(f"후보를 찾을 수 없음: {candidate_id}")

    @staticmethod
    def sourcing_queries(topic: str) -> list[dict]:
        """Search-query starters per topic (FR-9). Deliberately just queries:
        collecting the material and checking rights stays with the user."""
        base = [
            ("en", f"{topic} viral story most shared"),
            ("en", f"{topic} unbelievable true story photo"),
            ("ja", f"{topic} 話題 写真"),
            ("en", f"site:reddit.com {topic} story"),
            ("en", f"{topic} news oddity viral"),
        ]
        return [{"lang": lang, "query": q} for lang, q in base]

    # Analytics (P2) -----------------------------------------------------------
    def analytics(self) -> dict:
        materials = self.store.list()
        posted = [m for m in materials if m.views is not None]
        by_topic: dict[str, dict] = {}
        for m in posted:
            bucket = by_topic.setdefault(
                m.topic or "(없음)", {"count": 0, "views": 0})
            bucket["count"] += 1
            bucket["views"] += m.views or 0
        for bucket in by_topic.values():
            bucket["avg_views"] = round(bucket["views"] / bucket["count"]) \
                if bucket["count"] else 0
        top = sorted(posted, key=lambda m: m.views or 0, reverse=True)[:10]
        return {
            "total_materials": len(materials),
            "posted": len(posted),
            "total_views": sum(m.views or 0 for m in posted),
            "by_topic": by_topic,
            "top": [{"id": m.id, "topic": m.topic, "fact": m.fact,
                     "copy": m.chosen_copy, "views": m.views} for m in top],
            "kr_monthly_min_views": 1_000_000,
        }

    # FR-4 -----------------------------------------------------------------
    def _render_kwargs(self) -> dict:
        rcfg = self.cfg.get("render", {})
        return {
            "width": int(rcfg.get("width", 1080)),
            "height": int(rcfg.get("height", 1350)),
            "font_path": rcfg.get("font_path", ""),
            "font_size": int(rcfg.get("font_size", 64)),
            "text_color": rcfg.get("text_color", "#FFFFFF"),
            "accent_color": rcfg.get("accent_color", "#FFE600"),
        }

    # FR-12: story carousel --------------------------------------------------
    def set_slides(self, material_id: str, slides: list[dict]) -> Material:
        material = self._get(material_id)
        if not (2 <= len(slides) <= 12):
            raise ValueError("캐러셀은 2~12장이어야 합니다")
        cleaned = []
        for i, slide in enumerate(slides):
            text = (slide.get("text") or "").strip()
            if not text:
                raise ValueError(f"슬라이드 {i + 1} 문장이 비어 있습니다")
            if text.count("\n") > 1:
                raise ValueError(f"슬라이드 {i + 1} 문장은 최대 2줄입니다")
            if i > 0 and len(text.replace(" ", "")) > 45:
                raise ValueError(f"슬라이드 {i + 1} 문장이 너무 깁니다 (공백 제외 45자 이내)")
            cleaned.append({"text": text,
                            "prompt": slide.get("prompt", ""),
                            "image": slide.get("image", "")})
        if material.chosen_copy and cleaned[0]["text"] != material.chosen_copy:
            raise ValueError("첫 슬라이드 문장은 확정 카피와 같아야 합니다 (후킹 슬라이드)")
        material.slides = cleaned
        # New slides invalidate slide renders and any passed review.
        material.slide_renders = []
        material.review = {}
        material.manual_checks = []
        if material.status not in ("게시완료",):
            material.status = "카피완료" if material.chosen_copy else material.status
        self.store.update(material)
        return material

    def generate_slide_image(self, material_id: str, index: int) -> Material:
        material = self._get(material_id)
        if not (0 <= index < len(material.slides)):
            raise ValueError("슬라이드 번호가 범위를 벗어났습니다")
        prompt = material.slides[index].get("prompt") or material.fact
        from .providers import get_image_provider
        image = get_image_provider(self.cfg).generate(prompt)
        rel = f"inputs/{material.id}/slide_{index}.jpg"
        path = self.dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(image)
        material.slides[index]["image"] = rel
        material.slide_renders = []
        self.store.update(material)
        return material

    def render(self, material_id: str) -> Material:
        material = self._get(material_id)
        if not material.chosen_copy:
            raise ValueError("먼저 카피를 확정하세요")
        if material.slides:
            kwargs = self._render_kwargs()
            story_kwargs = dict(kwargs, font_size=int(kwargs["font_size"] * 0.72))
            rendered = []
            for i, slide in enumerate(material.slides):
                src = slide.get("image") or (material.image_rel if i == 0 else "")
                if not src:
                    raise ValueError(f"슬라이드 {i + 1} 이미지가 없습니다 — 먼저 생성하세요")
                out_rel = f"outputs/{material.id}/slide_{i + 1}.jpg"
                if i == 0:
                    render_mod.render(str(self.dir / src), slide["text"],
                                      str(self.dir / out_rel),
                                      highlight=material.highlight, **kwargs)
                else:
                    render_mod.render(str(self.dir / src), slide["text"],
                                      str(self.dir / out_rel), **story_kwargs)
                rendered.append(out_rel)
            material.slide_renders = rendered
            material.renders["ko"] = rendered[0]
            material.status = "합성완료"
            self.store.update(material)
            return material
        out_rel = f"outputs/{material.id}/render_ko.jpg"
        render_mod.render(str(self.dir / material.image_rel), material.chosen_copy,
                          str(self.dir / out_rel),
                          highlight=material.highlight, **self._render_kwargs())
        material.renders["ko"] = out_rel
        material.status = "합성완료"
        self.store.update(material)
        return material

    # FR-6 -----------------------------------------------------------------
    def review(self, material_id: str, manual_checks: list[str]) -> Material:
        material = self._get(material_id)
        findings = rules.screen_copy(material.chosen_copy) if material.chosen_copy else []
        material.review = {"auto_findings": findings}
        material.manual_checks = manual_checks
        material.status = "검수대기"
        blockers = self._blockers(material)
        if not blockers:
            material.status = "완성"
        material.review["blockers"] = blockers
        self.store.update(material)
        return material

    # FR-7 -----------------------------------------------------------------
    def export(self, material_id: str) -> dict:
        material = self._get(material_id)
        blockers = self._blockers(material)
        if material.status != "완성" or blockers:
            raise PermissionError("검수를 통과해야 내보낼 수 있습니다: "
                                  + "; ".join(blockers or ["상태가 '완성'이 아님"]))
        result = export_mod.build_package(material, self.dir)
        return result

    # P3: semi-automated publishing queue --------------------------------------
    def enqueue(self, material_id: str, on_date=None):
        from datetime import datetime

        from .models import QueueItem
        material = self._get(material_id)
        blockers = self._blockers(material)
        if material.status != "완성" or blockers:
            raise PermissionError("검수를 통과한(완성) 소재만 큐에 넣을 수 있습니다: "
                                  + "; ".join(blockers or ["상태가 '완성'이 아님"]))
        if any(q.material_id == material_id and q.status == "대기"
               for q in self.store.list_queue()):
            raise ValueError("이미 대기 중인 큐 항목이 있습니다")
        caption = (f"{material.chosen_copy}\n\n"
                   f"#{material.topic.replace('·', '')} #사진이야기")
        files = list(material.slide_renders) or [material.renders["ko"]]
        # Posting-time logic (PLAYBOOK §5, HW 2026-10-21): no fixed time —
        # draw a random minute inside the 18:00-21:00 evening window.
        # Weekly batches pass on_date to schedule a specific day; without
        # it, draw for today, or tomorrow if today's draw has passed.
        import random
        from datetime import date as _date
        from datetime import timedelta
        now = datetime.now()
        base_day = on_date or now.date()
        if isinstance(base_day, str):
            base_day = _date.fromisoformat(base_day)
        target = datetime(base_day.year, base_day.month, base_day.day, 18, 0) \
            + timedelta(minutes=random.randrange(0, 180))
        if on_date is None and now >= target:
            base_day = now.date() + timedelta(days=1)
            target = datetime(base_day.year, base_day.month, base_day.day, 18, 0) \
                + timedelta(minutes=random.randrange(0, 180))
        item = QueueItem(
            id=self.store.new_id(), material_id=material_id, caption=caption,
            langs=sorted(material.renders.keys()), files=files,
            created_at=now.isoformat(timespec="seconds"),
            scheduled_for=target.isoformat(timespec="seconds"))
        return self.store.add_queue_item(item)

    def record_publish_result(self, queue_id: str, *, status: str,
                              post_url: str = "", error: str = ""):
        from datetime import datetime

        item = self.store.get_queue_item(queue_id)
        if item is None:
            raise KeyError(f"큐 항목을 찾을 수 없음: {queue_id}")
        if status not in ("게시완료", "실패", "취소"):
            raise ValueError("큐 결과 상태가 올바르지 않습니다")
        item.status = status
        item.post_url = post_url
        item.error = error
        if status == "게시완료":
            item.published_at = datetime.now().isoformat(timespec="seconds")
            material = self.store.get(item.material_id)
            if material is not None:
                material.status = "게시완료"
                material.posted_at = item.published_at[:10]
                self.store.update(material)
        self.store.update_queue_item(item)
        return item

    # FR-8 (record keeping part) --------------------------------------------
    def record_views(self, material_id: str, views: int, posted_at: str = "") -> Material:
        material = self._get(material_id)
        if material.status not in ("완성", "게시완료"):
            raise ValueError("게시된 소재에만 조회수를 기록할 수 있습니다 "
                             f"(현재 상태: {material.status})")
        material.views = views
        if posted_at:
            material.posted_at = posted_at
        material.status = "게시완료"
        self.store.update(material)
        return material


def candidate_from_dict(data: dict) -> CopyCandidate:
    return CopyCandidate(**{k: v for k, v in data.items()
                            if k in CopyCandidate.__dataclass_fields__})
