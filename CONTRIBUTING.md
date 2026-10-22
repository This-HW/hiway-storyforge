# Contributing

## 원칙

1. **스펙 → 설계 → 구현** 순서를 지킨다. 동작을 바꾸면 `docs/SPEC.md`를 먼저 고치고, 구조를 바꾸면 `docs/DESIGN.md`를 먼저 고친다.
2. **의존성 방향**: `web → services → (rules, render, store, providers)`. `rules`와 `render`는 순수 함수 모듈로, 다른 내부 모듈을 import하지 않는다.
3. **의존성 최소화**: 런타임 의존성은 Pillow만 유지한다. 새 의존성이 필요하면 이유와 라이선스를 PR에 적는다.
4. **프라이빗 경계**: 비밀·개인 설정·개인 데이터를 커밋하지 않는다. 위치는 `.gitignore`와 `docs/DESIGN.md` §3을 따른다.
5. 파일 경로는 데이터 디렉터리 기준 **상대 경로**로만 저장한다.

## 작업 흐름

```bash
make test     # unittest 전부 통과해야 한다
make demo     # 스텁으로 전체 플로우가 도는지 확인
```

## 커밋

- 한 커밋 = 한 가지 변경. 메시지는 무엇을·왜를 한 줄로.
