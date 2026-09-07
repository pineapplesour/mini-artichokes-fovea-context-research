# 런타임 아키텍처 옵션

최종 업데이트 날짜: 2026년 5월 16일(KST)

이 문서는 Universal Artichoke가 브라우저 프론트엔드에서 HTML/CSS와 작은 JavaScript 커널을 기본값으로 두는 이유를 기록합니다. 이 결정은 취향이 아니라 제품 대상 환경에서 나온 운영 제약입니다.

## 현재 입장

플랫폼 계약은 구현 언어보다 중요합니다.

```text
DB/corpus -> engine contract -> API/jobs/source windows -> web/native frontend
```

다음 계약을 보존하면 런타임은 교체할 수 있습니다.

- 공개 API 경로.
- 내구성 있는 비동기 작업 의미.
- `source-grounded-v2` 결과 구조.
- source-window 하이라이트.
- 웹과 네이티브 thin shell의 기능 동등성.
- 저대역폭 예산.
- 테스트와 검증기 범위.

## 왜 경량 JavaScript를 기본값으로 둡니다

이 프로젝트의 웹 제품은 구형 저가형 휴대폰, 낮은 RAM/CPU, 불안정한 네트워크, 1Mbps 수준의 연결에서도 동작해야 합니다. 따라서 첫 화면 바이트 수, 초기 실행 시간, 캐시 안정성, 오프라인 복구, 오래된 브라우저 호환성은 부가 품질이 아니라 제품 요구사항입니다.

브라우저에서 공유 UI 커널이 처리하는 일은 대부분 CPU 연산이 아니라 상태와 입출구 조정입니다.

- 작업 상태 머신.
- SSE와 polling 대체 경로.
- 로컬 채팅 목록과 오프라인 제출 대기열 조정.
- `jobId -> assistantMessageId` 소유권 유지.
- 인용 클릭과 source-window 매핑.
- 안전한 Markdown 렌더링.
- i18n 바인딩.
- service worker 업데이트 정책.

이 영역의 주요 실패는 JavaScript가 느려서 생기는 문제가 아닙니다. 제품별 제출 핸들러 중복, 오래된 service worker 캐시, 일부 문자열만 바뀌는 i18n, 다른 채팅에 결과가 붙는 상태 소유권 오류, source-window offset 어긋남이 핵심 문제입니다. 따라서 해결책은 무거운 프레임워크로 덮는 것이 아니라 공유 UI 커널, 상태 머신, `data-action`, `data-bind`, `data-i18n`, 검증기를 고정하는 것입니다.

## 프레임워크와 시스템 언어 평가

### 현재 일반 웹 셸

일반 HTML/CSS와 작은 JavaScript 커널은 가장 낮은 의존성 표면을 가집니다. 감사가 쉽고, 오래된 브라우저와 낮은 대역폭에서 유리하며, thin WebView 네이티브 셸에 넣기 쉽습니다. hydration 실패 모드도 없습니다.

약점도 명확합니다. 제품별 JS가 늘어나면 `islam-chat.js`, `tcm-chat.js`, `simli-chat.js`가 조금씩 다른 버그를 가질 수 있습니다. 이 약점은 제품별 JS 자유도를 늘리는 방식이 아니라 공유 UI 커널 경계를 고정하는 방식으로 해결합니다.

### Svelte

Svelte는 컴포넌트를 빌드 시점에 컴파일하므로 향후 제품 스킨 작성 도구로 검토할 수 있습니다. 다만 Svelte를 쓰더라도 제품별로 제출, polling, 취소, 세션, source-window, i18n을 다시 구현하면 안 됩니다. 컴파일된 출력이 현재 셸보다 작거나 같고, 1Mbps/구형 기기 검증을 통과하며, 기존 공유 UI 커널에 연결되는 경우에만 채택할 수 있습니다.

### React

React는 전문적으로 사용할 수 있고 SSR 또는 Server Components와 함께 좋은 구조를 만들 수 있습니다. 그러나 저사양 웹 대상에서는 hydration, 클라이언트 번들, 상태 중복, 빌드 체인 복잡도가 실제 비용입니다. React를 채택하려면 공유 상태 머신 경계, 번들 예산, SSR/Server Components 운영 역량, 브라우저 검증을 함께 증명해야 합니다.

### Flutter

Flutter는 웹과 네이티브 앱을 한 코드베이스에서 만들 수 있고 웹 Wasm도 지원합니다. 그러나 공용 저대역폭 웹 셸의 기본값으로는 무겁습니다. 렌더링 모델과 산출물 크기, 고급 Wasm/멀티스레드 웹 출력의 브라우저/헤더 제약이 있습니다. 별도 고급 네이티브 앱에는 적합할 수 있지만, 1Mbps와 구형 휴대폰에서 현재 셸을 실제 산출물로 이기기 전에는 기본 웹 선택지가 아닙니다.

### Rust, C, WebAssembly

Rust/C/Wasm은 UI 배치와 버튼 상태를 해결하기 위한 기본 도구가 아닙니다. 이들은 안정적인 경계 뒤에서 측정된 병목에 적합합니다.

- 토크나이저와 청크 경계 감지.
- 대형 텍스트 정규화.
- 중복 제거, MinHash, SimHash.
- 그래프 구성과 탐색.
- 로컬 재정렬 primitive.
- SQLite/FTS 보조 색인.
- 대형 아티팩트 파싱.
- 대용량 문서의 source-window span 매핑.
- 압축과 체크섬 도구.

권장 통합 경로는 다음과 같습니다.

```text
Python/JS caller -> Rust CLI or service -> JSON artifacts
Python caller -> Rust extension module via PyO3/maturin
Browser/native wrapper -> WASM module for isolated CPU-heavy transforms
Tauri/native app -> Rust command API for local-only app tasks
```

현재 구현이 병목이라는 검증 결과 없이 UI 경로를 Rust/C로 다시 쓰지 않습니다.

### Tauri와 Rust 네이티브 셸

Tauri는 데스크톱/모바일 래퍼와 로컬 Rust 명령이 필요할 때 유용합니다. 그러나 공개 웹 앱을 대체하지 않습니다. Tauri도 웹 프론트엔드와 WebView를 사용하므로 제출 중복, i18n drift, source-window 상태 같은 브라우저 상태 버그를 자동으로 없애지 않습니다.

## 채택 기준

대체 런타임이나 프레임워크는 다음을 증명해야 합니다.

- 현재 셸보다 작거나 같은 전송 바이트 수.
- 구형 저가형 휴대폰에서 같거나 더 빠른 시작 시간.
- 1Mbps와 불안정 네트워크에서 동일한 제출, 재시도, 오프라인 복구.
- 웹과 네이티브 thin shell의 기능 동등성.
- 공유 UI 커널 경계 유지.
- 제품 스킨이 작업, 세션, source-window, i18n, 오프라인 동작을 복제하지 않는 구조.
- `python3 tools/verify_repo_contracts.py`와 프론트 검증기의 통과.

## 권장 단기 아키텍처

현재 권장 구조는 다음 순서입니다.

1. HTML/CSS와 작은 JavaScript 공유 UI 커널을 유지합니다.
2. 제품별 JS를 줄이고 `data-action`, `data-bind`, `data-i18n` 계약으로 수렴합니다.
3. 제품 스킨은 레이아웃, 색, 모션, 타이포그래피, 제품 정체성을 자유롭게 소유합니다.
4. 공유 UI 커널은 제출, 작업, 취소, 진행 표시, 결과 연결, source-window, i18n, 오프라인 제출 대기열, 세션 토큰을 소유합니다.
5. 관리가 어려운 제품 스킨 작성에 한해 작은 JavaScript로 컴파일되는 Svelte 같은 도구를 검토합니다.
6. 무거운 계산만 Rust/C/Wasm worker 또는 서버 Rust/C++ 경계로 분리합니다.

목표는 “영원히 순수 JavaScript만 사용”이 아닙니다. 목표는 저사양 환경에서 작동하는 최소 런타임을 유지하면서도, 공유 UI 커널로 유지보수 안정성을 확보하고, 측정된 병목만 더 낮은 레벨 언어로 옮기는 것입니다.

## 기본 기술 참고

아래 참고는 프레임워크와 런타임 사실 확인에만 사용합니다. Universal Artichoke의 실제 계약은 이 저장소 문서가 기준입니다.

- Svelte는 브라우저 작업 일부를 빌드 단계로 이동시키는 컴파일 모델을 설명합니다: https://svelte.dev/docs/svelte/overview
- React Server Components는 클라이언트 번들 전에 서버/빌드 환경에서 렌더링됩니다: https://react.dev/reference/rsc/server-components
- Flutter는 웹 컴파일 대상으로 WebAssembly를 지원하고 웹 renderer를 문서화합니다: https://docs.flutter.dev/platform-integration/web/wasm 및 https://docs.flutter.dev/platform-integration/web/renderers
- Tauri는 command/invoke bridge를 통해 Rust command를 웹 프론트엔드에 노출합니다: https://tauri.app/develop/calling-rust/
