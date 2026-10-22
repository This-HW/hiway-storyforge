# 설계 (DESIGN v0.1)

스펙: `docs/SPEC.md` / 운영법: `docs/PLAYBOOK.md`

## 1. 아키텍처 원칙

- **Modular Monolith + Ports & Adapters (모델 경계만)**: 단일 Python 패키지, 웹 서버 1개. AI 모델 호출만 프로바이더 인터페이스 뒤에 둔다.
- **의존성 방향**: `web → services → (rules, render, store, providers)`. `rules`·`render`는 다른 모듈을 import하지 않는다 (순수 함수). 순환 import 금지.
- **제로에 가까운 의존성**: 런타임 의존성은 Pillow 하나. 웹 서버는 표준 라이브러리 `http.server`, 테스트는 `unittest`. 설치 장벽을 낮추는 것이 OSS 확산 조건이다.
- **로컬 퍼스트**: 모든 데이터는 `data/`(기본값) 아래 파일로 저장. DB 없음 (P0). 경로는 설정으로 교체 가능.

## 2. 모듈 지도

| 파일 | 책임 | 스펙 대응 |
|---|---|---|
| `src/storyforge/config.py` | 3-layer 설정 로딩 (기본값 → user.json → 환경변수) | NFR |
| `src/storyforge/models.py` | 데이터 클래스 (Material, CopyCandidate, Package), 상태 전이 | §6 |
| `src/storyforge/store.py` | 소재 인덱스(JSON) + 파일 저장. 경로는 상대 경로로만 기록 | FR-1 |
| `src/storyforge/rules.py` | 카피 형식 검증(R5), 금지 패턴 검수, 상태 게이트 판정 — 순수 함수 | FR-3, FR-6 |
| `src/storyforge/providers.py` | 모델 프로바이더 인터페이스 + StubProvider(키리스 데모) + OpenAI 호환 프로바이더 | FR-2, FR-3, FR-5 |
| `src/storyforge/render.py` | PIL 템플릿 합성 (4:5, 하단 그라데이션, 강조색) | FR-4 |
| `src/storyforge/services.py` | 파이프라인 오케스트레이션 (등록→분석→생성→합성→검수→내보내기) | §5 |
| `src/storyforge/export.py` | 게시 패키지 폴더/zip 생성 | FR-7 |
| `src/storyforge/web.py` | HTTP 서버 + JSON API + 정적 파일 서빙 | 화면 |

## 3. 공개/프라이빗 분리 (OSS 경계)

| 구분 | 위치 | Git |
|---|---|---|
| 공개 코어 | 코드, `docs/`, `config/default.json`, `config/user.example.json`, `.env.example` | 커밋 |
| 개인 설정 | `config/user.json` (폰트 경로, 언어, 템플릿 색상 등 개인 취향) | **ignore** |
| 비밀 | `.env` (API 키만. 코드·설정 파일에 키를 쓰지 않는다) | **ignore** |
| 개인 데이터 | `data/` (소재 원본, 완성본, 성과 기록), `private/` (개인 노트·계정 정보) | **ignore** |

- 판정 규칙: "다른 사람이 클론해도 되는가?" — 아니면 위 표의 프라이빗 위치로.
- 데모는 시크릿 없이 돈다: `make demo`는 StubProvider + 합성 샘플 소재로 전체 플로우를 보여준다.

## 4. 설정 3-layer

1. `config/default.json` — 커밋되는 기본값
2. `config/user.json` — 개인 오버라이드 (없으면 건너뜀)
3. 환경변수 — `PB_` 접두사 (예: `PB_PROVIDER`, `PB_DATA_DIR`)와 `.env`의 API 키

우선순위: 환경변수 > user.json > default.json (항목 단위로 덮어쓴다).

## 5. 프로바이더 인터페이스 (Ports)

```python
class CopyProvider(Protocol):
    def analyze(self, image_path: str) -> AnalysisResult: ...   # 핵심 사실 후보 + 보이는 정보
    def generate(self, fact: str, *, visible_info: list[str], topic: str, humor: bool, count: int) -> list[CopyCandidate]: ...
    def localize(self, text: str, *, fact: str, target_lang: str) -> list[CopyCandidate]: ...
```

- `stub`: 결정적 템플릿 기반. 데모·테스트 전용. 실제 품질 목적이 아님을 README에 명시.
- `openai-compatible`: `base_url + api_key + model` 환경변수로 어떤 벤더든 연결 (OpenAI 호환 Chat Completions). 비전 분석은 이미지 입력 지원 모델에서만.

## 6. 데이터

- `data/index.json` — 소재 인덱스 (id, 메타데이터, 상태, 카피, 검수 결과, 성과)
- `data/materials/<id>.<ext>` — 원본
- `data/outputs/<id>/` — 렌더 결과·패키지
- 파일 경로는 인덱스에 **데이터 디렉터리 기준 상대 경로**로만 저장한다 (머신 이동성).

## 7. 단계 연결

- P0 (구현 완료): FR-1~FR-4, FR-6(기본), FR-7, 스텁+OpenAI 호환 프로바이더, 웹 UI, 데모 시드
- P1 (구현 완료): FR-5 현지화 6개 언어 + 전 언어 일괄, FR-8 배치(카피·합성·현지화), 승인 패턴 재활용(확정 카피 자동 적재 → 생성 시 참고), 설정 화면(user.json 저장)
- P2 (구현 완료): FR-9 소싱 보조(쿼리 생성 + 후보 수집함), 성과 분석(주제별·상위 게시물), 상태 보드
- P3 (구현 완료): FR-10 반자동 게시 큐, FR-11 AI 재생성 소재 (이미지 생성 프로바이더 포트 — 스텁/OpenAI 호환 이미지 API). 게시 실행은 앱 밖의 운영자(연결된 플랫폼 도구)가 하고, 앱은 큐와 결과 기록만 담당한다 — 채널이 사용자마다 다르고 게시 승인은 플랫폼 도구에서 받는 구조가 맞기 때문이다
