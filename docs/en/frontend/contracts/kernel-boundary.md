# Frontend Kernel Boundary

Last updated: 2026-05-15 KST

This contract defines what the shared UI kernel may control and what it must never control.

## Purpose

The project must not become:

```text
islam-chat.js
tcm-chat.js
simli-chat.js
hindu-chat.js
buddhist-chat.js
christian-chat.js
...
```

where every file owns a slightly different version of submit, polling, cancellation, citation handling, and chat persistence.

The shared kernel exists so one behavioral bug can be fixed once and removed from every product.

## Kernel Owns Behavior Only

The shared UI kernel owns:

- submit idempotency;
- job creation;
- SSE with polling fallback;
- cancellation;
- progress state;
- result ownership and attachment to the correct chat;
- durable chat/session storage;
- source-window and citation mapping;
- safe markdown rendering;
- i18n state changes;
- offline outbox and recovery;
- session token/account-subject transport;
- low-bandwidth runtime policy.

The kernel must stay small and predictable because the target environment includes old phones, low RAM/CPU, unstable networks, and roughly 1Mbps connections. The important property is not framework expressiveness; it is eliminating duplicated behavior while preserving low shipped bytes and durable retry/recovery.

## Skin Owns Design

The product skin owns:

- button position;
- page layout;
- visual hierarchy;
- product-specific typography;
- color, spacing, shadows, borders, and animation;
- card arrangement;
- progress indicator styling;
- citation/source-window presentation style;
- product examples and visible wording through i18n keys.

The shared kernel must not impose geometry, button placement, card order, brand treatment, or visual style. It may only read declared attributes, slots, callbacks, and renderer hooks supplied by the skin.

## Required Direction

Shared-shell products should converge on this shape:

```text
Product skin
  -> HTML/CSS/i18n/examples/renderer slots
  -> data-action/data-bind/data-i18n
  -> shared UI kernel
  -> product API
```

Product code should not directly implement:

- `fetch("/api/.../jobs")`;
- manual job polling loops;
- direct job cancel transport;
- direct localStorage/IndexedDB session mutation;
- source-window offset math;
- duplicate i18n patching;
- duplicate offline retry logic.

## Lawkey Migration Rule

Lawkey is allowed to keep its existing React/Expo visual implementation. Kernel migration for Lawkey must happen behind the existing hooks and API modules, not by replacing the UI with a Universal HTML shell.

The current Lawkey state is not full shared-browser-runtime integration. `external/lawkey-original/lib/universal-ui-kernel.ts` wraps the existing Lawkey API functions as a capability boundary, and `use-lawkey-job.ts` routes through that boundary. Submit/status/result/cancel/follow-up/source-detail behavior is now behind the boundary, but the Lawkey UI remains the original React/Expo implementation and does not run the same shared-shell runtime file as Islam/TCM/Simli.

Accepted Lawkey shape:

```text
existing Lawkey React/Expo UI
  -> Lawkey adapter hook
  -> Universal-capability kernel boundary
  -> original Lawkey backend / beta-6-compatible engine
```

Every Lawkey kernel step must prove:

- same route;
- same visual screenshot at desktop and mobile baselines;
- same visible controls;
- same document preset API behavior;
- same submit/result/session path under a controlled browser smoke;
- no generated `web/lawkey*.html/js` replacement shell.
