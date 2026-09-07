# Common-subtree crossover: separate no-model-call development

Hypothesis: two incomplete programs can be complementary inside the same
method, where whole-method swapping cannot construct the joint repair.
Align same-name method ASTs recursively, retain identical subtrees as common
anchors, and make the unequal scalar/subtree/list gaps binary donor choices.
Sequence alignment preserves common ordered statements. Methods with too many
gaps are coarsened whole-method-first, largest reduction first, until the same
14-choice bound is met. More than14 differing methods remains non-composable;
the task stays in the benchmark denominator. No reference solution, test body,
hand-written answer, field rename, synthesized literal or model call enters
this operator. Partial parent source is not assumed semantically correct.

Compare random and overlap-ranked masks on the SAME fine-grained candidate
space, each at16 distinct syntactically valid program evaluations. Keep the
existing intact-parent baseline. Ranking uses the same observed passing-test
method traces: all choices inside a traced method must retain the supporting
donor for that case's conservative prediction. Context choice also remains
constrained. Co-executed/shared-field method relations break ties. Prediction
is a search heuristic only; never count it as a test pass. Preserve full
observed passes and rank remaining candidates by actual passing-case count.

Development uses a frozen snapshot of ALL currently completed tasks from
textv2, with the existing exact-prefix diagnostic flag. This is a diagnostic,
NOT a selected successful subset or completed benchmark. The ongoing textv2
runner/operator/evaluator and all its outputs remain unchanged. The new replay
uses the original isolated evaluator and no new model calls. Do not present
unit-test constructive examples as benchmark superiority.

If useful, evaluate this space on all300 fixed parents and then apply identical
ordinary feedback repair under matched per-system budgets. Neither a source
rescue nor a post-hoc replay alone is enough to claim final system superiority;
fresh full-inventory matched sessions remain necessary for promotion.
