# Runtime Architecture Options

Last updated: 2026-05-16 KST

This document records why Universal Artichoke keeps plain HTML/CSS plus a small JavaScript UI kernel as the default browser frontend. This is an operating constraint, not an aesthetic preference.

## Current Position

The platform contract is more important than the implementation language:

```text
DB/corpus -> engine contract -> API/jobs/source windows -> web/native frontend
```

Any runtime can be replaced if it preserves:

- public API routes;
- durable async job semantics;
- `source-grounded-v2` result shape;
- source-window highlighting;
- web/native thin-shell capability parity;
- low-bandwidth budget;
- test and verifier coverage.

## What Should Stay Lightweight JavaScript

The web products must work for users on old low-end phones, low RAM/CPU, unstable networks, and roughly 1Mbps connections. Shipped bytes, startup time, cache reliability, offline recovery, and old-browser compatibility are product requirements.

The browser-facing shared UI kernel mostly coordinates state and I/O, not heavy CPU work:

- job state machine;
- SSE with polling fallback;
- local chat list and offline outbox coordination;
- `jobId -> assistantMessageId` ownership;
- citation click and source-window mapping;
- safe Markdown rendering;
- i18n binding;
- service-worker update policy.

The recurring failures here are not caused by slow JavaScript execution. They come from duplicated submit handlers, stale service-worker cache, partial i18n updates, result attachment to the wrong chat, and source-window offset drift. The remedy is a locked shared UI kernel, state machine, `data-action`, `data-bind`, `data-i18n`, and verifiers, not product-specific runtime freedom.

## Frontend Framework Evaluation

### Current Plain Web Shell

Plain HTML/CSS plus a small JavaScript kernel has the lowest dependency surface, is easy to audit, works well in old browsers and low bandwidth, fits thin native WebView shells, and has no framework-level hydration failure mode.

Its weakness is management stability: if every product owns its own script, `islam-chat.js`, `tcm-chat.js`, and `simli-chat.js` will each collect slightly different bugs. This is why the project locks the shared UI kernel instead of letting product scripts own behavior.

### Svelte

Svelte is a plausible future product-skin authoring layer because it compiles components and keeps browser work low. It may improve maintainability, but it must still mount onto the shared UI kernel. It must not reimplement submit, polling, cancellation, session, source-window, or i18n behavior per product.

Use Svelte only if the compiled output is no larger than the current shell, the 1Mbps/old-device verifiers still pass, and the product skin remains attached to the shared kernel.

### React

React can be used professionally, especially with SSR or React Server Components. It is not automatically better for low-end web targets. Hydration, client bundles, state duplication, and build-chain complexity are real costs for old phones and 1Mbps networks.

Use React only with strict state-machine boundaries, enforced bundle budgets, experienced SSR/Server Components maintenance, and browser verification.

### Flutter

Flutter can produce web and native apps from one codebase and supports web Wasm. It is still not the default public low-bandwidth web shell because its output and rendering model are heavier than a minimal HTML/CSS/JS shell, and advanced Wasm/multithreaded web output has browser/header constraints.

Flutter may be appropriate for a separate polished native app later, but it must not replace the low-end web shell unless benchmark artifacts prove it beats the current shell on shipped bytes, startup, and old-phone behavior.

## Where Rust Or C Can Help

Rust, C, and Wasm are not the default tools for button layout or UI state. They are useful behind stable boundaries for measured hot paths:

- tokenizer and chunk boundary detection;
- large-text normalization;
- deduplication, MinHash, and SimHash;
- graph construction and traversal;
- local reranking primitives;
- SQLite/FTS helper indexes;
- large artifact parsing;
- source-window span mapping on large documents;
- compression and checksum tooling.

Preferred integration paths:

```text
Python/JS caller -> Rust CLI or service -> JSON artifacts
Python caller -> Rust extension module via PyO3/maturin
Browser/native wrapper -> WASM module for isolated CPU-heavy transforms
Tauri/native app -> Rust command API for local-only app tasks
```

Do not rewrite UI paths in Rust/C until a verifier shows the current implementation is a bottleneck.

### Tauri / Rust Native Shell

Tauri is relevant for desktop/mobile wrappers and local Rust commands. It is not a replacement for the public web app. It still uses a web frontend and WebView, so it does not automatically eliminate submit duplication, i18n drift, or source-window state bugs.

## Adoption Gate

Any replacement runtime or framework must prove:

- equal or lower shipped bytes than the current shell;
- equal or faster startup on old low-end phones;
- identical submit/retry/offline recovery on 1Mbps and unstable networks;
- web/native thin-shell capability parity;
- preserved shared UI kernel boundary;
- no product-skin duplication of job/session/source-window/i18n/offline behavior;
- passing `python3 tools/verify_repo_contracts.py` and frontend verifiers.

## Recommended Near-Term Architecture

The recommended structure is:

1. Keep HTML/CSS plus a small JavaScript shared UI kernel.
2. Reduce product-specific JavaScript and converge on `data-action`, `data-bind`, and `data-i18n`.
3. Let product skins own layout, color, motion, typography, and identity.
4. Let the shared UI kernel own submit, jobs, cancellation, progress, result attachment, source windows, i18n, offline outbox, and session tokens.
5. Evaluate compile-to-small-JS tools such as Svelte only for product-skin authoring after the kernel is locked.
6. Move only measured heavy computation into Rust/C/Wasm workers or server-side Rust/C++ boundaries.

The target is not "pure JavaScript forever." The target is a minimal runtime that works in low-spec third-world environments, a locked shared UI kernel that prevents product-by-product bugs, and lower-level languages only where measurement proves a real hot path.

## Primary Technical References

These references are used only for framework/runtime facts. The Universal Artichoke contract above remains the source of truth for this repository.

- Svelte describes its model as moving work from the browser into the build step: https://svelte.dev/docs/svelte/overview
- React Server Components render ahead of the client bundle in a separate server/build environment: https://react.dev/reference/rsc/server-components
- Flutter supports WebAssembly as a web compilation target and documents its web renderers: https://docs.flutter.dev/platform-integration/web/wasm and https://docs.flutter.dev/platform-integration/web/renderers
- Tauri exposes Rust commands to a web frontend through its command/invoke bridge: https://tauri.app/develop/calling-rust/
