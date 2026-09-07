# 프런트엔드 요구 사항

최종 업데이트 날짜: 2026년 5월 16일(KST)

이 문서는 디자인/프런트엔드 팀이 과감한 제품 디자인을 만들면서도, 엔진과 가까운 고정 프런트엔드 기반에 안전하게 연결하는 방법을 정의합니다.

디자인팀은 시각적 레이아웃, 모션, 타이포그래피, 제품 아이덴티티, 제품별 구성을 변경할 수 있습니다. 그러나 제품 스킨은 공유 기반에 연결되어야 하며, 페이지마다 작업 상태나 엔진 연결을 다시 구현하지 않습니다.

## 핵심 원칙

디자인 작업은 엔진 가까이에 있는 프런트엔드 기반에 연결됩니다.

```text
제품 스킨 / HTML slot / CSS / animation
  -> 공유 UI 커널
  -> 타입이 정해진 상태 머신
  -> 허용된 effect
  -> API/작업/source-window 계약
```

디자이너는 셸에서 자유롭게 실험할 수 있습니다. 기반 구조는 작업 상태, 저장소, 언어 전환, 엔진 연결, source-window 동작을 제품 전반에서 동일하게 유지합니다.

## 왜 가벼운 JavaScript 중심 구조를 기본값으로 둡니다

이 제품군은 구형 휴대폰, 낮은 RAM/CPU, 1Mbps 수준의 느린 네트워크, 불안정한 연결을 실제 사용 환경으로 봅니다. 따라서 첫 화면 바이트 수, 초기 실행 시간, 캐시 안정성, 오프라인 복구, 오래된 브라우저 호환성은 선택 사항이 아니라 요구사항입니다.

React, Svelte, Flutter, Rust/C/Wasm 경로는 금지되지 않습니다. 다만 검토 기준이 다릅니다.

- React는 hydration, 클라이언트 번들, 상태 중복 비용을 증명 없이 추가하면 안 됩니다.
- Svelte는 공유 UI 커널이 잠긴 뒤 제품 스킨 작성 도구로 검토할 수 있습니다.
- Flutter는 웹/네이티브 공유 장점이 있지만 공용 저대역폭 웹 셸의 기본값으로는 무겁습니다.
- Rust/C/Wasm은 UI 배치가 아니라 토크나이저, 중복 제거, span 매핑 같은 측정된 병목에 사용합니다.

프론트의 반복 버그는 대부분 속도 문제가 아니라 상태 소유권 문제입니다. 그러므로 유지보수는 무거운 프레임워크가 아니라 공유 UI 커널, 상태 머신, `data-action`, `data-bind`, `data-i18n`, 검증기로 해결합니다.

## 대상 프런트엔드 아키텍처

```text
frontend/
  FRONTEND_REQUIREMENTS.md
  contracts/
    ui-state-machine.md
    engine-connection-guide.md
web/
  shared-client.js
  chat-store.js
  job-events.js
  job-progress.js
  job-cancel.js
  ui-i18n.js
  app-shell-manifest.json
  <product>.html
  <product>-chat.html
  <product>-chat.js
native/
  android/
  ios/
```

향후 마이그레이션은 반복되는 제품 JS를 공유 UI 커널에 집중해야 합니다. 그 전까지 제품 JS는 이 계약과 엔진 연결 지침을 따라야 합니다.

## 잠긴 런타임 계약

모든 제품 UI는 동일한 개념적 상태 시스템을 사용해야 합니다.

```text
booting
idle
composing
submitting
queued
running
completed
failed
cancelling
cancelled
source_open
offline_queued
```

허용되는 명령은 다음과 같습니다.

```text
BOOT
SUBMIT_QUESTION
CANCEL_JOB
RETRY_JOB
CHANGE_LANGUAGE
SELECT_CHAT
CREATE_CHAT
DELETE_CHAT
OPEN_SOURCE
CLOSE_SOURCE
EXPAND_SOURCE_BEFORE
EXPAND_SOURCE_AFTER
NETWORK_OFFLINE
NETWORK_ONLINE
JOB_STATUS_RECEIVED
JOB_RESULT_RECEIVED
JOB_FAILED
```

제품 페이지는 시각적 상태를 이러한 공유 상태에 연결합니다. 하나의 제품만 이해하는 숨겨진 작업 상태를 만들지 않습니다.

커널은 동작만 제어합니다. 버튼 위치, 레이아웃, 시각적 위계, 제품 브랜딩, 카드 배치, 애니메이션 방향은 제품 스킨의 책임입니다. 자세한 경계는 `frontend/contracts/kernel-boundary.md`에 있습니다.

## 협상할 수 없는 UI 불변성

아래 항목은 취향이 아니라 구조적 불변성입니다.

1. 새 `clientActionId`가 없으면 같은 채팅에서 이미 제출/작업이 활성화된 동안 `SUBMIT_QUESTION`은 무시됩니다.
2. 각 제출은 정확히 하나의 사용자 메시지와 하나의 답변 placeholder를 생성하거나 재사용합니다.
3. 결과는 같은 `jobId`를 소유한 답변 placeholder에만 붙을 수 있습니다.
4. 취소된 작업은 나중에 최종 답변을 추가하지 않습니다.
5. 다른 채팅의 작업 결과가 현재 채팅을 덮어쓸 수 없습니다.
6. 언어 변경은 i18n key에서 다시 렌더링합니다. 임의 text node를 수동으로 patch하지 않습니다.
7. 표시되는 모든 UI 문자열은 i18n key, 사용자/소스 텍스트, 승인된 고유명사 중 하나입니다.
8. 인용은 source-window request에 매핑되는 경우에만 클릭할 수 있습니다.
9. source window는 경계가 있는 텍스트와 정확한 highlight offset을 표시해야 합니다.
10. 웹과 네이티브 셸 기능은 `web/app-shell-manifest.json`와 일치해야 합니다.
11. event listener는 한 번만 위임하거나 등록해야 합니다. 제품 재렌더링이 중복 listener를 쌓으면 안 됩니다.
12. 제품 페이지는 공유 chat/session storage 계층 외부에 작업 token을 직접 저장하지 않습니다.

## 디자이너가 자유롭게 바꿀 수 있는 것

- 버튼 위치와 레이아웃.
- 시각적 레이아웃과 제품 아이덴티티.
- 색상 시스템과 타이포그래피.
- 애니메이션과 전환.
- evidence card 배열.
- progress indicator 스타일.
- source-window 표시 스타일.
- landing/chat 구성.
- 제품별 empty state와 예시.
- 가로 overflow가 없는 반응형 레이아웃.

## 공유 기반에 속하는 것

- API endpoint 경로 또는 token header.
- 작업/session/access token 의미.
- `source-grounded-v2` field name.
- 상태 머신 event 이름.
- storage key 소유권 규칙.
- 네이티브 manifest capability 목록.
- service worker cache 동작과 cache version 정책.
- i18n catalog 구조.
- source-window span math.

공유 기반은 renderer hook과 slot 계약을 노출할 수 있습니다. 그러나 제품의 제출 버튼, 진행 표시, source drawer, citation card 위치를 하드코딩하지 않습니다.

## 필수 제품 스킨 인터페이스

각 제품 스킨은 결국 다음 형태로 표현될 수 있어야 합니다.

```json
{
  "product": "islam",
  "routes": {
    "landing": "/islam-bayyinah.html",
    "chat": "/islam-bayyinah-chat.html"
  },
  "languages": ["en", "ko", "ar", "ur"],
  "theme": {
    "tokens": {},
    "components": {}
  },
  "i18n": {},
  "examples": [],
  "safetyNoticeKey": "safety.islam"
}
```

스킨은 제품의 모양과 느낌을 결정합니다. 공유 기반은 작업, 언어, 저장소, 엔진 연결, source window의 작동 방식을 결정합니다.

## 구조적 안전성을 갖춘 디자인 자유

깨지기 쉬운 동작 없이 파격적인 디자인을 허용하려면 다음 규칙을 지켜야 합니다.

- 디자이너는 마크업 slot과 CSS variable/class를 편집합니다.
- 동작은 `data-action`, `data-state`, `data-bind`, `data-i18n`를 통해 붙습니다.
- 런타임은 해당 속성을 읽고 command를 실행합니다.
- 제품 코드는 beta-6 작업에 대해 `fetch`를 직접 호출하지 않습니다.
- 제품 코드는 저장된 채팅 상태를 직접 변경하지 않습니다.
- 제품 코드는 `onclick`을 반복적으로 직접 바인딩하지 않습니다.
- 제품 코드는 제출, polling, 취소, 진행 표시, 결과 연결, source-window, 인용 매핑, i18n 상태, 오프라인 제출 대기열, 세션 토큰 동작을 복제하지 않습니다.

예시는 다음과 같습니다.

```html
<button data-action="submit-question" data-i18n="chat.submit"></button>
<button data-action="cancel-job" data-visible-state="queued running"></button>
<article data-bind="answer"></article>
<button data-action="open-source" data-source-id="S24"></button>
```

## 필수 프런트엔드 PR 게이트

최소 검증은 다음과 같습니다.

```bash
python3 tools/verify_repo_contracts.py
pytest tests/test_frontend_static.py tests/test_app_shell_parity.py tests/test_low_end_runtime_verifier.py tests/test_low_bandwidth_verifier.py -q
python3 tools/sync_native_shell_assets.py --check
```

실제 채팅 동작을 변경할 때는 다음 검증을 추가합니다.

```bash
python3 tools/verify_browser_submit_path.py ... --output runs/<artifact>.json
```

네이티브 shell asset을 변경하는 경우 다음 검증을 추가합니다.

```bash
python3 tools/sync_native_shell_assets.py
pytest tests/test_native_shell_parity.py -q
```

## 프런트엔드 버그 정책

UI 버그가 발견되면 그 화면만 patch하지 않습니다. 불변성을 추가하거나 갱신합니다.

예시는 다음과 같습니다.

| 버그 | 구조적 수정 |
|---|---|
| 더블클릭으로 무한 job이 생성됩니다 | command idempotency + reducer guard + test |
| 언어 변경이 일부 label에만 적용됩니다 | raw visible text/i18n coverage gate |
| 결과가 잘못된 채팅에 붙습니다 | `jobId -> assistantMessageId` ownership invariant |
| source link가 잘못된 인용문을 엽니다 | source-window span verifier |
| 재렌더링 후 버튼이 작동하지 않습니다 | delegated event binding rule |
