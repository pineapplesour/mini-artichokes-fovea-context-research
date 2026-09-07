# beta6 빠른 분석 / 0건 검색 보정 전달 메모

2026-05-28 기준으로 Merian 화면에서 쓰는 빠른 분석 엔진 변경사항을 메인에 올렸다.
다른 제품이나 브랜치에 붙일 때는 아래 내용만 맞추면 된다.

## 무엇을 고쳤나

기존 beta6는 근거를 많이 모으는 쪽으로 설계되어 있어서 답은 안정적이지만 느렸다.
특히 후보 근거를 100개 이상 잡고, 키워드별 검색도 넓게 돌고, claim-card 분석도 많은 청크를 훑어서 PsyKey보다 체감 응답이 늦었다.

Merian 계열 화면에서는 `analysisMode: "fast"`와 `limit: 30`을 보낸다.
서버는 이 요청을 `beta6_fast`로 기록하고, 이때만 아래 제한을 건다.

- 최종 선택 근거는 최대 30개
- frontier target / stop floor / per-keyword limit도 30개 안쪽
- claim-card 청크 분석은 최대 10청크
- 기존 정밀 beta6 경로는 그대로 둔다

그래서 UI 쪽 호출 수를 바꾼 것이 아니라, 같은 beta6 파이프라인 안에서 후보 폭과 분석 청크 수를 줄여서 빨라진 것이다.

## 검색이 0건일 때의 보정

예전에는 첫 검색에서 아무것도 안 잡히면 selector/writer까지 갈 근거가 없어서 빈 답변 흐름으로 빠질 수 있었다.
지금은 일반 검색이 0건이면 제품별로 넓은 첫 라운드 검색어를 한 번 넣는다.

- Islam: `prayer salah quran hadith fiqh`, `halal haram worship scripture`
- Buddhist: `dhamma karma sutta teaching`, `buddha dharma scripture commentary`
- Catholic: `grace scripture church catechism`, `christ faith sacrament doctrine`
- Hindu: `karma dharma moksha bhagavad gita`, `upanishad atman brahman scripture`
- TCM: `감초 本草 처방 변증`, `本草 方劑 辨證 classical medicine`

이건 답을 지어내는 장치가 아니다.
첫 후보군을 비어 있지 않게 넓혀 주는 장치이고, 이후 단계는 여전히 DB에서 실제로 검색된 source id와 passage를 가지고 진행한다.
결과 메타에는 `zeroSourceBootstrap: true`와 `zeroSourceBootstrapQueries`가 남는다.

## 프론트에서 해야 할 것

Merian 방식처럼 job 생성 요청에 아래 값을 넣으면 된다.

```json
{
  "query": "사용자 질문",
  "language": "ko",
  "limit": 30,
  "analysisMode": "fast"
}
```

옛 클라이언트 호환용으로 `fastMode: true`도 받지만, 새 화면에서는 `analysisMode: "fast"`를 쓰는 쪽으로 맞춘다.
프론트가 직접 모델 API나 키를 만지면 안 되고, 항상 `/api/{product}/jobs`로 보낸다.

## 확인해야 할 것

팀원이 자기 브랜치에 붙였으면 최소한 이것을 본다.

- job 응답이나 result에 `analysisMode: "beta6_fast"`가 찍히는가
- `fastMode: true`인가
- selector의 `topK`, `frontierTarget`, `frontierStopFloor`, `perKeywordLimit`이 30 안쪽인가
- claim analyzer 메타의 `claimAnalyzerChunkCount`가 10 이하인가
- 검색 0건 테스트에서 `zeroSourceBootstrap: true`가 남고 실제 DB source id가 선택되는가
- 화면에서 각주 버튼을 누르면 source-window가 열리고, passage highlight와 위/아래 더보기가 작동하는가

## 코드 위치

- 요청 파싱: `shared_platform/server.py`
- beta6 fast/zero-source 엔진: `shared_platform/beta6.py`
- Merian 화면 호출부: `web/merian-chat.js`
- Merian 화면/스타일: `web/*-merian-chat.html`, `web/merian-chat.css`
- 앱 셸/캐시 등록: `web/app-shell-manifest.json`, `web/sw.js`
- Android 내장 프론트/상태바 처리: `native/android/app/...`
