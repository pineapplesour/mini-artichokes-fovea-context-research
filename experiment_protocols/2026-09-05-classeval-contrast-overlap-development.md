# Contrastive test-method overlap ordering, v1 development

Motivation: a real post-repair crossover rescued ClassEval_43 (11/12 to12/12)
by preserving prior fulfillment behavior while adding the repair's asset
metadata fix. Both random and old overlap found it (12 and13 trials), so it
is NOT ranking superiority. That observation motivates this new algorithm;
it must remain exposed-track development, not confirmation.

Keep the frozen post-ordinary-repair history, helper-union candidate space,
14-choice bound, exact actual evaluator and16-program maximum. Generic random
ordering is byte-for-byte the existing policy. For overlap ordering, identify
the SAME test case that fails/errors in one parent but passes in the other.
Intersect the method names executed in those two runs, then retain only
methods whose actual implementations differ. Each such intersection yields
a donor-transplant hypothesis, first keeping anchor context, then donor
context. Also try individual methods for multi-method intersections. Order
witnesses by smallest intersection, case ID and anchor index. Fill remaining
candidate positions with the old conservative overlap ranking. Deduplicate
ASTs and exclude intact parents exactly as before. No synthesis, reference
implementation, new constant, case-specific rule or model call is added.

This is a hypothesis-ordering rule: a shared trace does not prove the fault
location, and a donor's passing result does not prove compositional validity.
Every accepted solution must actually pass the unchanged full test suite.
Never report predicted case coverage as correctness. Compare the entire
predeclared verifier-budget curve1,2,4,8,16, not a retrospectively chosen cap;
the main maximum remains16. Report all caps, including ties/losses, and adjust
any inferential family. Per-prefix development is diagnostic only. Final
claims require all300 and fresh paired full-inventory repetitions.

No changes to the currently executing textv2 generation/repair experiment or
its saved outputs. Use a separate replay root and record this protocol hash.
