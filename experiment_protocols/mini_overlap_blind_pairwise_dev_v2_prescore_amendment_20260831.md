# Blind pairwise development v2 — pre-score implementation amendment

## Timing and information boundary

This amendment was written after V7 completed and passed its frozen structural
and trace gates, but before the private registry was opened and before any V7
policy accuracy, rescue, harm, domain delta, or McNemar result was computed.
The observed blind preference counts do not determine any policy definition or
promotion threshold.

V7 remains bound to:

- freeze SHA-256
  `48e6db7da53a7333f63556d700a19b83b70a0f3ba694a3e9c2e320231f86f1e5`;
- certificate SHA-256
  `50d18f45c0472b9a084a12f9d0d04e081ab3d707cca4612564835c4c3d9fd2ab`;
- raw trace SHA-256
  `032644bcbbd66e87a53afb5f07eab497be11dca71f56b20db490d3c03b5320dc`;
- receipt SHA-256
  `7a79a7e5429428ceec3c0d960f175aa5b2b1b6d8278e311b89533ef86a9b17bf`;
- exactly one semantic model invocation and one thread; and
- elapsed time 594.678 seconds, with zero web-search events and zero
  network-capable shell commands.

## Gold-free combiner compatibility defect

The first gold-free combination attempt produced no policy output and stopped
before private data access.  It rejected the actual receipt key
`__main__|tools/run_blind_pairwise_veto_agent.py`.  This key is produced when
the frozen runner is executed as a script, whereas the combiner's test fixture
had recorded the imported-module spelling
`tools.run_blind_pairwise_veto_agent|tools/run_blind_pairwise_veto_agent.py`.
The relative path and file SHA-256 were already exact.

Checkpoint `8ede80a` makes one compatibility change: `__main__` is accepted
only when paired with the exact relative path
`tools/run_blind_pairwise_veto_agent.py`, and that one pair is canonicalized to
the required runner module identity.  Absolute paths, parent traversal, any
other `__main__` path, missing required modules, and file-hash mismatch remain
rejected.  The existing exact file-hash and repository-containment checks are
unchanged.

This change does not alter certificates, candidate roles, switch eligibility,
the four policy definitions, the private cohort, metrics, promotion gates,
tie-breaking, runtime ceiling, or scientific interpretation.  Forty-three
focused pipeline tests passed before the combination retry.  The retry must use
the same accepted V7 receipt and a fresh empty output directory; only after its
self-hashed policy receipt is verified may the fixed private analysis run.
