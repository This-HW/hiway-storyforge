"""Domain data classes. Paths are always relative to the data dir."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

TOPICS = [
    "운동", "동물", "우주", "음식·요리", "건강", "연예·남녀관계", "가족", "직장",
    "돈·경제", "자동차·교통", "군대·남자공감", "여행", "학교·학창시절", "결혼", "소비·생활",
]

RIGHTS_STATES = ["확인됨", "불명확", "사용불가"]

# Material lifecycle (SPEC §6 FR-1)
STATUSES = ["등록됨", "분석완료", "카피완료", "합성완료", "검수대기", "완성", "게시완료"]

# Language targets (SPEC FR-5). code -> (display name, market note)
LANGUAGES = {
    "ko": ("한국어", "대한민국"),
    "en": ("English", "미국·영국 등"),
    "ja": ("日本語", "일본"),
    "es": ("Español", "멕시코·아르헨티나 등"),
    "pt": ("Português", "브라질"),
    "id": ("Bahasa Indonesia", "인도네시아"),
    "tr": ("Türkçe", "튀르키예"),
}

# Photo/carousel bonus monthly view minimums by region, from Meta's published
# bonus programme rules (see analysis doc). Reference data only — thresholds
# are assessed per account and do not guarantee an invitation.
REGION_MONTHLY_MIN_VIEWS = {
    "KR": 1_000_000, "US": 5_000_000, "JP": 500_000, "IE": 1_000_000,
    "GB": 500_000, "AU": 500_000, "CA": 500_000, "NZ": 500_000,
    "SE": 500_000, "DK": 500_000, "FI": 500_000, "NO": 500_000,
    "ZA": 2_000_000,
}


@dataclass
class QueueItem:
    """Semi-automated publishing queue (P3). The app never posts by itself:
    an operator (the user, or their agent via the platform connector)
    publishes queued items and records the result here."""
    id: str
    material_id: str
    caption: str
    langs: list[str] = field(default_factory=list)   # rendered languages included
    files: list[str] = field(default_factory=list)   # ordered post files (carousel)
    status: str = "대기"          # 대기 | 게시완료 | 실패 | 취소
    post_url: str = ""
    error: str = ""
    created_at: str = ""
    published_at: str = ""
    scheduled_for: str = ""       # target posting time (local), evening window by default

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "QueueItem":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class SourcingCandidate:
    """FR-9: a sourcing lead the user found. Becomes a Material only when the
    user registers the actual image through FR-1 (rights check stays manual)."""
    id: str
    topic: str
    url: str
    note: str = ""
    origin_lang: str = ""
    status: str = "후보"          # 후보 | 채택 | 버림
    created_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SourcingCandidate":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class CopyCandidate:
    text: str
    note: str = ""          # which transformation was applied
    lang: str = "ko"
    valid: bool = True
    issues: list[str] = field(default_factory=list)


@dataclass
class Material:
    id: str
    image_rel: str                       # relative to data dir
    source: str                          # 출처 (required)
    rights: str = "불명확"               # 확인됨 | 불명확 | 사용불가
    topic: str = ""
    origin_lang: str = ""
    status: str = "등록됨"
    fact: str = ""                       # confirmed core fact
    visible_info: list[str] = field(default_factory=list)
    fact_candidates: list[str] = field(default_factory=list)
    copies: list[dict] = field(default_factory=list)       # serialized CopyCandidate
    chosen_copy: str = ""
    highlight: str = ""
    renders: dict = field(default_factory=dict)            # lang -> image rel path
    review: dict = field(default_factory=dict)             # last review result
    manual_checks: list[str] = field(default_factory=list)
    views: int | None = None
    posted_at: str = ""
    regen_prompt: str = ""               # FR-11: set when the image is AI-regenerated
    # FR-12 story carousel: slides[0] is the hook (text == chosen_copy);
    # later slides carry one story beat each. Empty = single-image post.
    slides: list = field(default_factory=list)             # [{text, prompt, image}]
    slide_renders: list = field(default_factory=list)    # rendered slide paths

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Material":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})
