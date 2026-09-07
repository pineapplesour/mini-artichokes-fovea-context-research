# Mini Artichokes: Verifier-Gated Recursive Portfolios for Test-Available Program Repair

## Abstract

Multiple LLM attempts can expose complementary program defects, but ordinary
ensembling can discard a verified solution or repeat a shared error. We study
**Mini Artichokes**, a recursive verified-redundancy procedure for
test-available program repair. Plain, requirement-Graph, and execution-feedback
candidates are evaluated task by task; every complete passing task state becomes
a byte-exact anchor; only common failures remain editable; and heterogeneous
direct and semantic-overlap routes are independently evaluated before their
passing states are promoted. The verifier, rather than a model vote or patch
intersection, is the only promotion authority.

On the initial three complete official Aider Polyglot tracks, Mini solves
**59/90** tasks, compared with 45/90 for ordinary execution-feedback repair and
15/90 for one-call Plain. The same frozen system reaches 33/39 on Go versus
25/39 and 17/39, and 47/49 on a clean before-call-frozen JavaScript track
versus 42/49 and 27/49. Across all five complete tracks, these systems solve
139/178, 112/178, and 59/178 tasks. On all 164 HumanEvalFixDocs Python tasks,
Mini improves on Plain (157/164) and reaches the same ceiling as ordinary
repair (164/164). These are bounded-call effectiveness results, not
fixed-resource efficiency claims.

As a secondary fairness sensitivity, a nominally equal-five-call
Direct-plus-Generic portfolio solves 132/178 Aider tasks versus Mini's 139/178,
with eight rescues and one harm. That comparison is mixed-stage; the only clean
prospective equal-call track, JavaScript49, is tied at 47/49. We therefore do
not use equal-call generic superiority as the paper's primary claim.

On the original common unresolved set, the overlap-aware route adds 10 verified
tasks above a 48-task floor, compared with 3 for each matched final control.
Recursive promotion preserves complementary Direct/TOV successes and produces
59/90 solutions across the original complete tracks. Newly frozen paired
sessions, however, show that the standalone overlap-route advantage varies by
trajectory. A one-task Java completion-lock result also does not repeat in five
new whole-track pairs. We therefore claim strong bounded-call system
effectiveness and deterministic preservation under explicit modularity and
verifier-stability assumptions, while treating semantic overlap as a useful
heterogeneous route rather than a universally superior final policy.

**Keywords:** large language models; program repair; semantic overlap;
verification; test-time compute; code agents

## 1 Introduction

LLM code agents commonly spend test-time compute on multiple attempts,
reflection, graph-structured reasoning, or a final verifier. These strategies
can improve over one-pass generation, yet their composition is fragile. A
critic may replace a task that another attempt already solved. A majority can
repeat a shared misconception. Conversely, requiring several patches to touch
the same lines can suppress complementary repairs that implement the same
behavior through different code.

This paper asks a systems question first: when a task-level external verifier
is available, can a repair agent preserve already demonstrated successes and
convert complementary route errors into additional verified successes? It then
asks the narrower component question of whether semantic relations among failed
hypotheses improve one final repair route. This separates three scientific
objects that are often conflated:

1. **candidate and anchor value:** whether multiple attempts collectively solve
   more tasks than a single attempt; and
2. **semantic-relation value:** whether comparing what failed candidates mean
   improves repair beyond a final agent with the same candidates, evidence,
   anchors, and budget; and
3. **recursive redundancy value:** whether verifier-backed promotion can turn
   complementary final-route crossovers into test-label-preserving system
   improvement.

Mini Artichokes first generates three complementary candidates. It then
constructs an execution-verified union: if any candidate passes a task's
complete official test command, all solution-file bytes for that task are
frozen. Only the common failure set remains editable. TOV represents each
remaining hypothesis through four behavioral fields--fault location,
invariant, counterexample, and edit intent. Convergence is supporting evidence;
disagreement specifies a claim to falsify. Literal edit-line intersection is
neither necessary nor sufficient. Because the semantic and direct routes later
exhibit large crossovers, the recursive variant evaluates both final outputs
and promotes every passing task into a second verified union. Its strongest
same-call comparator uses the identical `P/G/R` candidates and Direct route but
replaces TOV with a generic Critic; both portfolios therefore contain five
calls and the same promotion rule.

This design grew out of negative evidence. An earlier Java control required
two of three specification, implementation, and test views to agree before an
edit. It solved 5/20 tasks versus 7/20 for otherwise matched repair. The failure
suggested that overlap should guide tests, not authorize changes. A later
Java47 version also lost a Plain-passed task during manual patch transfer. TOV
v2 therefore makes verified preservation mechanical and makes semantic
disagreement actionable.

We ask three research questions in evidence order.

- **RQ1:** Does recursive verified redundancy improve Plain, Graph, and
  execution-feedback repair on complete official code tracks without selecting
  tasks?
- **RQ2:** Are direct and overlap-aware final routes complementary, and does
  verifier-only recursive promotion preserve their conditional successes?
- **RQ3:** Conditional on the same candidates and verified floor, what evidence
  isolates the incremental value and stability of semantic-relation guidance?

RQ1 and the preservation part of RQ2 define the primary system claim. RQ3 is a
secondary component analysis; acceptance of the system result does not require
TOV to be a uniformly superior standalone route.

Our contributions are:

- a verifier-gated composition rule that freezes complete passing task states,
  restricts further model action to the common unresolved set, and recursively
  promotes heterogeneous route successes without model voting or patch
  intersection;
- an overlap-aware TOV route that turns candidate agreement into supporting
  evidence and disagreement into a falsification target, plus matched generic
  and semantic-free controls that share candidates, anchors, evidence, calls,
  ledgers, and audit requirements;
- full-inventory system evidence on five official Aider tracks: Mini solves
  139/178, compared with 112/178 for ordinary repair and 59/178 for Plain,
  including before-call-frozen Go and JavaScript evaluations; and
- prospective complete-track and repeated-session analyses that establish the
  useful scope of verified route composition while explicitly bounding claims
  about standalone semantic-route superiority. Detailed chronology, failure
  cases, and robustness audits are preserved in the supplement.

The claim hierarchy is fixed as follows.

| Role | Claim | Evidence | Status in this paper |
|---|---|---|---|
| Primary | Test-label preservation under A1--A5 | Construction and byte audits | Structural property |
| Primary | End-to-end bounded-call effectiveness | 59/90 original; frozen Go 33/39; frozen JavaScript 47/49; complete HumanEvalFix extension | Supported in the reported test-available setting |
| Secondary sensitivity | Advantage over a same-call generic portfolio | Mixed-stage Aider 139/178 vs 132/178; clean JavaScript tie | Descriptive; not a primary superiority claim |
| Secondary component analysis | Standalone semantic-relation effect | Original 10-versus-3 matched-control result plus newly frozen paired sessions | Productive heterogeneous route; stable superiority not established |

The benchmark wrapper, hidden-test masking, and byte-restoration adapter are
experimental provenance, not contributions.

## 2 Related work

### 2.1 Feedback and intrinsic self-correction

Self-Refine alternates model-generated feedback and revision without additional
training [1]. Later work shows that intrinsic self-correction can fail when a
model cannot reliably identify its own mistake or accepts a false critique
[2,3]. Execution feedback changes this setting by providing an external
behavioral discrepancy, but a repair agent can still overfit a printed failure
or damage passing behavior. TOV uses execution evidence while restricting the
uncertain final edit surface to tasks not already verified.

Our ordinary-repair arm is a bounded execution-feedback realization in the
Self-Refine/Reflexion family, not a claim to reproduce every component of those
systems. It is important as a strong simple baseline: it raises accuracy from
the Graph candidate to 45/90 before any final adjudicator is used.

### 2.2 Candidate diversity, voting, and verification

Self-consistency selects a modal answer from multiple reasoning paths [4], and
multi-agent debate exchanges candidate arguments before selection [5]. Such
methods demonstrate the value of diversity but do not guarantee independent
errors. For code, executable tests can certify a candidate on the supplied
suite. Mini Artichokes exploits this asymmetry: a verified task becomes
test-label-preserved state, whereas failed candidates remain fallible evidence.

Best-of-multiple execution takes the highest-scoring complete candidate when a
verifier is available. Mini Artichokes instead operates on task-modular
whole-track states: it preserves different verified task states from different
routes, branches only the common failure set, and repeats that promotion after
heterogeneous final routes. This distinction matters only when A1--A5 hold; on
an indivisible task it reduces to ordinary verifier-selected best-of-multiple.

A generic Critic/Verifier can inspect the same candidates and failure traces.
We therefore do not use Plain as the only mechanism baseline. The verified-union
Critic shares every candidate, test outcome, anchor, model setting, and final
call with TOV. The stricter semantic-free control also shares TOV's decision
ledger, counterexample falsification, and two completion audits.

### 2.3 Structured reasoning and terminal agents

Graph of Thoughts organizes intermediate reasoning as a graph rather than a
single chain [6]. Our Graph candidate uses a compact requirement--invariant--
counterexample graph, but it is a prompt-level realization rather than a full
reproduction. KIRA emphasizes terminal-agent completion confirmation [7]; TOV's
two final audits are inspired by that general completion pattern. Neither graphs
nor auditing alone is claimed as novel. The experimental object is their
controlled composition with immutable verified anchors and semantic relations
among unresolved candidates.

### 2.4 Positioning

The closest interpretation is a recursively verified ensemble with a
relational repair branch. The novelty claim is not that multiple attempts,
testing, critics, graphs, or counterexamples are individually new. It is the
composition boundary: a complete verified task state is removed from model
discretion, only unresolved units are branched, and passing states from
heterogeneous routes are recursively promoted without patch intersection or an
LLM selector. Within one branch, candidate agreement and disagreement are
interpreted at the level of program obligations to choose what to falsify next.

Code-specific iterative methods are particularly close comparators.
AlphaCodium uses a test-based, multi-stage code-generation flow [8], while
Self-Debugging reuses failed programs with execution feedback and code
explanation [9]. These precedents mean that execution, repeated revision, and
retaining earlier work are not sufficient novelty claims. The narrower question
for semantic overlap is whether explicit relations among candidate assumptions
help a subsequent repair recover additional tasks beyond a strong generic
feedback-driven portfolio given the same candidate states and evidence.

Recent repair work also makes partial-solution composition a necessary
comparison. EvolRepair groups candidates by test-level behavior and uses
semantic recombination and mutation [10]. PatchFusion combines repeated edit
atoms within compatible repair scopes in a fixed candidate pool without using
test outcomes at decision time [11]. Our test-available setting instead uses
the external verifier to retain complete task states while separately testing
the value of semantic guidance for unresolved tasks. These settings distinguish
whole-task portfolio retention from within-task recombination and motivate
separate, resource-matched controls for the two operations.

## 3 Recursive Verified Redundancy with an Overlap-Aware Route

### 3.1 Setting

Let a complete benchmark track contain tasks `t=1,...,n`. Each task supplies an
official instruction, starter repository, allowed solution files, and a private
official test command. Models see the instruction and starter code but not test
source or gold implementation. After a call, the evaluator returns per-task
pass/fail and a bounded failure tail.

Three separate whole-track executions create candidate repositories:

- **Plain (`P`)** directly solves the starter tasks.
- **Graph (`G`)** first relates requirements, invariants, edge cases, and
  attempted counterexamples, then edits.
- **Ordinary repair (`R`)** starts from `G` and receives its bounded official
  failure output with a short instruction to fix failures and preserve passes.

Let `V_j(t)` be one when candidate `j` passes the complete official suite for
task `t`. The executions share a model and can have correlated errors; `R`
also explicitly depends on `G` and its feedback. No statistical independence
of candidate generation is assumed.

### 3.2 Deterministic verified union

For every task with `max_j V_j(t)=1`, the evaluator selects a passing candidate
under a frozen priority `R > G > P` and installs every listed solution file from
that candidate. Because all eligible candidates pass the full task suite, the
priority affects provenance, not the observed pass label. These bytes form the
anchor map `A`. The unresolved set is

\[
U = \{t : \max_j V_j(t)=0\}.
\]

Every final arm starts from the same union. After its model call, the experiment
restores all anchored bytes before evaluation. A final arm therefore cannot
exchange a known pass for a speculative repair. This test-label preservation is
shared by all final controls and cannot explain their differences.

### 3.3 TOV decision ledger

For each `t in U`, TOV writes one decision row containing:

1. candidate outcomes;
2. fault location;
3. violated requirement or invariant;
4. smallest counterexample class;
5. edit intent;
6. semantic agreements and disagreements among candidates, specification, and
   failure evidence;
7. a falsification attempt; and
8. selected evidence and final action.

The semantic comparison is behavioral. Two patches overlap when they target
the same unmet obligation, even if their edited lines differ. Agreement raises
confidence but does not authorize an edit automatically. Disagreement creates a
specific falsification burden. TOV must try to refute the leading hypothesis,
then synthesize the smallest general repair supported by the surviving
evidence. A requirement-to-diff audit and a separate completion/falsification
audit follow all repairs. The ledger must have exactly `|U|` unique task rows.

**Completion-locked TOV.** Two later full-track failures showed that a
semantically plausible repair can still leave a literal verifier obligation
open: one JavaScript repair repeated a shared sign misconception, and one Go
repair satisfied the function semantics but retained a compiler-visible unused
import. The revised final gate therefore enumerates every observed compiler,
runtime, assertion, expected/actual, timeout, and scope failure atom. Every atom
must map one-to-one to a concrete construct in the final solution file that
prevents recurrence. The agent reopens the actual final file after repair; any
atom without a present closure witness forces continued repair. Semantic
overlap remains a hypothesis generator, while literal verifier closure is the
last mandatory gate. This revision was developed on the completed JavaScript
and Go tracks, then frozen without change for Java164.

### 3.4 Controls

The **generic verified-union Critic** receives the identical original tasks,
candidate patches, per-task outcomes, bounded traces, union, anchors, model,
effort, final-call cap, and output cap. It is told to inspect all evidence and
fix unresolved tasks, but it has no required ledger or audit schema.

The **semantic-free structured control** is stricter. It uses the same ledger
fields, counterexample-based falsification, and two audits as TOV. Its semantic
relation field must be the constant `withheld-by-control`, and it is explicitly
prohibited from treating candidate convergence or disagreement as confidence,
routing, or authorization evidence. This natural-language ablation cannot make
latent model trajectories identical, but it holds the named structured
operations fixed while removing the proposed relational instruction.

Each single-final-route ablation uses four semantic calls: the shared `P/G/R`
candidates and one final adjudicator. The recursive system uses five by adding
both TOV and Direct. Running both four-call research alternatives does not add
calls to either ablation; promoting both together defines the distinct
five-call system. Realized tokens and latency can differ despite equal calls
and caps.

**Operational contract.** The exact frozen instruction strings are the
`GRAPH_LEAD`, `ORDINARY_REPAIR`, `GENERIC_VERIFIED_UNION`,
`SEMANTIC_OVERLAP_VERIFIED_UNION`, and
`SEMANTIC_FREE_STRUCTURED_VERIFIED_UNION` constants in the released runner;
the Java case study additionally freezes
`COMPLETION_LOCKED_SEMANTIC_OVERLAP_VERIFIED_UNION`;
their prompt hashes are stored per call. TOV and Direct must write parseable
`/tmp/artifacts/decision_ledger.json` with exactly one record for each frozen
unresolved task ID. Required fields are the eight items in Section 3.3; Direct
must place the literal `withheld-by-control` in its relation field. Integrity
checks validate parseability, task-ID set and order, row count, anchor bytes,
and changed paths. They do not score the natural-language diagnoses for
semantic correctness. Missing ledgers, wrong IDs, forbidden paths, or
agent-incomplete calls fail the strict protocol gate; task scoring still uses
the unmodified official verifier under intention-to-treat. Supplementary
Sections S13--S22 reproduce the contracts, hashes, and deviations.

### 3.5 Recursive dual-route promotion

The repeated studies reveal that TOV and the semantic-free structured route
often solve different unresolved tasks. In the explicitly test-available
setting, their complementarity can be stabilized without an LLM vote. Both
routes start from the same anchor map; the official evaluator tests each final
workspace; and for every task passed by either route, the complete passing
solution-file bytes are promoted into a second anchor map. If both pass, a
fixed direct-route-first priority determines provenance only. All original
anchors are restored before this promotion.

The complete **Mini Artichokes** system uses five calls: `P/G/R`, TOV, and the direct
structured route. Its equal-call non-overlap control uses `P/G/R`, the generic
Critic, and the same direct route. Thus the two five-call systems share four
calls and differ only in overlap-aware versus generic final repair. Recursive
verification preserves every observed pass from either included route on the
supplied official suites; it does not guarantee correctness beyond those tests.
The construction was formulated after final-route crossovers were observed and
is analyzed as exploratory in the first three tracks, then evaluated under a
before-call freeze on Go39.

Mini is an **online verified portfolio**, not an offline best-of-independent
outputs. Verification is inserted between generation stages: `P/G/R` outcomes
create the immutable floor supplied to both final routes, solved tasks are
removed from their editable set, bounded failure evidence is rebuilt only for
the remainder, and anchor bytes are restored before each evaluation. Terminal
promotion itself is deliberately simple--a task-wise verifier union--but the
generate--verify--freeze--branch--promote sequence changes the inputs and
allowed actions of later model calls. The systems contribution is this enforced
composition and its fail-closed preservation contract, not a learned selector
or a model vote.

### 3.6 Applicability contract and preservation property

The preservation claim requires a narrow contract. (A1) The benchmark is
partitioned into task units whose declared solution files and verifier do not
cross task boundaries. (A2) Each route is evaluated in an isolated workspace
by the same fixed task-level verifier. (A3) Promotion copies the complete
allowlisted solution-file tuple for a task, never an intersection or line-wise
merge. (A4) Previously anchored bytes are restored before every evaluation.
(A5) A missing file, forbidden-path change, verifier error, or non-pass fails
closed: it cannot replace an anchor. If multiple new routes pass, a frozen
priority chooses one complete state only for provenance.

**Test-label preservation property.** Under A1--A5, let `S_k` be the set of
tasks observed passing in included route `k`, and let `A` be the prior anchor
set. The recursively promoted output passes every task in
`A union (union_k S_k)` under the same verifier invocation used for promotion.
For each task, the construction copies either its prior anchored state or one
complete state already observed to pass; no unverified merged state is
created. Hence its observed task score is at least that of the prior anchor set
and each included route after anchor restoration. This is a property of the
promotion rule, not a claim of semantic correctness, verifier completeness,
or reliability under nondeterministic tests.

### 3.7 Outcome decomposition

For any final route `F`, define `V_F(t)=1` exactly when the post-restoration
workspace for task `t` passes its complete official verifier, and zero
otherwise. Deterministic promotion is not another model call. If routes `F`
and `D` are included, their recursive output has task indicator
`V_rec(t)=max(V_F(t),V_D(t))` under A1--A5. Because final arms share immutable
anchors, their accuracy decomposes as

\[
\operatorname{Acc}(F) = \frac{|A| + \sum_{t\in U} V_F(t)}{n}.
\]

For two final policies `F` and `C`, the full-denominator difference is

\[
\Delta(F,C)=\frac{r-h}{n},
\]

where `r` is the number of unresolved tasks solved only by `F` and `h` the
number solved only by `C`. Anchors cancel exactly. We report both the
full-denominator difference and the descriptive resolution rate on the common,
pre-final unresolved set. In this study `|A|=48` and `|U|=42`.

### 3.8 Expectation-aligned overlap of failed obligations

A failed requirement can be shared even when candidates produce different
wrong outputs. Comparing complete error strings can conceal this relation:
the required message may be identical while one candidate emits one incorrect
message and another emits a different one. We therefore test an observation
layer that separates a recognized displayed expectation from the observed
wrong result, then groups identical expectation fields and parsing forms within
each task. Every case identifier, candidate label, and distinct wrong observation
is retained. Same-case support across Plain and the Graph/repair lineage is
explicit; Graph and its repair are not counted as independent votes.

The repair agent uses these groups as obligations to check against the actual
source and original specification. A group does not prove a common root cause,
and exact displayed-expectation identity is not a general semantic-equivalence
test. Ambiguous or unrecognized diagnostics remain unparsed. The external
full-task verifier still decides whether the resulting complete program passes.

The matched control receives the same expected/observed parsing, raw feedback,
candidate sources, and repair instruction, but retains case-local organization.
Thus additional oracle information, a different repair prompt, and normalization
itself are not unique to the overlap arm. The tested component is explicit
cross-observation alignment. It adds no model call and does not perform a
task-specific source edit. Supplement S25 gives the development chronology and
information-equivalence checks; Section 5.10 reports the completed comparison.

## 4 Experimental design

### 4.1 Complete official tracks

We use `Aider-AI/polyglot-benchmark` commit
`7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f` [12]. The evaluation retains all 30
official Rust tasks, all 34 Python tasks, and all 26 C++ tasks. No task is
ranked, screened, removed, replaced, or topped up. Starter repositories pass
0/30, 0/34, and 0/26 complete official commands.

After the recursive rule was fixed, we added a previously untouched fourth
complete track containing all 39 official Go tasks in alphabetical order. Its
starter passes 3/39. The Go model workspace contains no `*_test.go` files,
whereas the private evaluator restores 61 official test files. One official
`counter` task reports `no tests to run`; it is retained in the denominator
rather than removed after inspection.

We subsequently froze the same six-arm design on the last untouched complete
Aider language track, all 49 JavaScript tasks. The starter passes 1/49. Each
model workspace excludes the declared official test file, and the evaluator
restores all 49. An evaluator smoke test initially lacked the shared dependency
path; it occurred before any scored call, was invalidated, and the corrected
environment was re-frozen before the six calls.

To test a different official benchmark family, we use all 164 Python tasks in
BigCode HumanEvalPack's `HumanEvalFixDocs` configuration [13,14], pinned at
dataset revision `9a41762f73a8cb23bb5811b73d5aab164efcf378`. The model sees each
buggy implementation and docstring but not the canonical solution or official
tests. The evaluator runs every supplied test. The starter passes 0/164. No
task in either new track is ranked, screened, removed, replaced, or topped up.

Robustness analyses additionally retain all 164 HumanEvalFixDocs Java tasks in
five newly frozen session pairs, all 164 C++ translations, and all 40 QuixBugs
Python programs at commit `4257f44b0ff1181dedaedee6a447e133219fcebf`
[15]. These experiments test route stability, language transfer, and a distinct
task family; they are not pooled into the primary Aider endpoint. Complete
runtime, task-visibility, and protocol details appear in Supplement S22--S24.

Gold `.meta/example.*` files and configured or conventional test files are
removed from model workspaces. The private evaluator restores untouched tests
and counts a task correct only when its full suite passes. Failure tails are
bounded and may reveal compiler or assertion output, but never test source or
gold code. This is a test-available repair setting, not a one-shot Aider
leaderboard submission or ordinary local development.

### 4.2 Model and call budget

In this paper, a "call" counts one complete Codex agent execution, which can
contain multiple model/tool turns; it is not one API completion. Every core
coding execution uses `gpt-5.6-luna` at medium reasoning and processes the
complete language track; there are no per-task model calls,
retries, or top-ups. Agent and evaluator caps are 30 minutes. Web, retrieval,
plugins, memories, and multi-agent delegation are disabled. Candidate
workspaces are isolated from private tests.

The evaluated arms are:

| Arm | Calls in system | Distinguishing operation |
|---|---:|---|
| Plain | 1 | Direct complete-track solve |
| Graph | 1 | Requirement/invariant/counterexample graph, then edit |
| Ordinary repair | 2 | Graph plus one generic execution-feedback repair |
| Verified union | 3 | Deterministic task-wise union of passing `P/G/R` files |
| Generic Critic | 4 | Verified union plus generic final repair |
| Semantic-free structured | 4 | Union plus TOV ledger/falsification/audits, relations withheld |
| **TOV v2** | **4** | Union plus semantic relations, disagreement falsification, and audits |
| Non-overlap dual-route union | 5 | Recursive verified union of generic and semantic-free final routes |
| **Mini Artichokes** | **5** | Recursive verified union of TOV and semantic-free direct routes |

These labels denote bounded prompt realizations. The supplement reports a
separate official LEET development screen for Self-Consistency, Tree of
Thoughts, Reflexion, Self-Refine, Critic/Verifier Separation,
Skeleton-of-Thought, and Graph. That screen is not pooled with code results.

The call column counts whole-track **model invocations**. Plain and Graph use
one each; ordinary repair reuses Graph and adds one; each four-call route reuses
`P/G/R` and adds one; each five-call portfolio reuses `P/G/R` and adds two.
Byte restoration, task-wise promotion, and official evaluation are
deterministic external operations and add no model call, but they do add test
execution and wall-clock cost. Therefore five-versus-two results measure
effectiveness under the stated call cap, while the two five-call portfolios are
the nominal-call-matched comparison. Neither comparison is token-matched.

The primary estimand is the accuracy of each complete policy at its declared
whole-track call budget. Candidate generation, verification, anchoring, and two
final routes are intentionally treated as one deployed system; the primary
comparison does not attribute its gain to any single component. Matched
four-call route ablations and five-call portfolio sensitivities answer the
separate component and allocation questions. This distinction makes additional
calls part of the primary treatment rather than an unreported confound, while
leaving efficiency and fixed-token dominance outside the claim.

### 4.3 Freeze chronology

Evidence stages are kept separate. Rust30 developed TOV v2; the policy was
then frozen for Python34 and extended unchanged to C++26. The stricter
semantic-free control and recursive dual-route analysis were specified after
the original outcomes and are secondary. Ten later whole-track pairs, five on
Python34 and five on C++26, exclude the motivating calls and directly sample
session variation.

Go39, JavaScript49, and HumanEvalFixDocs Python164 each used a protocol frozen
before their scored model calls. Go's original Generic endpoint was
agent-incomplete after provider errors; its separately authorized replacement
is sensitivity-only. JavaScript49 completed cleanly. HumanEvalFix used Python
3.13.11 rather than the protocol's anticipated 3.13.5 and is retained as a
complete-suite ceiling/portability evaluation.

The later Java, C++, and QuixBugs studies test revised failure-closure rules and
do not redefine the primary system claim. The motivating Java pair is excluded
from five new replication pairs; C++ reuses the underlying HumanEval tasks;
and QuixBugs has a recorded integrity-glob deviation. Supplement S1 and
S13--S24 preserve the full chronology, frozen hashes, deviations, and
intention-to-treat decisions.

### 4.4 Statistical analysis

For every paired contrast we report full-denominator accuracy, rescues, harms,
percentage-point difference, and exact one- and two-sided binomial/McNemar tests
on discordant tasks. A 50,000-draw paired bootstrap resamples within track with
seed 20260902.

All task rows within one arm share one whole-track model call. Task-level tests
therefore condition on realized calls and are not session- or
language-population inference. Track signs and the five-pair studies use the
whole track/session as the unit; their exact sign tests and 100,000-draw session
bootstraps are reported alongside task-conditional estimates. Nested
five-versus-one/two-call comparisons measure bounded-call effectiveness, not
efficiency. The two five-call portfolios match nominal calls and caps but not
realized tokens or time.

The 139/178 Aider comparison sums all stored complete-track vectors without
task removal or new model calls. It is explicitly mixed-stage: the original
three-track union is post hoc, Go uses a replacement sensitivity, and
JavaScript is prospective. We therefore report both task discordance and five
track signs and do not label the aggregate a preregistered endpoint. Detailed
seeds, effect gates, and per-study decision rules are in Supplement S1.

## 5 Results

Read the evidence in three layers. Sections 5.1 and 5.3--5.5 report end-to-end
system effectiveness; the original 90-task construction is exploratory and the
Go39, JavaScript49, and HumanEvalFix rules were frozen before calls. Sections
5.6--5.7 report compact robustness boundaries for the component claim. The
five-track equal-call summary is mixed-stage: its original contrast is
exploratory, Go is sensitivity-only, and JavaScript supplies a clean
prospective tie. HumanEvalFix Python supplies a ceiling tie.
Section 5.2 isolates TOV as a component and does not establish repeatable
session-level superiority.

### 5.1 Full-denominator performance

Table 1 reports all 90 official tasks. Mini Artichokes solves 59/90 (65.6%),
compared with 15/90 (16.7%) for Plain, 21/90 (23.3%) for Graph, 45/90 (50.0%)
for ordinary repair, and 48/90 (53.3%) for the deterministic verified floor.
Its TOV branch alone reaches 58/90 (64.4%); each single final control reaches
51/90 (56.7%). The equal-call non-overlap dual-route union scores 54/90
(60.0%).

**Table 1. Complete official Aider tracks; no task selection.**

| Track | Plain | Graph | Ordinary | Verified floor | Generic | Direct | TOV | Non-overlap dual | **Mini Artichokes** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Rust30 | 5 | 8 | 15 | 16 | 16 | 19 | 18 | 19 | **19** |
| Python34 | 6 | 5 | 17 | 19 | 21 | 19 | 23 | 21 | **23** |
| C++26 | 4 | 8 | 13 | 13 | 14 | 13 | 17 | 14 | **17** |
| **All90** | **15** | **21** | **45** | **48** | **51** | **51** | **58** | **54** | **59** |

Relative to Plain, Mini Artichokes adds 44 tasks and loses none (+48.9
percentage points; conditional task-level one-sided `p=5.68e-14`). Relative to
ordinary repair, it adds 14 and loses none (+15.6 points; `p=6.10e-5`). These
are effectiveness comparisons between nested one-, two-, and five-call
systems, not efficiency or overlap-only estimates. Candidate diversity,
external execution, the verified floor, and both final routes contribute.

TOV also improves ordinary execution-feedback repair by 13 tasks with no harms:
+14.4 points, `p=.000122`, bootstrap `[+7.8,+22.2]`. The gain is positive on
all tracks (+3 Rust, +6 Python, +4 C++).

At equal five-call count, Mini Artichokes has five rescues and no harms
against the non-overlap dual-route union: 59/90 versus 54/90, +5.56 points,
one-sided exact `p=.03125`, two-sided `p=.0625`, and within-track bootstrap
`[+1.11,+10.00]` points. The five unique tasks are Python `forth` and
`go-counting`, and C++ `complex-numbers`, `robot-name`, and `yacht`. Track
differences `[0,+2,+3]` give a sign value of `.25` over two nonzero tracks.
Because recursive union was chosen after observing crossovers, this is a
post-hoc equal-call system contrast, not confirmatory mechanism evidence.

### 5.2 Route complementarity and repeated-session stability

The three initial candidates verify 48/90 tasks, leaving the same 42-task
unresolved set for every final route. Generic and semantic-free structured
repair each add 3 tasks; TOV adds 10. Against the stricter control, TOV is
58/90 versus 51/90 with eight rescues and one harm (one-sided exact
`p=.01953125`; bootstrap `[+2.22,+14.44]` points). This result is secondary
because the stricter control was designed after the original outcomes.

Ten newly frozen whole-track pairs show why the system retains both routes.
TOV's mean final-route difference is +1.2/34 on Python and +0.4/26 on C++, but
both session intervals include help and harm. Recursive verifier promotion
converts those crossovers into 210/300 task-session passes, compared with 198
for TOV alone and 190 for the semantic-free route (Table 2). It exceeds TOV in
six sessions and ties in four. This is descriptive evidence of complementary
successes: the union cannot score below either constituent on the same stable
test labels, so a sign test against a constituent is not evidence of architectural
superiority. The relevant scientific comparison is an equally budgeted generic
portfolio with the same preservation rule.

**Table 2. Final-route performance and recursive promotion.**

| Evidence block | Semantic-free route | TOV route | Recursive union | Interpretation |
|:---|---:|---:|---:|:---|
| Original complete tracks | 51/90 | 58/90 | **59/90** | Secondary 8:1 TOV-control discordance |
| Python34, five sessions | 107/170 | 113/170 | **118/170** | TOV-control mean +1.2/34 |
| C++26, five sessions | 83/130 | 85/130 | **92/130** | TOV-control mean +0.4/26 |
| **Repeated sessions combined** | **190/300** | **198/300** | **210/300** | **Union exceeds either route** |

The discordant repairs concentrate in interface-heavy tasks, but the same task
can cross between routes across sessions. We therefore use candidate relations
to generate falsifiable hypotheses, not to select a winner without execution.
Per-task cases, paired differences, intervals, and all retained protocol
deviations are reported in Supplement S13--S17.

### 5.3 Frozen complete-track Go39 evaluation

Table 3 reports the new track. Every arm processes the complete 39-task batch
in one call. The 26-task candidate union is immutable for the three final
routes. TOV resolves six of the 13 remaining tasks, compared with three for
Direct and three for the valid Generic replacement. Mini Artichokes
retains seven complementary final-route additions and reaches 33/39, the
highest observed score.

**Table 3. Complete official Go39 results; no task selection.**

| Plain | Graph | Ordinary | Verified floor | Direct | Generic* | TOV | Non-overlap dual* | **Mini Artichokes** |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 17 | 16 | 25 | 26 | 29 | 29 | 32 | 31 | **33** |

`*` The preregistered Generic invocation was transport-null, so Generic and
non-overlap values come from a separately frozen same-input replacement
sensitivity after TOV outcomes were known.

Relative to Plain, Mini Artichokes gains 16/39 (+41.03 points; 16 rescues, no
harms; one-sided `p=1.526e-5`; bootstrap `[+25.64,+56.41]`). Relative to
ordinary repair it gains 8/39 (+20.51 points; 8:0; `p=.003906`; bootstrap
`[+7.69,+33.33]`). These are large but nested system comparisons with
additional calls. They establish end-to-end value, not an overlap-only effect.

The tighter same-anchor comparisons are positive but smaller. TOV scores
32/39 versus 29/39 for Direct (four rescues, one harm; +7.69 points,
`p=.1875`) and 29/39 for replacement Generic (also 4:1, `p=.1875`). The
equal-five-call replacement sensitivity is 33/39 versus 31/39: TOV union
rescues `bottle-song`, `poker`, and `two-bucket`, loses `react`, and yields
+2/39 (+5.13 points; `p=.3125`; bootstrap `[-5.13,+15.38]`). It fails both
the `.05` directional gate and the separately named +8/39 strong-effect gate.

All valid Go calls were agent-complete and safe. Direct, replacement Generic,
and TOV received byte-identical seed, anchor map, candidate patches, and
bounded failure evidence; 78/78 route-by-anchor file comparisons were exact.
Direct and TOV ledgers contained the exact 13 unresolved IDs in frozen order,
and all Direct relation fields were `withheld-by-control`. TOV used more
realized compute than Generic, so the systems are call-matched but not
token-matched. Full task IDs, hashes, transport events, compute, and intervals
are reported in Supplementary Section S18.

Because `counter` has no active tests, we also treat it as unverified and
exclude it from every arm in a prespecified-after-review sensitivity. Scores
then become Mini 32/38, non-overlap 30/38, TOV 31/38, Direct and Generic 28/38,
ordinary 24/38, and Plain 16/38. All rescue:harm counts and exact tests are
unchanged; Mini is +42.11 points over Plain, +21.05 over ordinary, and +5.26
over the equal-call sensitivity system. The row inflates absolute scores but
does not create a between-arm gain.

Across the five complete official Aider tracks, the descriptive cumulative
system counts and the equal-call portfolio sensitivity are shown in Table 4.
This aggregation combines development, prospective, extension, and
sensitivity stages, so it summarizes coverage rather than defining a new
confirmatory trial. The starred Go cells use only the separately identified
model-complete replacement, never the transport-null arm.

**Table 4. Descriptive five-track Aider coverage; all 178 official tasks retained.**

| System or route | Original90 | Go39 | JavaScript49 | All178 |
|---|---:|---:|---:|---:|
| Plain | 15 | 17 | 27 | 59/178 (33.1%) |
| Graph | 21 | 16 | 27 | 64/178 (36.0%) |
| Ordinary repair | 45 | 25 | 42 | 112/178 (62.9%) |
| Verified floor | 48 | 26 | 42 | 116/178 (65.2%) |
| Direct final route | 51 | 29 | 45 | 125/178 (70.2%) |
| Generic final route* | 51 | 29 | 47 | 127/178 (71.3%) |
| TOV final route | 58 | 32 | 47 | 137/178 (77.0%) |
| Direct∪Generic* | 54 | 31 | 47 | 132/178 (74.2%) |
| **Mini Artichokes** | **59** | **33** | **47** | **139/178 (78.1%)** |

Against the five-call Direct∪Generic portfolio, Mini has eight task rescues
and one harm, +7/178 (+3.93 points), conditional one-sided exact `p=.01953`,
two-sided `p=.03906`, and paired bootstrap `[+1.12,+7.30]` points. Its
track-level net differences are Rust 0, Python +2, C++ +3, Go +2, and
JavaScript 0: positive on three tracks and tied on two, with one-sided sign
`p=.125` over the nonzero tracks. This is the fairest available same-call
inventory comparison, but it remains mixed-stage and not token-matched. In
particular, JavaScript is the only clean prospective equal-call track and is a
tie. The result therefore supports a bounded realized-portfolio advantage, not
a prospective population or overlap-causal claim.

### 5.4 Before-call-frozen complete JavaScript49 evaluation

All six preregistered calls completed without retry or replacement. The
42-task `P/G/R` candidate floor was immutable for Direct, Generic, and TOV.
Direct solved 45/49; both Generic and TOV solved the same 47/49 tasks, and both
materialized five-call unions consequently scored 47/49.

**Table 5. Complete official JavaScript49 results; no task selection.**

| Plain | Graph | Ordinary | Verified floor | Direct | Generic | TOV | Direct∪Generic | **Mini Artichokes** |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 27 | 27 | 42 | 42 | 45 | 47 | 47 | **47** | **47** |

Mini gains 20/49 over Plain (+40.82 points; 20:0; one-sided
`p=9.537e-7`; bootstrap `[+26.53,+55.10]`) and 5/49 over ordinary
repair (+10.20 points; 5:0; `p=.03125`; bootstrap `[+2.04,+18.37]`).
The five latter rescues are `beer-song`, `food-chain`, `go-counting`,
`killer-sudoku-helper`, and `twelve-days`. The +10/49 preregistered strong
gate is met against Plain but not ordinary repair.

For the primary overlap-specific comparison, Mini and Direct∪Generic are an
exact tie: 0 rescues, 0 harms, `p=1`, interval `[0,0]`. TOV and Generic also
have identical task vectors. This clean prospective result strengthens the
system-level effectiveness evidence while directly rejecting a claim that the
overlap route was superior on this track. All 126 route-by-anchor byte checks
passed, and the final routes received byte-identical evidence.

### 5.5 Independent HumanEvalFix Python164 ceiling evaluation

On all 164 official BigCode HumanEvalFixDocs Python tasks, Plain solves
157/164 and Graph 154/164. One execution-feedback repair call raises Graph to
164/164, so the candidate union and every final route remain at 164/164.

**Table 6. Complete HumanEvalFixDocs Python164 results.**

| Plain | Graph | Ordinary | Verified floor | Direct | Generic | TOV | Direct∪Generic | **Mini Artichokes** |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 157 | 154 | **164** | **164** | **164** | **164** | **164** | **164** | **164** |

Mini gains 7/164 over Plain (+4.27 points; 7:0; one-sided `p=.0078125`;
bootstrap `[+1.22,+7.32]`) but zero over ordinary repair. It does not meet the
+33/164 strong-effect gate. The result transfers verified preservation to a
second benchmark family but is a ceiling boundary for both recursive
branching and overlap attribution. The actual freeze and evaluator used Python
3.13.11 rather than the protocol's predeclared 3.13.5; the runtime-version
deviation makes this a ceiling/portability evaluation, not a strict
protocol-confirming endpoint. All twelve calls across JavaScript and
HumanEvalFix were nevertheless agent-complete and safe. HumanEvalFix had 492/492 exact
route-by-anchor byte checks and byte-identical final-route evidence.

### 5.6 HumanEvalFix Java164 completion-lock result and replication

The Java protocol retained all 164 official tasks and froze completion locking
before the motivating calls. Plain scores 147/164, ordinary repair 162/164,
and the verified floor 163/164. The initial Completion-Locked TOV route repaired
the sole residual task and produced the canonical 164/164 solution, whereas
Generic remained at 163/164. Five new predeclared whole-track pairs did not
repeat that difference: candidate-minus-Generic scores were `[0,0,-1,-1,0]`
(no wins, two losses, three ties; one-sided sign `p=1.0`). The initial rescue is
therefore retained as an exact mechanism case, not promoted to a stable
superiority claim. The complete pair table, task outcomes, and realized costs
are reported in Supplement S23.

### 5.7 Complete-suite transfer boundaries

Two further complete-suite checks bound that component conclusion without
changing the primary Aider system result. On all 164 HumanEvalFixDocs C++
translations, Direct and Generic reach 164/164, the revised overlap route
reaches 163/164, and both five-call unions reach 164/164 because they share
Direct. On the semantically independent 40-program QuixBugs hidden-test
variant, Direct, Generic, and an executable source-bound closure route all
reach 40/40 from a 39-task floor. These are language-transfer and ceiling
diagnostics, respectively, rather than evidence against verifier-gated
recursive promotion. Full route tables, compute, ledger audits, and the
QuixBugs allowlist deviation appear in Supplement S24.

### 5.8 Integrity and compute

There were 16/19/13 anchored tasks and 32/19/26 anchored files in
Rust/Python/C++. Every final workspace matched its selected anchor bytes. TOV
and both controls received byte-identical candidate patches, per-task outcomes,
bounded traces, evidence index, and anchor map. TOV and the stricter control
produced exactly 14/15/13 ledger rows, equal to unresolved counts. Every
semantic-free relation field was `withheld-by-control`; forbidden changed paths
were zero.

**Table 7. Realized original final-call cost.**

| Final arm | Input tokens | Cached input | Output tokens | Seconds |
|---|---:|---:|---:|---:|
| Generic Critic | 5,438,878 | 5,136,896 | 48,179 | 1,233.6 |
| Semantic-free structured | 7,060,198 | 6,728,448 | 54,728 | 1,392.7 |
| TOV | 6,608,440 | 6,232,576 | 59,551 | 1,422.3 |

Calls and caps are matched, but tokens and latency are not exact. TOV uses
fewer input and more output tokens than the stricter control and takes 29.6
more seconds in aggregate. No efficiency or monetary-cost dominance is claimed.
The four-call system is intended for quality-sensitive repair, not cheap
default completion.

**Table 8. Realized cost of the three earlier five-call system comparisons.**

| Track and system | Input | Cached input | Output | Reasoning output | Agent s |
|:---|---:|---:|---:|---:|---:|
| JavaScript Direct∪Generic | 7,537,226 | 7,085,568 | 82,649 | 14,372 | 1,825.3 |
| JavaScript Direct∪TOV | 7,864,718 | 7,402,240 | 86,300 | 14,875 | 1,892.9 |
| HumanEvalFix Direct∪Generic | 3,002,483 | 2,748,160 | 42,913 | 11,079 | 1,005.3 |
| HumanEvalFix Direct∪TOV | 2,797,351 | 2,567,168 | 42,483 | 10,730 | 987.1 |
| Java164 Direct∪Generic | 10,560,445 | 10,073,344 | 92,793 | 26,154 | 2,778.2 |
| Java164 Direct∪completion-locked TOV | 10,577,460 | 10,097,920 | 94,103 | 25,773 | 2,771.5 |

The TOV system uses 4.35% more input tokens and 3.70% more time on JavaScript,
but 6.83% fewer input tokens and 1.82% less time at the HumanEvalFix ceiling.
This reversal reinforces that call matching is not token matching. Monetary
cost cannot be reconstructed from these receipts without a dated account-rate
contract, so no price estimate or cost superiority is reported.

Resource receipts for the later Java replication and transfer diagnostics are
reported in Supplement S23--S24. They do not support an efficiency claim and
are not pooled with the primary effectiveness result.

Post-result verifier audits reran each new materialized Mini workspace twice.
JavaScript reproduced the identical 47/49 task vector in both reruns; its
normalized outcome SHA-256 was
`f6eee9417245ba316134fb16875dda1d4fbaa63df2c63fa1714e41c67a52d8ad`.
HumanEvalFix reproduced 164/164 with byte-identical stdout SHA-256
`c37bd431873259b50d981f631331c5a3672fa385bb50d2f38a5f90b87fc2843a`.
Java164 likewise reproduced 164/164 twice with byte-identical stdout SHA-256
`6fdfac26bd45c95f3c0cc4edc1f35dabb7344b316010eca6b57cf444cde220dc`.
Manifest audits found unique, non-nested task roots and zero multiply owned
declared solution paths (49/49 and 164/164). These checks support A1/A2 for the
new packaged tracks; they do not prove verifier stability outside the observed
reruns or for repositories with shared build state.

### 5.9 Failure-driven and ceiling boundaries

The earlier strict Java20 gate solved 5/20 versus 7/20 for matched structured
repair. This negative result rejects the rule “edit only when two views agree.”
An earlier Java47 adjudicator solved one additional task but lost a Plain pass
during manual patch transfer, motivating byte-exact anchoring. These are
development results and are not pooled with the 90 v2 tasks.

Additional ceiling and out-of-domain diagnostics are reported in the
supplement and are not pooled with the code-repair endpoint. Together with the
development failures above, they motivate the paper's central design choice:
agreement proposes a hypothesis, whereas executable verification authorizes
promotion.

### 5.10 Matched expectation-view development on complete Java47

The expectation-aligned variant was frozen before its new final executions
on all 47 official Java tasks. This was an already exposed development track,
not an untouched benchmark. Both arms started from the original R candidate,
received the same P/G/R sources and 899 candidate-case failure records, and used
the exact same generic repair instruction. Each system contained four logical
agent executions: the shared P/G/R prefix and one new repair. Both new calls
had a 900-second cap and the same 180-second completion reserve.

| Feedback representation | Raw candidate | Materialized system | Final agent s | Final output tokens |
|---|---:|---:|---:|---:|
| Case-local expected/observed feedback | 12/47 | 12/47 | 639.07 | 20,170 |
| Expectation-aligned obligation overlap | 16/47 | **17/47** | 701.81 | 22,055 |
| Fresh case-local execution B | 20/47 | **21/47** | 744.81 | 24,850 |

The system difference is 5/47 tasks, or 10.64 percentage points. Overlap uniquely
solves affine-cipher, all-your-base, change, circular-buffer, phone-number and
pig-latin; the control uniquely solves alphametics. A previously passing
book-store state is restored by the common verifier selector, raising overlap's
raw 16-task candidate to its actually re-evaluated 17-task system. Both arms pass
normal-completion, source-scope, evidence-preservation and complete-inventory
gates. The two views reconstruct all 899 original failure records exactly.

This isolates a concrete representation contrast under a common instruction,
but its 6:1 discordance is one realized whole-track pair: conditional exact
one-sided p=.0625 and two-sided p=.125. It does not establish repeated-session
superiority. Full four-execution agent-time totals are 2187.76 and 2250.50 seconds;
output-token totals are 85,377 and 87,262. The same ceilings were assigned, while
realized agent time and output tokens were 2.87% and 2.21% higher for overlap,
respectively; evaluator time is excluded from these agent totals.

Source inspection identifies both contract repairs and a branching repair.
The control leaves bare exceptions in BaseConverter despite the supplied
message requirements; overlap distinguishes invalid bases, negative digits and
out-of-range digits with their required messages. Its Pig Latin repair also
handles noninitial y and qu in the consonant scan. These examples support
missed-obligation repair as a plausible explanation, not an independently
validated cause for every outcome. The earlier raw-feedback generic system
scored 16/47 under a different instruction/representation; the 12-task matched
control is not the best generic trajectory ever observed.

A fresh case-local execution B, specified before either original A/O outcome
existed, received the original inputs without A/O outputs. Its normally
completed candidate solved 20/47 and its re-evaluated four-execution system
solved 21/47. Thus the first 17-versus-12 contrast is not evidence of stable
dominance over repeated generic repair. The separately frozen five-execution
comparison gives **18/47 for P/G/R+A+O versus 22/47 for P/G/R+A+B**, after
both complete source portfolios are materialized and re-evaluated. Overlap
rescues three tasks and loses seven relative to the repeated-generic system,
for a net -4/47. Thus the expectation-view signal merits mechanism development,
but this variant does not supply the missing equal-budget system advantage.
S25 retains the complete chronology and resource accounting.

## 6 Discussion

### 6.1 What is established

The best-supported object is Mini Artichokes as a five-call effectiveness
system, not semantic overlap as an isolated causal treatment. It reaches 59/90
on the original complete tracks, 33/39 on frozen Go, and 47/49 on cleanly
frozen JavaScript. It also reaches 164/164 on complete HumanEvalFix Python.
JavaScript exceeds ordinary repair by five tasks and Plain by twenty; Go
exceeds them by eight and sixteen. Descriptively across all 178 Aider tasks,
Mini, ordinary repair, and Plain score 139, 112, and 59. These are bounded-call
effectiveness results, not a general efficiency claim.

The matched portfolio view is narrower in claim but stronger in fairness. The
two five-call systems score 139/178 for Mini and 132/178 for
Direct∪Generic, with 8:1 discordance and positive net differences on three of
five tracks. This reduces nominal-call confounding but not chronology,
trajectory dependence, or realized-compute confounding: the original tracks
are post hoc at this layer, Go is a replacement sensitivity, and prospective
JavaScript is tied. We therefore treat it as a descriptive inventory
sensitivity rather than the main confirmation.

The system result has two parts. First, the promotion property is mechanical
under A1--A5: an observed pass is represented by a complete task state and is
never surrendered to model discretion. Second, the empirical benefit beyond
the verified floor depends on route complementarity. TOV and direct repair add
different passing tasks in the original tracks, repeated sessions, and Go39;
recursive promotion retains those crossings. The repeated-session union has
210/300 verified passes, versus 198 for TOV alone, and the frozen Go system adds
seven tasks to its 26-task floor.

The component evidence is narrower. On the common original starting state,
Generic and semantic-free structured calls each add 3 solutions whereas TOV
adds 10. The stricter control gives a seven-task realized TOV advantage after
ledger, falsification, and audits are matched. Newly frozen sessions show
trajectory variation, however, and the motivating one-task Java
completion-lock result does not repeat in five new whole-track pairs. Semantic
relations with literal failure closure are therefore supported as a productive
heterogeneous branch, not as a reliably superior standalone policy or a
validated semantic measurement instrument.

### 6.2 Why soft semantic overlap differs from consensus

Hard consensus asks whether candidates choose the same answer or edit. TOV asks
which behavioral obligation each candidate appears to satisfy or violate.
Agreement can be useful, but disagreement is often more diagnostic: competing
implementations expose an ambiguous interface, lifetime rule, overload, or
edge-case convention. TOV turns that difference into a counterexample request.
The strict Java failure demonstrates why disagreement must not be a veto.

Verified anchoring is complementary but causally separate. It preserves the
observed test labels of already solved tasks and eliminates their regression
surface. Because generic,
semantic-free, and TOV all share the same anchors, anchoring explains their
common 48/90 floor but not TOV's original 7-task advantage. Applying the same
rule recursively explains why conditional TOV successes can be retained
without accepting its session-specific harms.

### 6.3 Appropriate operating point

The observed regime has four properties: tasks are modular, candidate attempts
fail differently, a trusted external verifier can certify completed units, and
failure output is informative without revealing gold code. TOV has little room
to help at ceiling, as QuixBugs illustrates, or when all candidates repeat the
same defect. It is also inappropriate when tests are unavailable or too weak to
make anchors meaningful.

The post hoc discordance analysis suggests that interface-heavy tasks provide
room for semantic falsification, but the repeated C++ crossovers show that
task type alone is not a sufficient gate. When trusted task tests are available,
the appropriate operating point is recursive: retain the deterministic floor,
run overlap-aware and direct repairs only on unresolved tasks, and promote only
verifier-passing files. When such tests are unavailable, an evidence-only
selector remains an unvalidated extension. Rust `fizzy` and C++ session 1 also
show that accurate diagnosis does not guarantee syntactically or operationally
safe execution.

## 7 Limitations

All semantic calls use one model and runtime, so candidate errors can be
correlated. Each task vector is also produced inside one whole-track call.
Task-level exact tests and bootstraps therefore condition on realized calls;
five-pair repetitions on two tracks measure trajectory variation but do not
estimate a broad model, language, or benchmark population.

The evidence has multiple stages. Rust develops TOV, Python confirms the frozen
policy, and C++ extends it. The stricter ablation and recursive composition are
secondary. Go's system protocol is frozen, but its Generic replacement is
post-primary. Consequently, 139/178 versus 132/178 is a complete-inventory
descriptive summary, not a preregistered five-track trial; the clean prospective
JavaScript comparison is a tie between the five-call portfolios.

The method assumes modular task ownership, isolated workspaces, and a stable
task verifier. The Go `counter` row has no active test, and every official suite
is only a finite specification. Anchors preserve observed test labels, not
correctness beyond those tests. Shared files, cross-task build state, flaky
tests, or unavailable tests require a coarser unit or a different method.

The semantic-free control matches explicit instructions, evidence, calls, and
caps, but cannot equalize latent trajectories or realized compute. The initial
TOV advantage is post hoc at the strictest ablation layer; repeated effects are
uncertain. Likewise, one exact Java completion-lock rescue does not repeat in
five new pairs. Ledger diagnoses are not independently labelled, so semantic
overlap is a useful route construction rather than a validated measurement
instrument.

HumanEvalFix Python reaches a 164/164 ordinary-repair ceiling and used Python
3.13.11 rather than the anticipated 3.13.5/reference 3.9.13 environment. Java
uses OpenJDK 17.0.17 rather than the reported Java 18.0.2; C++ translates the
same underlying tasks; and public QuixBugs may occur in training data. These
studies bound portability and mechanism claims rather than establish broad
generalization.

Finally, Mini uses five whole-track model calls plus intermediate verification.
It is an effectiveness system, not an efficiency result. Graph, ordinary
repair, Generic Critic, and the named reasoning methods are bounded prompt
realizations rather than complete reproductions of every published framework.
We do not claim state-of-the-art superiority over a matched full repository
agent such as KIRA.

## 8 Ethics and reproducibility

The primary study uses public open-source exercises and no human participants.
Models never receive private test source or gold implementations. Failure
stdout can nonetheless reveal behavioral expectations, so the experiment is
reported as test-available program repair rather than one-shot code generation.
The method increases inference compute; actual calls, tokens, cached tokens, and
latency are disclosed.

The evaluated Exercism task directories carry per-task MIT license files, and
HumanEvalPack is distributed under the MIT license. Redistribution of source
tasks must retain those notices; generated patches and experiment metadata do
not relicense upstream material. The artifact should therefore ship upstream
license notices beside any redistributed task files.

The artifact contains frozen protocols, complete task IDs, source commit,
public task packets, evaluator hashes, candidate and final patches, bounded
traces, per-task outcomes, ledgers, anchor maps, and paired reports. Benchmark
packaging and verification code support auditability but are not claimed as
scientific contributions.

## 9 Conclusion

Mini Artichokes turns complementary repair attempts into a test-label-preserved
system. A complete task state that passes the external verifier becomes an
immutable anchor; only common failures remain editable; direct and
overlap-aware routes branch from the same floor; and the verifier, not an LLM
vote or patch intersection, decides which complete states are recursively
promoted.

On the original 90 complete Aider tasks, Mini reaches 59/90 versus 45/90 for
ordinary repair and 15/90 for Plain. The frozen Go39 system reaches 33/39
versus 25/39 and 17/39; cleanly frozen JavaScript49 reaches 47/49 versus 42/49
and 27/49. Across all five complete tracks the corresponding totals are
139/178, 112/178, and 59/178. HumanEvalFix Python provides an independent
164/164 ceiling result, and repeated route pairs produce 210/300 passes after
recursive promotion versus 198 for TOV alone. These comparisons establish
effectiveness with additional bounded calls, not compute efficiency or
correctness beyond the supplied tests.

The same-five-call Direct∪Generic portfolio reaches 132/178. This secondary
comparison reduces nominal call-count confounding but is mixed-stage, and the
clean prospective JavaScript track is tied at 47/49. It is therefore a fairness
sensitivity rather than the primary empirical claim.

Semantic overlap remains important but subordinate to that system claim. TOV
adds 10 tasks above the original 48-task floor, versus 3 for each final control,
and contributes unique rescues to the recursive system. Newly frozen sessions
show that no standalone semantic route is uniformly best; the recursive union
is valuable precisely because the verifier can retain route-specific wins
without entrusting preservation to the model. The supported conclusion is:
preserve complete externally verified states, use semantic agreement and
disagreement to generate falsifiable repair hypotheses, require literal closure
of every observed failure, and recursively promote only observed passing
outcomes.

## Data and code availability

The artifact contains the frozen protocols, complete task manifests, prompt
hashes, model receipts, candidate and final patches, bounded failure evidence,
decision ledgers, anchor maps, per-task outcomes, paired analyses, materialized
unions, and post-result verifier audits. Supplement S1 provides the SHA-256
manifest that binds every reported experiment to these files; S13--S24 provide
the corresponding result and deviation records.

Upstream sources are pinned to Aider Polyglot commit
`7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`, HumanEvalPack revision
`9a41762f73a8cb23bb5811b73d5aab164efcf378`, and QuixBugs commit
`4257f44b0ff1181dedaedee6a447e133219fcebf`. Packaging and evaluator code are
released for auditability but are not claimed as contributions.

## References

1. Madaan A, Tandon N, Gupta P, et al. Self-Refine: Iterative Refinement with
   Self-Feedback. Advances in Neural Information Processing Systems 36, 2023.
   https://proceedings.neurips.cc/paper_files/paper/2023/hash/91edff07232fb1b55a505a9e9f6c0ff3-Abstract-Conference.html
2. Huang J, Chen X, Mishra S, et al. Large Language Models Cannot Self-Correct
   Reasoning Yet. International Conference on Learning Representations, 2024.
   https://openreview.net/forum?id=IkmD3fKBPQ
3. Stechly K, Valmeekam K, Kambhampati S. On the Self-Verification Limitations
   of Large Language Models on Reasoning and Planning Tasks. arXiv:2402.08115,
   2024. https://arxiv.org/abs/2402.08115
4. Wang X, Wei J, Schuurmans D, et al. Self-Consistency Improves Chain of
   Thought Reasoning in Language Models. International Conference on Learning
   Representations, 2023. https://openreview.net/forum?id=1PL1NIMMrw
5. Du Y, Li S, Torralba A, Tenenbaum JB, Mordatch I. Improving Factuality and
   Reasoning in Language Models through Multiagent Debate. Proceedings of the
   41st International Conference on Machine Learning, 2024.
   https://proceedings.mlr.press/v235/du24e.html
6. Besta M, Blach N, Kubicek A, et al. Graph of Thoughts: Solving Elaborate
   Problems with Large Language Models. AAAI 38(16), 2024.
   https://arxiv.org/abs/2308.09687
7. KRAFTON AI and Ludo Robotics. KIRA: a terminal-use agent harness. GitHub
   repository, accessed 2026. https://github.com/krafton-ai/KIRA
8. Ridnik T, Kredo D, Friedman I. Code Generation with AlphaCodium: From
   Prompt Engineering to Flow Engineering. arXiv:2401.08500, 2024.
   https://arxiv.org/abs/2401.08500
9. Chen X, Lin M, Schärli N, Zhou D. Teaching Large Language Models to
   Self-Debug. arXiv:2304.05128, 2023. https://arxiv.org/abs/2304.05128
10. Le CC, Le-Anh M, Van CD, Nguyen TN. Semantic Evolution over Populations
    for LLM-Guided Automated Program Repair. arXiv:2604.02134, 2026.
    https://arxiv.org/abs/2604.02134
11. Yang B, Hu X, Ren L, et al. A Single Patch Is Not Enough: Deterministic
    Fusion of Repair Candidates. arXiv:2607.01597, 2026.
    https://arxiv.org/abs/2607.01597
12. Aider-AI. Polyglot Benchmark: Exercism-based code-editing benchmark. GitHub
    repository, commit `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`.
    https://github.com/Aider-AI/polyglot-benchmark
13. Muennighoff N, Liu Q, Zebaze A, et al. OctoPack: Instruction Tuning Code
    Large Language Models. International Conference on Learning
    Representations, 2024. https://openreview.net/forum?id=mw1PWNSWZP
14. BigCode. HumanEvalPack. Hugging Face dataset, revision
    `9a41762f73a8cb23bb5811b73d5aab164efcf378`, accessed 2026.
    https://huggingface.co/datasets/bigcode/humanevalpack
15. Lin D, Koppel J, Chen A, Solar-Lezama A. QuixBugs: A Multi-Lingual Program
    Repair Benchmark Set Based on the Quixey Challenge. Proceedings of the 3rd
    ACM SIGPLAN International Workshop on Machine Learning and Programming
    Languages, 2017. https://github.com/jkoppel/QuixBugs
