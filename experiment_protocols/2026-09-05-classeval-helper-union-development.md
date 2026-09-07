# Separate helper-union source-space development

Motivation observed during the ongoing v2 development: the first valid A/B
pair has different class-method inventories, so BOTH frozen source policies
perform zero trials. This is not a reason to mutate or restart the live run.

New module tools/classeval_source_overlap_union.py broadens the source space
generically: retain each parent's existing methods and add methods defined
only by the other parent. Shared same-name methods and module context remain
the original binary source-choice slots. Constructor is a method. No gold
dependencies, task-specific fixes, field renames or synthesized method bodies.
Unresolved global-helper/field incompatibilities remain possible and must be
caught by actual execution; enrichment is not assumed behavior-preserving.

Compare generic random and overlap-ranked search on the SAME broadened space
with the SAME16 distinct-program evaluation cap and14 differing-slot bound.
The enriched corner states are NEW programs and consume evaluation budget;
never inherit their original parents' passing outcomes. Original whole-pass
parents remain available unchanged to both selectors. Only observed full
test passes score, never predicted support or toy-unit-test success.

No new model calls are required for this operator comparison: use the same
frozen A/B pool from the ongoing complete300 campaign. A one-task or completed
prefix replay is a diagnostic ONLY, not a full-benchmark accuracy result.
Any promoted development comparison must replay all300 tasks, including
non-composable/invalid/known benchmark-issue tasks, without selected retries.
Do not overwrite v2 outputs or silently choose the better source-space result.
The stronger ordinary-repair comparison and fresh replication still remain
necessary before architectural superiority or committee-goal completion.

The module is independently developed while original v2 executes; its hashes,
trial outcomes and provenance belong in a distinct diagnostic/replay root.
The original live runner, operator and evaluator are unchanged.
