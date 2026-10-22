# Agent Guide (10분 온보딩)

AI 코딩 도구·기여자가 이 저장소에서 작업할 때의 지도.

## 읽는 순서

1. `README.md` — 무엇이고 어떻게 실행하나
2. `docs/SPEC.md` — 요구사항 (FR 번호가 코드·테스트의 기준)
3. `docs/DESIGN.md` — 모듈 지도, 의존성 방향, 공개/프라이빗 경계
4. `docs/PLAYBOOK.md` — 도메인 방법론 (왜 이런 규칙이 있나)

## 절대 규칙

- `rules.py`·`render.py`에 내부 모듈 import 추가 금지 (순수 함수 유지)
- 비밀·개인 데이터를 코드/설정/docs에 쓰지 않는다. `.env`, `config/user.json`, `data/`, `private/`만 프라이빗이다
- 런타임 의존성 추가는 Pillow 외 금지 (필요하면 DESIGN에 먼저 기록)
- 동작 변경 시 SPEC부터, 구조 변경 시 DESIGN부터 수정
- 카피 규칙(R1~R6)과 검수 8규칙의 출처는 PLAYBOOK과 SPEC §6이다. 임의로 완화하지 않는다

## 검증

- `make test` (unittest), `make demo`로 스텁 플로우 확인
- 렌더 변경 시 샘플 출력 이미지를 눈으로 확인할 것
