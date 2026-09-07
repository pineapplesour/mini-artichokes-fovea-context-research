# UI State Machine Contract

Last updated: 2026-05-14 KST

This contract is intentionally framework-neutral. It can be implemented in plain DOM, React, Flutter, Swift, Kotlin, or any future shell.

## State

Minimum state shape:

```json
{
  "product": "islam",
  "language": "ko",
  "activeChatId": "chat-...",
  "chats": {},
  "jobs": {},
  "network": "online",
  "sourceWindow": null,
  "ui": {
    "phase": "idle",
    "elapsedSeconds": 0,
    "progressStage": "queued"
  }
}
```

## Command Rules

Commands are the only way UI state changes.

```text
event -> command -> reducer -> effects -> reducer -> render
```

The renderer must not start network calls. Effects must not mutate DOM directly.

## Submit Idempotency

Every submit must include:

```json
{
  "clientActionId": "uuid",
  "chatId": "chat-...",
  "userMessageId": "msg-...",
  "assistantMessageId": "msg-..."
}
```

If the same `clientActionId` is observed again, the runtime reuses the existing job or outbox item. It must not create a second job.

## Job Ownership

```text
jobId -> chatId -> assistantMessageId
```

A result may only update the assistant message linked to the same job. If the active chat changed while the job was running, the result still attaches to its original chat.

## Language

Language is state, not a DOM patch.

```text
CHANGE_LANGUAGE -> state.language -> render(state)
```

All UI labels resolve through i18n keys during render.

## Source Window

Opening a source requires:

```json
{
  "sourceId": "canonical source id",
  "start": 123,
  "end": 180,
  "radius": 900,
  "citationLabel": "S24"
}
```

The rendered highlight must use server-returned `highlightStart` and `highlightEnd`, not client-side fuzzy matching.

