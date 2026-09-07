# Lawkey Original Snapshot

This directory is a source snapshot copied from:

```text
external/lawkey-original
```

It is preserved so the original Lawkey implementation remains available without
editing `external/lawkey-original` in place. Lawkey must keep the
original design and engine. Universal Artichoke only adds a thin adapter:

```text
apps.lawkey.server:app -> external/lawkey-original/backend.server:app -> original Expo dist
```

The adapter contract is recorded in:

```text
integrations/lawkey/original-app-contract.json
```

Excluded from this snapshot:

- `.git/`
- `node_modules/`
- `.tmp/`
- local checkpoints, memory logs, and task logs

Included generated artifact:

- `dist/` is included because the original backend serves it directly and this
  preserves the visible Lawkey UI without rebuilding or recreating it as a
  Universal HTML shell.

Do not create `web/lawkey.html`, `web/lawkey-chat.html`, or another lookalike
shared shell unless the user explicitly approves a Lawkey redesign.
