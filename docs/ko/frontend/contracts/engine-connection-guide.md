# 프론트엔드 엔진 연결 가이드

최종 업데이트 날짜: 2026년 5월 15일(KST)

이 가이드는 디자인/프론트엔드 팀을 위한 것입니다. 각 디자이너가 작업 상태, API 호출, 인용, 저장소를 직접 구현하지 않아도 제품 디자인이 메모리 엔진에 연결되는 방법을 설명합니다.

## 코어 모양

제품 페이지는 beta-6에 직접 연결되지 않습니다.

```text
제품 스킨
  -> 선언적 slot과 data 속성
  -> 공유 UI 커널
  -> 공유 클라이언트/작업 런타임
  -> 제품 API
  -> beta-6 메모리 엔진
```

디자인 팀은 제품 스킨을 소유합니다. 공유 UI 커널은 동작을 소유합니다.

공유 UI 커널은 레이아웃을 소유하지 않습니다. 버튼 위치, 카드 배치, 시각적 밀도, 애니메이션은 제품 스킨에 속합니다.

## 제품 스킨 책임

제품 스킨은 다음을 제공합니다.

- 경로 이름;
- 언어 목록
- 시각적 토큰
- HTML 슬롯;
- i18n 키를 통한 예시 및 빈 상태 복사;
- CSS 및 모션;
- 선택적인 제품별 카드 구성.

다음 동작은 제품 스킨이 직접 구현하지 않습니다.

- 직접 엔진 호출;
- 작업 polling;
- 작업 token;
- 내구성 있는 채팅 저장 공간
- 소스 창 오프셋 수학;
- 언어 상태 변경;
- 네이티브/웹 기능 패리티.
- 제출, 폴링, 취소, 소스 창, 인용, i18n, 오프라인 제출 대기열 또는 세션 토큰 동작.

## 공유 UI 커널 책임

공유 UI 커널은 다음을 소유합니다.

- `SUBMIT_QUESTION` 멱등성;
- `jobId -> chatId -> assistantMessageId` 소유권;
- 진행 상태 렌더링;
- `POST /api/{product}/jobs`;
- `GET /api/jobs/{jobId}`;
- `GET /api/jobs/{jobId}/events`;
- `GET /api/jobs/{jobId}/result`;
- `POST /api/jobs/{jobId}/cancel`;
- `GET /api/{product}/source-window`;
- 로컬 채팅 캐시;
- 오프라인 제출 대기 동작;
- 인용 클릭 처리
- i18n을 다시 렌더링합니다.

## 필수 마크업 계약

디자인은 속성을 통해 의도를 드러냅니다.

```html
<form data-action="submit-question">
  <textarea data-bind="question-input" data-i18n-placeholder="chat.placeholder"></textarea>
  <button data-action="submit-question" data-i18n="chat.submit"></button>
</form>

<section data-bind="chat-list"></section>
<section data-bind="messages"></section>
<section data-bind="progress"></section>
<article data-bind="answer"></article>
<div data-bind="citations"></div>
```

소스 제어는 임시 DOM ID가 아닌 엔진 증거 ID를 사용합니다.

```html
<button data-action="open-source" data-source-id="S24" data-claim-id="C7"></button>
```

런타임은 이를 소스 창 API와 정확한 하이라이트 오프셋에 매핑합니다.

## 제품 매니페스트 계약

각 제품 스킨은 매니페스트에서 파생되어야 합니다.

```json
{
  "product": "islam",
  "landingRoute": "/islam-bayyinah.html",
  "chatRoute": "/islam-bayyinah-chat.html",
  "apiProduct": "islam",
  "languages": ["ko", "en", "ar", "ur"],
  "capabilities": ["chat", "citations", "sourceWindow", "offlineOutbox"]
}
```

매니페스트 변경이 허용됩니다. 공유 런타임 의미 체계를 깨는 것은 아닙니다.

## 로컬 테스트 경로

하나의 제품 서버를 실행합니다.

```bash
RELIGION_LLM_DISABLED=1 python3 -m uvicorn apps.islam.server:app --host 127.0.0.1 --port 8061
RELIGION_LAWKEY_DB_PATH=/var/lib/universal-artichoke/lawkey/precedents.sqlite3 python3 -m uvicorn apps.lawkey.server:app --host 127.0.0.1 --port 8037
```

열기:

```text
http://127.0.0.1:8061/islam-bayyinah.html
http://127.0.0.1:8037/
```

Lawkey는 공유 프런트엔드 스킨 규칙의 예외입니다. 원래 디자인과 엔진은 `external/lawkey-original/`에 유지되는 반면 Universal은 `integrations/lawkey/original-app-contract.json`에 어댑터 계약을 제공하고 `external/lawkey-original/lib/universal-ui-kernel.ts`에 후크 수준 기능 경계를 제공합니다. 이는 공유 셸 제품과의 완전한 단일 런타임 통합이 아닙니다.

PR 전 최소 확인 사항:

```bash
python3 tools/verify_repo_contracts.py
pytest tests/test_frontend_static.py tests/test_app_shell_parity.py -q
python3 tools/sync_native_shell_assets.py --check
```

디자인으로 인해 채팅 동작이 변경되면 브라우저 제출 확인 프로그램을 실행하고 JSON 아티팩트 경로를 PR에 연결해야 합니다.
