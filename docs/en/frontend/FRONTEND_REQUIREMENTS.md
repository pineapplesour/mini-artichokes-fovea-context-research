# Frontend Requirements

Last updated: 2026-05-16 KST

This file defines how the design/frontend team can create bold product designs while connecting to a fixed engine-near frontend foundation.

The design team may change visual layout, motion, typography, product identity, and product-specific composition. The product skin connects to the shared foundation; it does not reimplement job state or engine wiring per page.

## Core Principle

Design work connects to an engine-near frontend foundation:

```text
Product skin / HTML slots / CSS / animation
  -> shared UI kernel
  -> typed state machine
  -> allowed effects
  -> API/job/source-window contract
```

Designers can be radical in the shell. The foundation keeps job state, storage, language switching, engine connection, and source-window behavior consistent across products.

## Why The Frontend Stays Close To Plain JavaScript

The products target users on old phones, low RAM/CPU, unstable networks, and roughly 1Mbps connections, including users in third-world environments. Shipped bytes, startup time, cache reliability, offline recovery, and old-browser compatibility are requirements, not preferences.

React, Svelte, Flutter, and Rust/C/Wasm paths are not banned. They have different gates:

- React must not add hydration, client-bundle, and state-duplication costs without proof.
- Svelte may be evaluated as a product-skin authoring tool after the shared UI kernel is locked.
- Flutter has web/native sharing advantages, but it is heavy for the public low-bandwidth web shell by default.
- Rust/C/Wasm belongs in measured hot paths such as tokenizers, dedupe, and span mapping, not UI geometry.

The recurring frontend bugs are mostly state ownership bugs, not speed bugs. Maintenance is handled through the shared UI kernel, state machine, `data-action`, `data-bind`, `data-i18n`, and verifiers rather than product-specific runtime freedom.

## Target Frontend Architecture

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

Future migration should concentrate repeated product JS into a shared UI kernel. Until then, product JS must follow this contract and the engine connection guide.

## Locked Runtime Contract

Every product UI must use the same conceptual state machine:

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

Allowed commands:

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

Product pages connect visual states to these shared states. They do not create hidden job states that only one product understands.

The kernel controls behavior only. It must not prescribe button position, layout, visual hierarchy, product branding, card placement, or animation direction. Those remain product-skin responsibilities; see `frontend/contracts/kernel-boundary.md`.

## Non-Negotiable UI Invariants

These are structural, not stylistic:

1. `SUBMIT_QUESTION` is ignored while a submit/job is already active for the same chat unless it has a new `clientActionId`.
2. Each submit creates or reuses exactly one user message and one assistant placeholder.
3. A result can only attach to the assistant placeholder that owns the same `jobId`.
4. Cancelled jobs must not append final answers later.
5. A chat cannot be overwritten by another chat's job result.
6. Language change re-renders from i18n keys; it must not patch random text nodes manually.
7. Every visible UI string is either an i18n key, user/source text, or an approved proper noun.
8. Citations are clickable only if they map to a source-window request.
9. Source windows must show bounded text and exact highlight offsets.
10. Web and native shell capabilities must match `web/app-shell-manifest.json`.
11. Event listeners must be delegated or registered once; product re-rendering must not stack duplicate listeners.
12. Product pages must not directly store job tokens outside the shared chat/session storage layer.

## What Designers May Change Freely

- button position and layout;
- visual layout and product identity;
- color systems and typography;
- animations and transitions;
- evidence card arrangement;
- progress indicator style;
- source-window presentation style;
- landing/chat composition;
- product-specific empty states and examples;
- responsive layout, as long as no horizontal overflow.

## What Belongs To The Shared Foundation

- API endpoint paths or token headers;
- job/session/access token semantics;
- `source-grounded-v2` field names;
- state machine event names;
- storage key ownership rules;
- native manifest capability list;
- service-worker cache behavior and cache-version policy;
- i18n catalog structure;
- source-window span math.

The shared foundation may expose renderer hooks and slot contracts, but it must not hard-code where a product puts a submit button, a progress indicator, a source drawer, or a citation card.

## Required Product Skin Interface

Each product skin should eventually be expressible as:

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

The skin decides how the product looks and feels. The shared foundation decides how jobs, language, storage, engine connection, and source windows behave.

## Design Freedom With Structural Safety

To allow radical designs without fragile behavior:

- designers edit markup slots and CSS variables/classes;
- behavior is attached through `data-action`, `data-state`, `data-bind`, and `data-i18n`;
- runtime reads those attributes and dispatches commands;
- product code must not directly call `fetch` for beta-6 jobs;
- product code must not directly mutate persisted chat state;
- product code must not directly bind `onclick` repeatedly;
- product code must not duplicate submit, polling, cancellation, progress, result attachment, source-window, citation mapping, i18n state, offline outbox, or session-token behavior.

Example:

```html
<button data-action="submit-question" data-i18n="chat.submit"></button>
<button data-action="cancel-job" data-visible-state="queued running"></button>
<article data-bind="answer"></article>
<button data-action="open-source" data-source-id="S24"></button>
```

## Required Frontend PR Gates

Minimum:

```bash
python3 tools/verify_repo_contracts.py
pytest tests/test_frontend_static.py tests/test_app_shell_parity.py tests/test_low_end_runtime_verifier.py tests/test_low_bandwidth_verifier.py -q
python3 tools/sync_native_shell_assets.py --check
```

When changing actual chat behavior:

```bash
python3 tools/verify_browser_submit_path.py ... --output runs/<artifact>.json
```

When changing native shell assets:

```bash
python3 tools/sync_native_shell_assets.py
pytest tests/test_native_shell_parity.py -q
```

## Frontend Bug Policy

When a UI bug is found, do not only patch that one screen. Add or update an invariant.

Examples:

| Bug | Structural fix |
|---|---|
| Double click creates infinite jobs | command idempotency + reducer guard + test |
| Language changes only some labels | raw visible text/i18n coverage gate |
| Result appears in wrong chat | `jobId -> assistantMessageId` ownership invariant |
| Source link opens wrong quote | source-window span verifier |
| Button stops working after rerender | delegated event binding rule |
