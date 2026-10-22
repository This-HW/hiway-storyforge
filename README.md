# hiway-storyforge

검증된 실화 스토리를 사진 게시물로 제작·게시·학습하는 스토리 제작 시스템.
소재 1건을 넣으면 — 핵심 사실 추출 → 후킹 카피 → 스토리 캐러셀 합성 → 정책 검수 → 게시 큐·성과 추적 — 까지 한 흐름으로 처리한다.
핵심 자산은 채널이 아니라 스토리이며, 코어(소싱·카피·제작·큐·성과)는 매체 무관하게 설계됐다. 현재 채널은 인스타그램 사진 게시글이고, 릴스·숏츠 등 영상 포맷은 렌더러·게시 어댑터 추가로 확장한다.

> 방법론(왜·어떻게 운영하나)은 `docs/PLAYBOOK.md`, 요구사항은 `docs/SPEC.md`, 설계는 `docs/DESIGN.md`를 본다.
> 보너스 초대는 Meta가 결정한다. 이 도구는 초대·수익을 보장하지 않으며, "초대 후보군이 될 계정 운영"을 돕는 제작 도구다. (이 보너스 운영은 hiway-storyforge의 첫 번째 운용 사례다.)

## 빠른 시작 (키 없이 데모)

```bash
pip install -r requirements.txt   # Pillow 하나뿐
make demo                         # 스텁 프로바이더 + 샘플 소재로 실행
# http://127.0.0.1:8765
```

데모의 스텁 프로바이더는 실제 AI가 아니라 규칙 기반 자리표시자다. 전체 화면 흐름을 확인하는 용도이며, 카피 품질은 실모델 연결 후의 몫이다.

## 실사용

```bash
cp .env.example .env              # PB_PROVIDER와 모델 키 설정 (OpenAI 호환 엔드포인트)
cp config/user.example.json config/user.json   # (선택) 개인 설정 오버라이드
make run
```

## 공개/프라이빗 경계

이 저장소는 공개 OSS 전제로 만들어졌다. 개인적인 것은 전부 git-ignore 영역에 있다:

| 위치 | 내용 |
|---|---|
| `.env` | API 키 (비밀은 여기만) |
| `config/user.json` | 개인 설정 (폰트, 언어, 색상) |
| `data/` | 소재 원본·완성본·성과 기록 |
| `private/` | 개인 노트·계정 정보 |

설정은 3-layer다: `config/default.json` < `config/user.json` < 환경변수(`PB_` 접두사).

## 기능 (전부 웹 UI에서 조작 가능)

- 제작: 소재 등록(출처·권리 필수) → 분석 → 후킹 카피 후보(형식 검증·승인 패턴 참고) → 합성(1080×1350) → 검수 게이트 → 게시 패키지(zip)
- 현지화: 영어·일본어·스페인어·포르투갈어·인도네시아어·튀르키예어 (전 언어 일괄 버튼)
- 보드·배치: 상태별 보드에서 여러 소재를 골라 카피 생성·합성·현지화를 일괄 실행
- 소싱: 주제별 탐색 쿼리 생성 + 후보 수집함 (수집·권리 확인은 사용자 몫 — 자동 수집 없음)
- 성과: 조회수 기록 기반 주제별·상위 게시물 분석, 승인 패턴 라이브러리
- 설정: 대상 언어·템플릿 색상/글자 크기·카피 자수 범위를 화면에서 바꿔 개인 설정(user.json)에 저장

## 구조

```
src/storyforge/   코어 (web → services → rules/render/store/providers)
web/              웹 UI (빌드 과정 없는 정적 파일)
docs/             SPEC / PLAYBOOK / DESIGN / AGENT_GUIDE
tests/            unittest
scripts/          데모 시드 등
```

## 개발

```bash
make test
```

기여 방법은 `CONTRIBUTING.md`, 에이전트( AI 코딩 도구)로 작업할 때는 `docs/AGENT_GUIDE.md`부터 읽는다.

## 라이선스

MIT — `LICENSE` 참조.
