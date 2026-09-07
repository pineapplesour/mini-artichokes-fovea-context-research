# Within-method subtree crossover AFTER ordinary feedback repair

This combines two already implemented structural choices without new model
calls: the frozen subtree operator e6b16a8 and the shared ordinary-repair
parent selection d88315c. It does not modify either algorithm, the original
textv2 execution, or the queued full300 contrast-overlap replay.

Observed motivation: the prior subtree diagnostic used initial A/B draws,
which had strongly correlated failures. A later actual post-repair rescue
established complementary correctness between pre-repair code and its repair.
In task30, only checkout_and_install differs between those parents, so the
whole-method space has no new program; the14-slot cap was NOT the obstruction.
Task51 has two differing methods. These observations motivate trying the
already-frozen finer operator at the later stage, not selected task retries.

Use ALL currently completed tasks as an exact frozen prefix diagnostic, with
the full benchmark denominator300 retained and diagnosticOnlytrue. No full
benchmark claim until all300 are evaluated. Preserve already passing ordinary
finals. On unresolved tasks, pair the best original A/B parent with the exact
ordinary repair. Both generic random and old subtree-overlap ranking receive
the same fine-grained candidate space and16-program maximum. Keep actual
official grading unchanged; predicted coverage is not a pass. No new model
calls, hand-written repairs, gold source, or task-specific rule enters this
experiment. This is development; report ties and losses as well as rescues.
