# 프론트엔드 커널 경계

최종 업데이트 날짜: 2026년 5월 16일(KST)

이 계약은 공유 UI 커널이 제어할 수 있는 것과 제어하면 안 되는 것을 정의합니다.

## 목적

프로젝트가 다음 형태로 흩어지면 안 됩니다.

```text
islam-chat.js
tcm-chat.js
simli-chat.js
hindu-chat.js
buddhist-chat.js
christian-chat.js
...
```

각 파일이 제출, polling, 취소, citation 처리, chat persistence를 조금씩 다르게 소유하면 제품마다 다른 버그가 생깁니다. 공유 커널은 하나의 동작 버그를 한 번 수정하면 모든 제품에서 제거할 수 있게 하기 위해 존재합니다.

## 커널은 동작만 소유합니다

공유 UI 커널은 다음 동작을 소유합니다.

- 제출 멱등성.
- 작업 생성.
- polling 대체 경로가 있는 SSE.
- 취소.
- 진행 상태.
- 올바른 채팅에 대한 결과 소유권과 연결.
- 내구성 있는 채팅/세션 저장.
- source-window와 인용 매핑.
- 안전한 Markdown 렌더링.
- i18n 상태 변경.
- 오프라인 제출 대기열과 복구.
- 세션 토큰/account-subject 전달.
- 저대역폭 런타임 정책.

이 커널은 저사양 기기와 느린 네트워크에서도 작고 예측 가능해야 합니다. 오래된 휴대폰과 1Mbps 수준의 네트워크에서 중요한 것은 UI 프레임워크의 표현력이 아니라 중복 동작 제거, 작은 전송 바이트 수, 안정적인 재시도와 복구입니다.

## 스킨은 디자인을 소유합니다

제품 스킨은 다음 요소를 소유합니다.

- 버튼 위치.
- 페이지 레이아웃.
- 시각적 위계.
- 제품별 타이포그래피.
- 색, 간격, 그림자, 테두리, 애니메이션.
- 카드 배치.
- 진행 표시 스타일.
- 인용/source-window 표시 스타일.
- i18n key를 통한 제품 예시와 표시 문구.

공유 커널은 geometry, 버튼 배치, 카드 순서, 브랜드 표현, 시각 스타일을 강제하지 않습니다. 공유 커널은 스킨이 제공하는 선언 속성, slot, callback, renderer hook만 읽을 수 있습니다.

## 필수 방향

공유 셸 제품은 다음 형태로 수렴해야 합니다.

```text
제품 스킨
  -> HTML/CSS/i18n/examples/renderer slot
  -> data-action/data-bind/data-i18n
  -> 공유 UI 커널
  -> 제품 API
```

제품 코드는 다음 동작을 직접 구현하지 않습니다.

- `fetch("/api/.../jobs")`.
- 직접 작성한 작업 polling 루프.
- 직접 작성한 작업 취소 전송.
- localStorage/IndexedDB 세션 직접 변경.
- source-window offset 계산.
- 중복 i18n patch.
- 중복 오프라인 retry 로직.

## Lawkey Migration Rule

Lawkey는 기존 React/Expo 시각 구현을 유지할 수 있습니다. Lawkey의 커널 마이그레이션은 UI를 Universal HTML 셸로 바꾸는 방식이 아니라 기존 hook과 API module 뒤에서 이루어져야 합니다.

현재 Lawkey는 완전한 공유 브라우저 런타임 통합 상태가 아닙니다. `external/lawkey-original/lib/universal-ui-kernel.ts`는 기존 Lawkey API 기능을 capability boundary로 감싸고, `use-lawkey-job.ts`는 그 경계를 통해 route합니다. 제출, 상태 조회, 결과 조회, 취소, 후속 질문, source-detail 동작은 경계 뒤에 있지만, Lawkey UI는 원래 React/Expo 구현으로 유지되며 Islam/TCM/Simli와 동일한 공유 셸 런타임 파일을 실행하지 않습니다.

허용되는 Lawkey 형태는 다음과 같습니다.

```text
existing Lawkey React/Expo UI
  -> Lawkey adapter hook
  -> Universal-capability kernel boundary
  -> original Lawkey backend / beta-6-compatible engine
```

모든 Lawkey kernel 단계는 다음을 증명해야 합니다.

- 동일한 route.
- desktop과 mobile 기준에서 동일한 visual screenshot.
- 동일한 visible control.
- 동일한 document preset API behavior.
- controlled browser smoke에서 동일한 submit/result/session path.
- 생성된 `web/lawkey*.html/js` replacement shell이 없습니다.
