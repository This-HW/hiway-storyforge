"""Pure rule functions: copy format validation + policy screening.

No imports from other storyforge modules. Sources: SPEC §6 (FR-3 R1-R6,
FR-6) and docs/PLAYBOOK.md §6.
"""
from __future__ import annotations

import re

# --- FR-3 R5: 15-28 chars (spaces excluded), max 2 lines ---------------------

def char_count(text: str) -> int:
    return len(re.sub(r"\s", "", text))


def validate_copy_format(text: str, *, min_chars: int = 15, max_chars: int = 28,
                         max_lines: int = 2) -> list[str]:
    issues: list[str] = []
    lines = [ln for ln in text.split("\n")]
    if len(lines) > max_lines:
        issues.append(f"줄 수 {len(lines)}줄 (최대 {max_lines}줄)")
    count = char_count(text)
    if count < min_chars:
        issues.append(f"글자 수 {count}자 (최소 {min_chars}자)")
    if count > max_chars:
        issues.append(f"글자 수 {count}자 (최대 {max_chars}자)")
    return issues


# --- FR-6: banned / risky patterns -------------------------------------------
# Pattern screening is an assist, not a legal/policy judgment. Manual checks
# in services.review() cover what patterns cannot (rights, factuality, ...).

ENGAGEMENT_BAIT = [
    r"좋아요\s*(눌러|좀|부탁)", r"댓글\s*(달아|남겨|좀)", r"팔로우\s*(해|좀|부탁)",
    r"공유\s*해\s*주", r"친구\s*태그", r"저장\s*해\s*두",
]
MEDICAL_DEFINITIVE = [
    r"반드시\s*낫", r"100%\s*(효과|완치|치료)", r"완치\s*(됩니다|보장)",
    r"먹으면\s*바로\s*(낫|빠진)", r"의사가\s*숨긴",
]
SENSATIONAL_EMPTY = ["매우 놀라운", "정말 충격적인", "믿을 수 없는 일이", "경악을 금치"]

BANNED_GROUPS = {
    "참여 유도": ENGAGEMENT_BAIT,
    "단정적 의학 표현": MEDICAL_DEFINITIVE,
}


def screen_copy(text: str) -> list[str]:
    """Return human-readable findings for risky patterns in a copy text."""
    findings: list[str] = []
    for group, patterns in BANNED_GROUPS.items():
        for pat in patterns:
            if re.search(pat, text):
                findings.append(f"{group} 패턴 감지: /{pat}/")
    for phrase in SENSATIONAL_EMPTY:
        if phrase in text:
            findings.append(f"빈 수식어 사용 (R4 위반 소지): '{phrase}'")
    return findings


# Manual review items that export gating requires (SPEC FR-6).
MANUAL_CHECK_ITEMS = [
    "원본 권리·출처를 확인했다",
    "사실관계를 원본으로 대조했다",
    "선정·폭력·혐오·조롱 표현이 없다",
    "반복·저품질(워터마크, 동일 문구 반복)이 아니다",
]


def export_blockers(material_rights: str, review: dict, manual_checks: list[str],
                    has_render: bool = True) -> list[str]:
    """Gate for export/queue: returns reasons the step must be blocked
    (empty = OK)."""
    blockers: list[str] = []
    if not has_render:
        blockers.append("합성된 이미지(한국어 렌더)가 없다")
    if material_rights == "사용불가":
        blockers.append("권리 상태가 '사용불가'인 소재는 진행할 수 없다")
    if review.get("auto_findings"):
        blockers.append(f"자동 검수 발견 사항 {len(review['auto_findings'])}건이 남아 있다")
    missing = [item for item in MANUAL_CHECK_ITEMS if item not in manual_checks]
    if missing:
        blockers.append("수동 확인 미완료: " + ", ".join(missing))
    return blockers
