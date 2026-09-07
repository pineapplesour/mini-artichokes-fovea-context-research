# Frozen protocol: Go39 Generic transport-null replacement sensitivity

Status: frozen before the replacement model call.

## Reason for this separately labelled call

The preregistered Go39 confirmation remains failed at its integrity-promotion
gate because its fifth, Generic, invocation was not agent-complete. The raw
event stream contains `thread.started`, `turn.started`, connection retries, and
`turn.failed`, but no model message, reasoning item, tool call, or usage event.
The failure was an HTTP 404 at both WebSocket and HTTPS Codex endpoints after
15.403 seconds. The observed 26/39 workspace score is the deterministic
pre-call verified-anchor seed and is not a Generic model result.

This additional call does not repair or replace the preregistered primary
result and cannot make that experiment prospectively confirmatory. It is a
separately reported operational sensitivity analysis asking what the frozen
equal-call comparison would show after one model-complete Generic invocation.

## Frozen execution

- Benchmark: all 39 official Aider Go tasks from commit
  `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`; no selection or removal.
- Model/account: `gpt-5.6-luna`, medium reasoning, low verbosity,
  `/home/pineapple/.codex-new-account`.
- Arm: `generic_verified_union`.
- Candidate ID: `generic_verified_union_transport_replacement_01`.
- Exactly one whole-track call; no task-wise calls, top-ups, or score-based
  reruns.
- Identical frozen source, task file, runner, prompt construction, verified
  anchor seed, candidate patches, and bounded official outcome traces used by
  the failed Generic invocation.
- Runner SHA-256:
  `d8526504b1ab8c4f6251449bca24df284205142cf8707c3d66cd21a54159dbeb`.
- Evidence-index SHA-256 expected after staging:
  `d14301db8b6479467d7c4eea794d3f2850b452b97cd467cf2ec5a2392227f84f`.
- Seed-patch SHA-256 expected after staging:
  `6e7ce9080f8b402bce5bbf3ab6cfc20d0d24d2b6acf7a2d7dc12581616ed6e57`.

## Analysis boundary

If agent-complete and integrity-valid, compare the observed replacement
Generic route and its Direct union against the already frozen TOV route and
its Direct union. Report task scores, rescues, harms, net difference, exact
paired one- and two-sided values, and task IDs. Because this protocol was
written after TOV outcome inspection and adds a seventh attempted invocation,
all such comparisons are explicitly post-primary sensitivity evidence.

If this invocation has any nonzero agent exit, timeout, missing final message,
forbidden path, anchor-restoration defect, evidence mismatch, or prompt/seed
mismatch, retain it and stop without another replacement.
