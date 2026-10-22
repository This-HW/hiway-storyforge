"""Model providers (Ports & Adapters at the model boundary only).

- StubProvider: deterministic, keyless. For demo/tests — NOT for real copy quality.
- OpenAICompatibleProvider: any Chat Completions endpoint via env config.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.request
from dataclasses import dataclass, field

from .models import CopyCandidate
from .rules import char_count

HOOK_SYSTEM = (
    "너는 인스타그램 사진 게시물 후킹 카피 작가다. 규칙: "
    "R1 핵심 사실 하나만. R2 사진에 이미 보이는 정보는 넣지 않는다. "
    "R3 기사체·번역체 금지, 구어체. R4 빈 수식어 대신 구체적 사건·수치·결과. "
    "R5 공백 제외 15~28자, 최대 2줄, 가장 강한 결과·반전을 앞에. "
    "R6 사실을 왜곡하지 않는다. 참여 유도 문구 금지."
)


@dataclass
class AnalysisResult:
    fact_candidates: list[str] = field(default_factory=list)
    visible_info: list[str] = field(default_factory=list)


class StubProvider:
    """Rule-based placeholder so the full flow runs without any API key."""

    name = "stub"

    def analyze(self, image_path: str) -> AnalysisResult:
        return AnalysisResult(
            fact_candidates=["(스텁) 핵심 사실을 직접 입력해 주세요"],
            visible_info=[],
        )

    def generate(self, fact: str, *, visible_info: list[str], topic: str,
                 humor: bool, count: int = 5,
                 examples: list[str] | None = None) -> list[CopyCandidate]:
        fact = fact.strip()
        variants = [
            (fact, "원문 유지"),
            (f"결국 {fact}" if not fact.startswith("결국") else fact, "결과 앞배치 시도"),
            (fact.replace("입니다", "").replace("이다", ""), "어미 정리"),
            (f"{fact}, 진짜였다" if humor else fact, "유머 한 스푼" if humor else "원문 유지"),
            (fact, "원문 유지"),
        ]
        if examples:
            variants.insert(1, (examples[0], "승인 패턴 참고(스텁: 형태만)"))
        out: list[CopyCandidate] = []
        seen: set[str] = set()
        for text, note in variants:
            if text in seen:
                continue
            seen.add(text)
            out.append(CopyCandidate(text=text, note=f"스텁: {note}"))
            if len(out) >= count:
                break
        return out

    def localize(self, text: str, *, fact: str, target_lang: str) -> list[CopyCandidate]:
        return [CopyCandidate(text=text, note="스텁: 현지화는 실모델 연결 후 동작", lang=target_lang)]


class OpenAICompatibleProvider:
    name = "openai-compatible"

    def __init__(self) -> None:
        self.base_url = os.environ.get("PB_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.api_key = os.environ.get("PB_LLM_API_KEY", "")
        self.model = os.environ.get("PB_LLM_MODEL", "")

    def _chat(self, messages: list[dict], max_tokens: int = 800) -> str:
        body = json.dumps({
            "model": self.model, "messages": messages,
            "max_tokens": max_tokens, "temperature": 0.8,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=body, method="POST",
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]

    @staticmethod
    def _parse_lines(raw: str) -> list[str]:
        lines = []
        for line in raw.splitlines():
            line = line.strip(" -\t0123456789.)")
            if line:
                lines.append(line)
        return lines

    def analyze(self, image_path: str) -> AnalysisResult:
        with open(image_path, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode()
        raw = self._chat([
            {"role": "user", "content": [
                {"type": "text", "text":
                 "이 사진의 핵심 사실 후보 3개를 한 줄씩 써라. 그 다음 빈 줄 뒤에, "
                 "사진만 봐도 알 수 있는 정보(카피에 넣으면 안 되는 것)를 한 줄씩 써라."},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ]}])
        parts = raw.split("\n\n", 1)
        facts = self._parse_lines(parts[0])[:3]
        visible = self._parse_lines(parts[1]) if len(parts) > 1 else []
        return AnalysisResult(fact_candidates=facts, visible_info=visible)

    def generate(self, fact: str, *, visible_info: list[str], topic: str,
                 humor: bool, count: int = 5,
                 examples: list[str] | None = None) -> list[CopyCandidate]:
        examples_block = ""
        if examples:
            examples_block = ("승인된 카피 패턴(형태·리듬만 참고, 문구 복붙 금지):\n"
                              + "\n".join(f"- {e}" for e in examples[:10]) + "\n")
        prompt = (
            f"핵심 사실: {fact}\n주제: {topic}\n"
            f"사진이 이미 보여주는 정보(카피에 넣지 말 것): {', '.join(visible_info) or '없음'}\n"
            f"유머: {'한 스푼만' if humor else '넣지 말 것'}\n"
            f"{examples_block}"
            f"후킹 카피 {count}개를 한 줄에 하나씩, 설명 없이 카피만 출력해라.")
        raw = self._chat([
            {"role": "system", "content": HOOK_SYSTEM},
            {"role": "user", "content": prompt}])
        return [CopyCandidate(text=t, note="모델 생성")
                for t in self._parse_lines(raw)[:count]]

    def localize(self, text: str, *, fact: str, target_lang: str) -> list[CopyCandidate]:
        prompt = (
            f"원본 카피(한국어): {text}\n핵심 사실: {fact}\n"
            f"이 카피를 {target_lang} 사용 국가의 후킹 문장으로 다시 써라. 직역 금지. "
            "그 언어에서 실제 쓰는 구어체로, 결과·반전을 앞에, 짧고 강하게. "
            "후보 3개를 한 줄에 하나씩, 설명 없이 출력해라.")
        raw = self._chat([
            {"role": "system", "content": HOOK_SYSTEM},
            {"role": "user", "content": prompt}])
        return [CopyCandidate(text=t, note="현지화 생성", lang=target_lang)
                for t in self._parse_lines(raw)[:3]]


class StubImageProvider:
    """Keyless placeholder scene for the FR-11 regeneration path (demo/tests)."""

    name = "stub-image"

    def generate(self, prompt: str) -> bytes:
        import io

        from PIL import Image, ImageDraw
        img = Image.new("RGB", (1080, 1080), (96, 128, 96))
        draw = ImageDraw.Draw(img)
        draw.ellipse([290, 330, 790, 760], fill=(140, 140, 140))
        draw.ellipse([620, 640, 800, 790], fill=(235, 235, 225))
        draw.text((40, 40), "STUB regenerated scene", fill=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, "JPEG")
        return buf.getvalue()


class OpenAICompatibleImageProvider:
    """Image generation via an OpenAI-compatible /images/generations API."""

    name = "openai-compatible-image"

    def __init__(self) -> None:
        self.base_url = os.environ.get("PB_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.api_key = os.environ.get("PB_LLM_API_KEY", "")
        self.model = os.environ.get("PB_IMAGE_MODEL", "gpt-image-1")

    def generate(self, prompt: str) -> bytes:
        body = json.dumps({"model": self.model, "prompt": prompt,
                           "size": "1024x1024"}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/images/generations", data=body, method="POST",
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        item = data["data"][0]
        if item.get("b64_json"):
            return base64.b64decode(item["b64_json"])
        with urllib.request.urlopen(item["url"], timeout=120) as resp:
            return resp.read()


def get_image_provider(cfg: dict):
    if cfg.get("provider") == "openai-compatible":
        return OpenAICompatibleImageProvider()
    return StubImageProvider()


def get_provider(cfg: dict):
    kind = cfg.get("provider", "stub")
    if kind == "openai-compatible":
        return OpenAICompatibleProvider()
    return StubProvider()


# Re-exported for services that only need a length check helper.
__all__ = ["AnalysisResult", "StubProvider", "OpenAICompatibleProvider",
           "get_provider", "char_count"]
