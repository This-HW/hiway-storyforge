# End Card — cross-account reusable component

> Status: pattern documented 2026-10-30. Two production implementations exist
> (animal v6, property v5). A shared parameterized module has NOT been built yet —
> build it when a third account needs an end card, not before.

## What it is

A fixed, reusable last slide appended to **every** carousel post, on **every**
account. No "next episode" teaser — the card itself never changes per episode.

## Layout grammar (top → bottom)

1. Full-bleed cinematic background photo (per-account tone)
2. Uniform dark overlay, 40–55% depending on background brightness
3. Brand lockup, top center — tracked caps + thin flanking gold lines
4. Headline — centered, bold white, 1–2 lines (the brand promise)
5. Thin gold divider
6. Sub-copy — light weight, exactly one hook (curiosity / exclusivity / benefit)
7. Bottom: handle (gold bold) → CTA (white bold, **single** action).
   The action line is always last.

## Copy roles

| Slot     | Role                                              | Example (property)                        | Example (animal)                          |
|----------|---------------------------------------------------|-------------------------------------------|-------------------------------------------|
| Headline | Brand promise — what the account does for you     | 건물 가치 올리는 법, 쉽게 설명해드려요      | 마음이 따뜻해지는 이야기 하나               |
| Sub      | Hook — creates curiosity, never gives the answer  | 아는 사람만 아는 부동산 관리법              | 세계 곳곳의 귀여운 동물 이야기를 전해드려요 |
| CTA      | One action, short, high impact                    | 다음 편이 궁금하면 팔로우하세요             | 팔로우하고 내일 이야기도 받아보세요         |

**Terminology rule** (2026-10-30): never repeat the same key noun in headline
and sub — vary them top to bottom. ("건물 가치 올리는 법" + "부동산 관리법")

## Pipeline rule

- The end card lives as ONE canonical file per account
  (`baseline/endcard.jpg`). Renderers / production jobs copy it as the last
  slide automatically — never hardcode end-card content into an episode renderer.
- Copy or design change process: perfect ONE sample slide → owner review →
  replace the canonical file → all episodes pick it up on next render.

## Production implementations

- Property (@property.easy.kr): `~/workspace/property-account/baseline/endcard.jpg`
  (v5), renderer `~/workspace/property-account/render_endcard_v2.py`.
  Attached by `render_epN_final.py` (all 5).
- Animal (@animal.stories.kr): `~/workspace/animal-account/endcard/animal-endcard-v6.jpg`,
  renderer `~/workspace/animal-account/endcard/render_animal_endcard_v6.py`.
  Attached by the `photo-bonus-daily-prep` cron.

## Shared copy/design rules

The full cross-account rules live in `~/workspace/copy-style/STYLE_RULES.md`
§2.3 (layout grammar, copy roles, terminology). That file is the source of truth
for wording; this doc is the source of truth for the component contract.
