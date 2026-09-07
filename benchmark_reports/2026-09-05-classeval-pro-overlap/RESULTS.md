# ClassEval-Pro source-overlap development — live, no superiority claim

## Current experiment

The complete author300-task inventory is running under frozen commit e61baa8,
using `tools/run_classeval_text_overlap.py` and protocol
`experiment_protocols/2026-09-05-classeval-text-overlap-v2.md`.
Root: `runs/classeval-pro300-text-overlap-20260905-development-v2`.
Session76151 / driver4043574 was confirmed live after launch. Do not restart
or modify its runner/operator/evaluator while active. This is DEVELOPMENT;
there is no completed300-task result or comparative accuracy claim yet.

Latest live checkpoint (13:36KST):65/300 completed, Plain41, best-of-two45,
all three original final systems60. Parent session76151/driver4043574 remains
live and unchanged. Full contrast-overlap replay is queued in session79651,
waiting for that exact parent and a complete result; it has NOT started.
The queue checks scientific files against c7e1ae2 before executing all300 at
`runs/classeval-pro300-contrast-overlap-20260905-full-v1`. Do not duplicate it
or edit queued scientific code. No new model calls are required for replay.

Later live checkpoint:23/300 completed, Plain14, adaptive best-of-two16,
both source-only policies16, all three repaired final systems23. Driver4043574
was directly confirmed live at elapsed19m55s. There are no final-system
discordances so far. This initial success rate is not a full-benchmark result.

Initial verified progress:4/300 completed, Plain3, best-of-two/source policies3,
all three repaired final systems4. The first task used two normal parents
(23.252/35.217seconds, each7/10 tests),14 actual mixtures per source policy,
and one shared ordinary repair. All three selected final sources are byte
identical; a separate fresh evaluation reproduced10/10/full pass. Selected
SHA256:9ac138dd60857eb5bbf8c42de03e3fb1b78079e4650d56593f788e336d422266.
This is a common repair rescue, NOT an overlap advantage. So far5 parent
calls and1 physical repair cover the4 completed tasks; live calls beyond
that checkpoint are not included in those counts.

Luna/medium returns complete code without tools, with the same120-second cap
for all calls. Every task receives A; every A failure receives B once. Three
systems share these parents: ordinary best-parent repair; random source
crossover plus repair; overlap-ranked crossover plus repair. Each receives
at most3 logical calls. Byte-identical repair prompts share one physical
result and incur one logical call for each consumer. Random and overlap
source searches have the same helper-union candidate space and16-program cap.
Only actually evaluated complete programs can pass; predicted test coverage
is not a solved problem. Full passing states remain unchanged.

All300 official tasks and unchanged tests remain in the denominator, including
the9 previously disclosed reference/runtime failures (reference291/300).
Source output, not the benchmark test or gold, receives a common one-line
method-signature instruction to avoid the author's line-based staticmethod
preprocessor misclassifying multiline instance methods.

## Closed feasibility campaigns (not full benchmark results)

| Run | Process termination | Completed tasks | Endpoint | Initiated calls | Completed receipts | Timeouts |
|---|---|---:|---|---:|---:|---:|
|Native sourcev2|session34880 exit130, deliberate stop|23/300|Plain10, generic13, overlap13|37|36|14|
|Code-outputv1|session11125 exit130, deliberate stop|3/300|Plain2, all repaired finals2|7|6|0|

Nativev2 produced zero actual composition trials: differing source inventories
and invalid parents prevented useful source search. It was stopped for
feasibility, not reported as a completed losing or winning300-task benchmark.
Completed receipts total3,764.157 agent seconds. Available normal-completion
usage totals1,502,288 input /79,366 output tokens; interrupted and timed-out
calls can lack final usage, so these are not complete cost totals.

Code-outputv1 produced normal valid text-only calls; its first A/B took
25.566/27.553 seconds. Both policies actually evaluated16 mixtures for the
first task, without a full solution. However, its multiline initializer was
misclassified by the unchanged author preprocessor. The same error affected
the shared general repair. All6 completed calls were valid normal executions;
their172.217 agent seconds and47,618 input /7,453 output tokens exclude the
interrupted seventh call. The3 completed tasks remain2/3 for every final
system. No rescore, answer reuse or selected task retry enters v2.

The earlier helper-union diagnostic is also only a frozen prefix:8/300,
generic4 versus overlap4. It exercised15 real mixtures for task0 without an
extra solution, and used no additional model calls. It is not confirmation.

## Scientific decision

These configuration/compatibility changes are feasibility work, NOT a paper
contribution or evidence of overlap superiority. The meaningful endpoint is
whether the complete overlap-containing final system beats both strong
repaired controls, with full denominators, disclosed realized compute,
appropriately adjusted paired analysis and fresh full-inventory repetitions.
Latest actual paper review remains v26 MAC final committee3/6; no new review
or4/6 claim follows from this experiment launch.

## Separate within-method structural experiment

Commit e6b16a8 freezes `tools/classeval_subtree_overlap.py`, recursively
aligning common ASTs and exposing binary choices inside unequal subtrees and
statement-list gaps. This can construct a correct method from two defective
methods in a unit example, unlike whole-method swapping. Both random and
overlap-ranked variants use the same14-slot bound and16-program cap. It is an
algorithmic hypothesis, not benchmark proof. All25 related tests pass.

No-model-call replay session69291 completedexit0 on its exact19-task completed
prefix snapshot (total benchmark300), at
`runs/classeval-pro300-subtree-overlap-20260905-diagnostic-v1`.
Both variants evaluate80 actual mixtures across that prefix; both solve14/19,
the same as the existing source-only result. No additional complete problem
is solved. Generic fine-grained selection drops ClassEval_11 partial coverage
from11 to10 passing cases versus the coarse generic selection. This variant
is not promoted to a new model-based experiment on these observations.

## Observed candidate complementarity, not a mathematical ceiling

At the23-task live checkpoint,7 tasks have two incomplete original parents:

| Task suffix | A passing cases | B passing cases | Observed union | Complete inventory |
|---|---:|---:|---:|---:|
|0|7|7|7|10|
|4|9|9|9|10|
|9|16|16|16|18|
|11|10|8|11|13|
|13|12|12|12|13|
|19|14|14|14|15|
|20|9|9|9|10|

Six pairs have identical passing-case sets; every pair shares at least one
failed case. This suggests limited observed donor complementarity in the
initial sample, not a theorem that composition cannot repair shared failures.
Common ordinary feedback repair solves all7 for every final system so far.
Increasing blind source search is not justified by the observed signal.
The next structural hypothesis should create genuinely complementary partial
implementations with shared interface constraints, instead of assuming two
identical-prompt draws provide them. No such new model campaign is launched.

## Bounded follow-up benchmark reading (not an experiment)

SciCode was inspected as a scientific-coding alternative with supplied
subproblem structure. The newer independent SciCode-Verified release contains
64 main problems/287 scored subproblems; its authors exclude one original
ill-posed problem. Any future use would retain this entire externally released
set and label it as the independent corrected benchmark, not a self-selected
64/65 subset or an unchanged upstream SciCode score. Its paired-environment
grading and long per-step timeouts require feasibility checks before calls.
No dataset download, installation, model invocation or adoption occurred.
Sources: https://github.com/flyingwagner/scicode-verified and
https://arxiv.org/abs/2608.04975 . The benchmark paper reports large changes
after defect correction; those are the authors' measurements, not ours.

Further read-only feasibility found the released grading HDF5 is1,108,078,257
bytes and the release manifest binds64 problems. Canonical grading uses two
scientific-Python environments and a1,800-second per-step cap. No files were
downloaded or environments installed. The size/requirements do not justify
interrupting the current run for immediate benchmark setup.

## Actual post-repair rescue and contrastive overlap ordering

Frozen d88315c adds a separate replay AFTER the shared ordinary repair, using
its best original A/B source plus the exact ordinary repair. It does not use
any other policy's repair or add model calls. Whole passing ordinary finals
remain immutable. Session96010 completedexit0 on a frozen47-task prefix:
ordinary44, random post-repair crossover45, old overlap post-repair45. This
is an actual code-composition rescue, not ranking superiority or full300 data.

The rescue is ClassEval_43, ClientAdaptiveFulfillmentNode. Original A passes
11/12 but stock_asset omits target_platform. The ordinary repair adds the
metadata but regresses fulfillment tracking (Rejected rather than Delivered),
also11/12. Both actual mixtures reach12/12; independent fresh reevaluation
reproduced ordinary11/12 and both mixtures12/12. The overlap mixture combines
the repair's stock_asset with original request_fulfillment and track_fulfillment.

| Actually re-evaluated source | SHA256 |
|---|---|
|Ordinary selected,11/12|91515637cc579b33fc9ec3eb650ca3ae80d9b3a17088755f1e46dcfe1704de44|
|Random post-repair,12/12|8bef37bdb598a3f81c22602cdde22e420cc3b381c7dfd803f71f0dc04a5beda0|
|Old overlap post-repair,12/12|00c2d422893acf988bc3b4198bdbcb456af5de350f8c3808df8ebbc52423f0b7|

Generic finds the rescue at trial12, old overlap at13. This motivated the new
contrastive ordering frozen c7e1ae2: intersect methods traced by the SAME test
that fails in an anchor but passes in the donor; prioritize the resulting
minimal transplant hypotheses, then fall back to existing overlap ordering.
The source space and16-program maximum are unchanged, and the generic policy
is unchanged. No task-ID-specific repair or new literal is introduced.

Session39728 completedexit0 on its exact58-task snapshot. The complete
predeclared verifier-budget curve is:

| Maximum new program trials | Ordinary | Random post-repair | Contrast-overlap |
|---|---:|---:|---:|
|1|54|54|55|
|2|54|54|55|
|4|54|54|55|
|8|54|54|55|
|16|54|55|55|

The same motivating task43 is found on the FIRST contrast-overlap trial,
versus12 for random crossover. The overlapping trace identifies
_parse_capabilities and stock_asset for transplantation. Fresh evaluation
again confirms12/12, and AST comparison confirms stock_asset comes from the
repair while request_fulfillment and track_fulfillment remain from original A.
SourceSHA8cbcb5be7f9a7b08b6b2293351057174701b63fbfd8e882b4cd070118d426156.
32 related tests pass. This is a ONE-CASE, exposed-development improvement in
search order. At the full16-trial cap both policies tie. It is not statistical
superiority, a20-percentage-point accuracy gain, or a new committee score.

Queued full300 replay will retain all tasks and all declared budgets. Any
positive development result still needs fresh matched full-inventory
replication before a strong paper claim. Latest final committee remains3/6.

## Diagnostic analysis and post-repair subtree follow-up — 2026-09-05

Commit ec914cf adds the full-inventory analyzer and freezes a separate
post-repair use of the existing within-method subtree operator. It does not
change the running text-v2 experiment or the scientific files of the queued
full contrast replay. The 36 focused tests passed before this report update.

`CONTRAST_DIAGNOSTIC_ANALYSIS.json` reconstructs every reported full pass from
the saved ordinary result or an actually executed mixture. On the 58-task
snapshot, the one discordant task gives conditional one-sided p=0.5; Holm
adjustment across both comparisons at all five declared budgets gives 1.0.
The analyzer rejects this prefix as a full benchmark unless the explicit
diagnostic flag is supplied. These are exposed-development statistics, not
fresh-session confirmation.

The three compared systems share 100 logical model calls on this snapshot,
with 2,809.839 seconds of recorded model duration, 811,243 input tokens and
119,770 output tokens. The parent campaign physically made 102 calls for
these tasks: two additional calls served other exploratory branches and are
not used by these derived systems. At cap 16, random recombination makes 28
actual new-program trials and contrast overlap makes 17. Trial-suite timings
are 1.355 and 0.820 seconds respectively, but exclude candidate-construction
and ranking overhead. This is not a total-latency or end-to-end efficiency
claim, and accuracy is tied at this cap.

Session 37353 completed the separately frozen post-repair subtree diagnostic
with exit 0 on the exact 94-task completed prefix, not a selected benchmark
subset. Ordinary repair and random subtree crossover solve 87 tasks;
overlap-ranked subtree crossover solves 88 at cap 16. The ONLY additional
solution is the same ClassEval_43. Overlap finds it at trial 13, while the
random fine-grained ordering does not find it within 16 trials. The simpler
whole-method random comparator already solves this task at trial 12 and the
primary contrast ordering at trial 1. Therefore this follow-up is neither
a second rescued problem nor an advantage over the strongest tested generic
comparator. It does not justify replacing the primary contrast method.
See `POSTREPAIR_SUBTREE_DIAGNOSTIC_ANALYSIS.json` for all five trial budgets.

The working manuscript-method draft is
`paper_revision/2026-09-01/working/contrast_overlap_method.md`. It explains the
actual overlap-guided transplantation rule, its shared-output comparison and
the motivating source-level repair. It is not a new submission version:
the manuscript, supplement, DOCX files and valid committee score remain v26
and Overall 3/6. Full-300 results and matched fresh repetitions are pending.

### Read-only opportunity check at the 112-task prefix

The live ordinary-repair result solves 105 of 112 completed tasks. Of the
seven unresolved tasks, 24 and 80 encounter the previously recorded empty
declared-test-class issue. Tasks 30, 51 and 69 have identical passing-case
sets before and after ordinary repair. Task 62 gains one passing test without
losing one, but still fails another. Task 43 is the sole observed unresolved
pair whose passing-case union exceeds the stronger parent's passing set:
11/12 plus 11/12 covers 12/12. Its executable rescue was already verified.

This is an opportunity diagnostic, not a compositional upper bound: mixtures
can in principle solve tests that neither parent passes, and case-set union
does not itself prove that any valid source mixture exists. The observed
scarcity of contrasting outcomes does not support increasing the trial cap
or presenting the finer operator as a breakthrough. Keep the frozen full-300
experiment and full contrast replay running unchanged before deciding the
next generation/repair design.
