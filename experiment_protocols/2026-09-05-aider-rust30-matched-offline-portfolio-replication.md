# Rust30 matched offline-portfolio replication

Frozen before both calls on 2026-09-05 KST.  This is a separate replication,
not a retry or replacement inside the stopped Aider90 campaign.

## Scope and treatment

Use all 30 tasks in the already frozen complete official Aider Rust track at
`Aider-AI/polyglot-benchmark` commit
`7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`.  No task may be selected,
removed, replaced, topped up, or called separately.

The fixed candidate calls are Plain, Graph, and ordinary execution-feedback
repair.  Run two new whole-track offline routes from the ordinary candidate,
with the same P/G/R patches and bounded test outcomes: one semantic-free
structured route and one Try--Semantic-Overlap--Verify route.  Neither route
receives protected anchors.  The terminal official verifier materializes the
union with overlap priority followed by semantic-free.

To match the historical online calls exactly, do **not** pass `--rust-root` or
any other optional tool root.  The model sandbox PATH is
`/tmp/codex-node/bin:/usr/local/bin:/usr/bin:/bin`.  Hidden tests and gold stay
masked.  Calls use `gpt-5.6-luna`, medium reasoning, low verbosity, and the
existing 1,500-second agent cap.

Frozen order and unique IDs:

1. arm `semantic_free_structured_offline_portfolio`, candidate
   `semantic_free_structured_offline_portfolio_matched_v2`;
2. arm `semantic_overlap_offline_portfolio`, candidate
   `semantic_overlap_offline_portfolio_matched_v2`.

Any unsafe call, transport-null event, or timeout stops this protocol.  There
are no retries.  The earlier compiler-exposed Rust calls remain invalid and
are not reused.

## Estimands

Primary: matched offline terminal union minus the existing online terminal
union over all 30 tasks.  Secondary: corresponding route contrasts and the new
system versus fixed Plain and ordinary candidates.  Report exact paired tests
and task bootstrap intervals.  A Rust-only strong mechanism effect requires at
least `+6/30` (`+20` points) and one-sided exact `p < .05`.  Otherwise the
result may contribute only as a full-track replication within the pooled
Aider90 system analysis.

## Frozen hashes

- runner: `a682de4e251f7d93855e54570561300cd719d3e2df9245192ee14a9bb1e913bb`
- freeze: `0e53b43f5c68f48feb3f01c269de8094e480ffc653a474a0d16ff474e4207cce`
- task packet: `9984a717e82443c239396eb3b167613511051f071080f1ff7e58aa949cacc1c0`
- Plain result: `7d843c32eb24de611d1ca8a66fb36ef2d253f85b98faf822457ea1031df95e8b`
- Graph result: `54f32ad1e3c17349bc4f199fe06d4fa13b8b4ef8834fbc71057a926797a6b46b`
- ordinary result: `3324a4b80925570b22481e5e8720e6bf11175c9f10db064270514619a1b2034c`
