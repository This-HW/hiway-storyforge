# 채널 설정 가이드

## 개념

hiway-storyforge는 **하나의 파이프라인**으로 여러 인스타그램 채널을 운영할 수 있다.
채널별 차이는 설정 파일로 주입한다.

```
OSS (hiway-storyforge)          Private (your workspace)
─────────────────────           ────────────────────────
파이프라인 단계 구현             channels/*.yaml
검수 게이트                      브랜드 에셋 (이미지)
렌더 엔진                        실제 계정 ID
config/channel.example.yaml     지식 브리프, 큐 데이터
  (템플릿, 값 비어있음)
```

## 새 채널 추가하기

1. 템플릿 복사:
   ```bash
   mkdir -p channels
   cp config/channel.example.yaml channels/my_channel.yaml
   ```

2. 값 채우기:
   - `instagram.account_id`: 인스타그램 계정의 user_fbid
     (`instagram-cli accounts`로 확인)
   - `brand.*`: 브랜드 에셋 경로 (워터마크, 폰트, 색상)
   - `endcard.path`: 매 게시물 마지막 장으로 붙일 엔드카드
   - `tone`: 콘텐츠 톤 (예: "따뜻한 친구", "옆집 전문가")
   - `caption.format`: 캡션 포맷 (STYLE_RULES.md에 정의된 것)

3. 코드에서 사용:
   ```python
   from storyforge.channel import load_channel

   cfg = load_channel("my_channel")
   account_id = cfg["instagram"]["account_id"]
   tone = cfg["tone"]
   ```

## 주의사항

- `channels/*.yaml`은 `.gitignore`에 포함되어 있어 커밋되지 않는다.
- 실제 계정 ID가 들어간 설정 파일을 절대 OSS에 푸시하지 마라.
- 플레이스홀더 값(`REPLACE_WITH_*`)이 남아있으면 로더가 에러를 낸다.

## 채널 설정 찾는 순서

1. `./channels/<name>.yaml` (현재 디렉토리)
2. `~/workspace/channels/<name>.yaml`
3. `$STORYFORGE_CHANNELS_DIR/<name>.yaml` (환경변수로 지정)
