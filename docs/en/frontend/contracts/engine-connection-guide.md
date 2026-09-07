# Frontend Engine Connection Guide

Last updated: 2026-05-15 KST

This guide is for the design/frontend team. It explains how a product design connects to the memory engine without each designer hand-wiring job state, fetch calls, citations, or storage.

## Core Shape

The product page does not connect to beta-6 directly.

```text
Product Skin
  -> declarative slots and data attributes
  -> shared UI kernel
  -> shared client / job runtime
  -> product API
  -> beta-6 memory engine
```

The design team owns the Product Skin. The shared UI kernel owns behavior.

The shared UI kernel does not own layout. Button position, card placement, visual density, and animation belong to the product skin.

## Product Skin Responsibilities

A product skin provides:

- route names;
- language list;
- visual tokens;
- HTML slots;
- examples and empty-state copy through i18n keys;
- CSS and motion;
- optional product-specific card composition.

It must not own:

- direct engine fetch calls;
- job polling;
- job tokens;
- durable chat storage;
- source-window offset math;
- language state mutation;
- native/web feature parity.
- submit, polling, cancellation, source-window, citation, i18n, offline outbox, or session-token behavior.

## Shared UI Kernel Responsibilities

The shared UI kernel owns:

- `SUBMIT_QUESTION` idempotency;
- `jobId -> chatId -> assistantMessageId` ownership;
- progress state rendering;
- `POST /api/{product}/jobs`;
- `GET /api/jobs/{jobId}`;
- `GET /api/jobs/{jobId}/events`;
- `GET /api/jobs/{jobId}/result`;
- `POST /api/jobs/{jobId}/cancel`;
- `GET /api/{product}/source-window`;
- local chat cache;
- offline queued submit behavior;
- citation click handling;
- i18n re-rendering.

## Required Markup Contract

Designs expose intent through attributes:

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

Source controls use engine evidence IDs, not ad hoc DOM ids:

```html
<button data-action="open-source" data-source-id="S24" data-claim-id="C7"></button>
```

The runtime maps this to the source-window API and exact highlight offsets.

## Product Manifest Contract

Each product skin should be derivable from a manifest:

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

Changing the manifest is allowed. Breaking shared runtime semantics is not.

## Local Test Path

Run one product server:

```bash
RELIGION_LLM_DISABLED=1 python3 -m uvicorn apps.islam.server:app --host 127.0.0.1 --port 8061
RELIGION_LAWKEY_DB_PATH=/var/lib/universal-artichoke/lawkey/precedents.sqlite3 python3 -m uvicorn apps.lawkey.server:app --host 127.0.0.1 --port 8037
```

Open:

```text
http://127.0.0.1:8061/islam-bayyinah.html
http://127.0.0.1:8037/
```

Lawkey is an exception to the shared frontend skin rule: the original design and engine are preserved in `external/lawkey-original/`, while Universal supplies the adapter contract in `integrations/lawkey/original-app-contract.json` and a hook-level capability boundary in `external/lawkey-original/lib/universal-ui-kernel.ts`. This is not full single-runtime integration with the shared-shell products.

Minimum checks before PR:

```bash
python3 tools/verify_repo_contracts.py
pytest tests/test_frontend_static.py tests/test_app_shell_parity.py -q
python3 tools/sync_native_shell_assets.py --check
```

If the design changes chat behavior, run a browser submit verifier and attach the JSON artifact path to the PR.
