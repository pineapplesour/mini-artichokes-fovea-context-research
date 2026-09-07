# Mini Artichokes fresh legal confirmation v1 — design draft

## Status

**DRAFT; not a preregistration and not authorization to invoke a fresh-reserve
solver.**  Development runner tests and load tests may use only synthetic rows
or the already exposed development set.  No fresh-reserve prompt byte may be
delivered to any solver, judge, verifier, or load-test model until every field
marked `FREEZE-BEFORE-GOLD` has been resolved, the comparator/fairness/statistics
code has passed synthetic adversarial tests, and the phase-A source freeze has
been Git-anchored as `FROZEN BEFORE GENERATOR OUTPUT`.  A local Git commit is a
recoverable byte commitment, not an independently timestamped witness; any
remote append-only witness is reported only if it actually exists.

The instantiated blind packets cannot be known at phase A.  They are frozen
after D1–D3 and before any blind call under the phase-B procedure below.  This
two-phase necessity is stated explicitly; a one-phase pre-output freeze is not
claimed.  `FREEZE-BEFORE-GOLD` also means **before the first fresh solver call**
unless the field is intrinsically derived from already frozen gold-free model
artifacts, in which case the derivation rule and code must be phase-A frozen.

Hashing, isolation, receipts, and fail-closed validation protect the evidence.
They are not scientific contributions.  The scientific target is higher
full-denominator problem-solving accuracy from a small, reusable overlap-and-
veto decision rule.

## Claim and development boundary

The primary question is whether an at-most-four-response Mini policy
outperforms both fresh one-response Luna anchors and every frozen selected
at-most-four-response comparator on a new legal-outcome reserve:

> Two mutually blinded, separately sampled structured solutions select the
> same alternative outcome and cite the same case-specific decisive evidence;
> a provenance-blind pairwise judgment may veto, but never invent, the proposed
> replacement.

`Independent` is not used as a statistical or epistemic claim.  G1, G2, and G3
use the same Luna model and case, but run in separate ephemeral threads and
cannot read one another's output, memory, trace, or workspace.

The Universal d1/d3/d4 MCQs, V3, V5, V7, and the 589/941 polarity-conditioned
replay are development evidence.  The last of these was selected after private
development outcomes were known (V3 versus replay discordance 5:3, two-sided
exact McNemar p=.7266).  It contributes one design hypothesis only: on a
positive correctness task, a valid blind tie is not a veto and only an
explicit preference for the incumbent cancels a proposed switch.

## Reserve feasibility gate

The source database is the read-only precedent store; its exact path, schema
version, and file hash are `FREEZE-BEFORE-GOLD`.  The seven previous private outcome
sets contain 544 unique cases from three provider datasets:

- `01_joonhok_precedents` (393 prior cases);
- `02_lbox_open` (109); and
- `lawlaw` (42).

The available pool does not support excluding all three provider datasets in
full while retaining the planned strata.  The only permitted disjointness term
is therefore **`prior-project/case/source-record/content-disjoint`**.  The paper
must not shorten this to dataset-disjoint.  Cases dated 2005–2021 are never
described as temporal, post-training, contamination-free, or model-unseen.

All prior outcome public/private files and accepted model-mounted outcome
inputs form the exposure ledger.  A candidate is excluded on any exact match
of canonical ID, normalized court/case number, case number, dedupe key,
primary/fallback dedupe key, text hash, nonempty split group, source dataset
plus source record ID, source path locator, or template-stripped normalized
claim/facts prompt.  The same family keys are unique inside the new cohort.
Deterministic near-duplicate and conclusion-leak checks, their thresholds, and
all exclusions must be frozen before provisional labels are audited.
Generic regex sensitivity hits for procedural words, related dates or courts
are informational and may be legitimate predictive facts.  They do not fail
the reserve merely because an evidence clause contains `인용` or `기각`.
Fail-closed gates are the builder-bound exact target-holding overlap/holding-
section checks and the paired target-specific court, case-number and decision-
date metadata screen.

The public task contains only claim/facts (civil) or disposition-history facts
(tax).  A dedicated facts-only tax template must be used; a literal `None`,
holding, result phrase, reasoning section, source locator, court/case number,
date, label, or label-correlated opaque-ID field is prohibited.  Public
evidence clauses are segmented and numbered by one frozen deterministic
algorithm.  Segmentation markers are stripped when comparing to prior prompt
fingerprints.

## Gold construction and privacy

A deterministic holding parser supplies only a provisional label.  Two
separately invoked auditors see only an opaque ID and the target holding/
disposition text—not the full case record, provisional label, the other audit,
reserve quota, development results, or solver output.  Each records
eligibility, `인용됨|기각|AMBIGUOUS` (reported in English as
`GRANT|DISMISS|AMBIGUOUS`), a meaningful exact holding span, and ambiguity
flags.  Disagreement goes to a third blind adjudicator, who also audits a
committed hash-selected 10% of A/B agreements.

These are expert-model label audits, not human gold and not statistically
independent annotators.  A and C use separate `gpt-5.6-sol` invocations and B
uses `gpt-5.6-terra`; common training and A/C model identity can correlate
errors.  The paper must report that limitation and call the result audited
consensus labels rather than incontrovertible ground truth.

Required acceptance conditions are initial A/B Cohen kappa at least .90,
100% resolved consensus among final rows, no unresolved/counterclaim/appeal/
settlement/dismissal-without-prejudice ambiguity, and zero errors in the third
auditor's agreement sample.  A failed gate causes a full audit/rebuild under a
new documented protocol version, never a selective relabel.

Within each domain/label cell, accepted cases are selected by
`SHA256(committed_sample_salt || canonical_id)`.  Let

- `q_civil = min(150, accepted civil-grant count, accepted civil-dismiss count)`,
  with the feasibility requirement `q_civil >= 140`; and
- `q_tax = min(90, accepted tax-grant count, accepted tax-dismiss count)`, with
  the feasibility requirement `q_tax >= 80`.

The final reserve therefore has exactly
`N = 2*q_civil + 2*q_tax`, hence **440 <= N <= 480**, with equal grant/dismiss
counts inside each domain.  The exact accepted counts, salts, ordered IDs,
public/private hashes, and N are `FREEZE-BEFORE-GOLD`.

`FREEZE-BEFORE-GOLD`: a power analysis recomputed for the exact N, the
four-cell MBA statistic, the full IUT, and conservative discordance/trigger
rates taken only from exposed development evidence.  Retrospective observed
power and sample-size extension after gold opening are prohibited.

A second committed salt assigns opaque IDs and an order used for artifact
publication only.  Gold auditing and exposed development may be sharded for
transport.  **Every fresh solver item is nevertheless executed as a singleton
model invocation:** one case, one item-stage stdin packet, one fresh thread.
No fresh confirmation response may contain two reserve cases.  Private labels,
source metadata, audit receipts, and the mapping to opaque IDs remain outside
every solver-visible packet.  The private commitment is opened only after all
arm outputs, costs, eligibility decisions, and receipts are accepted and
frozen.

## Common singleton runner and structured draw bank

The structured draw bank contains eight separately sampled singleton draws
`D1` through `D8`.  For the Mini notation, `G1=D1`, `G2=D2`, `G3=D3`, and
`G4=D4`.  D1–D8 receive byte-identical one-case public packets, role
instructions, schema, model, and runtime settings in separate ephemeral
threads.  A draw cannot read another draw.  The bank exists both to share
candidate luck fairly across Mini/SC/Bo3+J and to publish the complete
`SC-k, k=1,...,8` cost–accuracy curve; unused later draws never affect Mini.

Every model-bearing stage in every fresh arm—structured draws, plain direct,
blind or multiway judges, critique, revision, suggestion, memory, and ICR final
revision—uses the same singleton zero-tool first-attempt runner.  Causal prior
artifacts are embedded in the exact stdin packet for that item; they are not
made available through files or tools.  The common fixed settings are:

- `CODEX_HOME=/home/pineapple/.codex-new-account` supplied by the supervisor;
- `gpt-5.6-luna`, reasoning `high`, verbosity `low`, service tier `default`;
- exactly one public case and only the stage-authorized prior artifacts
  embedded in stdin, with no public or prior-artifact file mount;
- `FREEZE-BEFORE-GOLD`: exact Codex CLI version/binary hash, feature-list
  stdout hash, and canonical `{name,stage,enabled}` snapshot hash;
  `--ignore-user-config`, `--ignore-rules`, `--strict-config`, and
  `--ephemeral` are mandatory;
- every enumerated model-tool surface in the frozen strict-control argv,
  including `shell_tool`, `unified_exec`, `code_mode`, `code_mode_host`, apps,
  browser/computer, plugins, skills, multi-agent, image/view and shell-snapshot
  surfaces, is explicitly configured false; native web, MCP and local code are
  off;
- the runner records an empty configured model-tool-schema list and its hash,
  but does not call provider-side schema advertisement independently attested;
- the exact JSON output-schema file SHA and literal `--output-schema` CLI
  argument are bound in each source/stage receipt; the blind schema template is
  phase-A frozen and any conflict-count-specific instance is phase-B frozen;
- strict parsing of the final response and zero tool events in raw traces,
  including both `item.started` and `item.completed` command/tool events.  Raw
  event types are allowlisted to thread/turn lifecycle plus item lifecycle;
  item lifecycle records may contain only `reasoning` or `agent_message`.
  Codex 0.151.0 also emits one pre-turn `item.completed/error` stating that
  code mode is unavailable because `code_mode_host` is disabled and will fail
  closed; only that exact frozen diagnostic, schema, cardinality, and position
  are accepted.  Every other error, unknown event or item type, including
  `file_change`, fails closed;
- exactly one nonempty `thread.started` identity in each singleton item-stage
  trace, bound into its stage receipt; all model-bearing stages for an item
  have distinct thread identities;
- legacy file-agent/bubblewrap receipts are ineligible.  The Codex process may
  receive its required authentication, but the receipt may state only the
  validated consequence that it was not exposed through a model tool surface;
- `FREEZE-BEFORE-GOLD`: exact per-stage output and total-token ceilings derived
  only from synthetic or exposed-development load tests.  A fresh reserve row
  may never be used to tune or load-test a limit;
- exactly one model-bearing semantic first attempt, no selective top-up, and no
  retry after any thread, reasoning, agent-message, or token event.  Any
  permitted pre-model transport retry rule is `FREEZE-BEFORE-GOLD`, common to
  every arm, and must prove zero model events/tokens on the abandoned process;
- an authenticated missing, malformed, or semantically invalid first-attempt
  row becomes a null scientific prediction and is scored wrong on the full
  denominator.  Deterministic invalid placeholders may carry causal pipelines
  forward; no arm or item is removed.  Missing or tampered authentication
  rejects the joint campaign rather than selectively dropping an arm.

Fresh item-stage execution is dependency-aware and interleaved across arms by
a committed hash schedule over `(schedule_salt, opaque_id, arm, stage)`.  At
each step the ready causal stages are hash-ranked; the exact salt, scheduler
code/hash, order manifest, model identifier, CLI version, timestamps, and any
backend fingerprint exposed by the runtime are `FREEZE-BEFORE-GOLD`.  This
prevents a long sequential arm run from silently confounding method with model
or service drift.  BLIND item-stages do not enter the ready set until the global
phase-B conflict/package manifest has been Git-anchored.

Each structured singleton draw returns exactly one record for its one case:

```json
{
  "id": "opaque-id",
  "outcome": "인용됨|기각|ABSTAIN",
  "rationale": "bounded text",
  "evidenceAtoms": [
    {
      "issueCode": "ENUM",
      "evidenceClauseId": "F001",
      "exactQuote": "the complete referenced public-clause text",
      "direction": "FAVORS_GRANT|FAVORS_DISMISS"
    }
  ]
}
```

There are zero to two atoms.  `exactQuote` is 8–240 Unicode code points and
must equal the entire text of the named numbered public clause.  An arbitrary
substring is invalid.  Duplicate atoms, unknown
clause IDs/codes, mismatched quotes/directions, a third atom, missing or extra
rows, or synthesized IDs are invalid.  The frozen issue-code set is:

- `REQUIRED_ELEMENT_PRESENT`;
- `REQUIRED_ELEMENT_ABSENT`;
- `RULE_OR_EXCEPTION_APPLIES`;
- `BURDEN_OR_STANDARD_MET`;
- `BURDEN_OR_STANDARD_NOT_MET`;
- `REMEDY_OR_PROCEDURE_CONTROLS`;
- `RECORD_CONTRADICTION`; and
- `UNSUPPORTED_INFERENCE`.

The exact overlap key is
`(issueCode, evidenceClauseId, exactQuote, direction, outcome)`.  Because the
quote must be the complete clause, this operationally means the same
issue-tagged evidence clause, not a claim that two model-generated propositions
are epistemically identical.  Rationale,
embeddings, synonyms, judge interpretation, confidence, domain, and private
outcomes never enter matching.  Clause IDs replace model-supplied character
offsets so that matching remains exact without testing an LLM's arithmetic
over Unicode positions.

## Primary Mini-4 policy

`Mini-4` is shorthand for an **at-most-four-response** per-item policy.  D1–D3
always run.  The blind fourth response runs only for an authenticated
answer-only conflict `D2=D3!=D1`; items without that conflict end after three
responses.  The deployable and attributed research cost includes every stage
the policy would invoke under this rule.

Let P be the canonical G2/G3 outcome.  The deterministic trigger is true iff:

1. G1, G2 and G3 have valid canonical outcomes;
2. `G2.outcome == G3.outcome == P != G1.outcome`; and
3. the exact G2/G3 atom intersection contains at least one atom whose
   direction supports P.

If several atoms overlap, the lexicographically first key is recorded without
changing the action.  Answer agreement without atom overlap is ineligible.
G1's atoms are never part of the trigger.

For every answer-only conflict, whether or not atom overlap holds, a committed
hash bit selects D2 or D3 as the exact proposal carrier and independently
rotates incumbent/proposal to LEFT/RIGHT.  The same singleton blind-certificate
inventory is attributed to Mini and answer-only-veto so that atom eligibility
is their only mechanism difference.  The blind judge sees only the public case
and two canonical outcome labels.  It does not see prose, atoms, agreement
count, overlap eligibility, confidence, generator roles, strict-verifier data,
development results, or gold.

The final action is:

- no trigger: exact G1 outcome;
- valid trigger plus explicit hidden-incumbent preference: exact G1;
- valid trigger plus proposed preference or valid tie/unresolved judgment:
  exact P;
- on a case where the policy's trigger requires the blind certificate, an
  authenticated invalid first attempt yields exact G1 only in a separately
  named deployment fallback; the scientific prediction is null and wrong on
  the unchanged full denominator.  A blind failure on an answer conflict that
  lacks structured overlap does not invalidate Mini's unchanged G1 scientific
  prediction, but it does invalidate answer-only-veto on that case;
- missing or tampered authentication/receipt artifacts: reject the campaign.

The judge cannot synthesize an outcome.  This is an explicit-incumbent veto,
not a requirement for a second positive vote.

## Frozen comparator family

The frozen joint family distinguishes two one-response anchors and strong
selected inference-time comparators.  These names do not imply coverage of all
published methods.

- `Plain-Luna-1`: one separately sampled Luna response to the same public case
  using a minimal frozen `{outcome,rationale}` schema and no atom request.  This
  is the plain direct anchor.
- `Structured-Direct-1`: exact D1.  This is a one-response structured anchor,
  not relabeled as plain Luna.
- `SC-4`: plurality over D1–D4.  `ABSTAIN` is a canonical but always-wrong
  prediction; any top-count tie returns D1.  No judge or synthesis is used.
- `Bo3+J`: D1–D3 plus a separately invoked provenance-blind multiway judge.
  The judge sees the public case and the complete bounded rationale/evidence
  content of all three candidates, with candidate identity removed and order
  hash-rotated.  It must select an exact existing candidate index and cannot
  synthesize text or an outcome.  A label-only judge is ineligible because it
  would not implement a strong generative-verifier baseline.
- `CR-4`: shared initial D1, then a case-grounded critique, a revision consuming
  D1 and the critique, and a fourth provenance-blind pairwise judge.  The judge
  sees the public case plus the complete bounded initial and revised candidates
  under hash-rotated LEFT/RIGHT roles and must select one exactly.  The frozen
  paper name must state that this is the task-adapted four-response
  critique–revise-plus-choice implementation, not an exact reproduction of
  every Self-Refine configuration.
- `task-adapted-ICR-4`: shared initial D1, iterative suggestions, a memory stage
  compressing the public case/D1/suggestions to at most eight **bounded**
  bullets, and a final revision consuming all three artifacts.  It uses the
  common stdin-only zero-tool runner.  It is a budgeted task adaptation, not a
  claim to reproduce canonical or historical ICR exactly.
- `answer-only-veto-4`: the same D1–D3 and exact blind-certificate inventory as
  Mini-4, but eligibility uses only `D2=D3!=D1`, omitting atom overlap.  It is
  the mandatory paired mechanism control; all shared calls and blind costs are
  attributed in full to both deployable policies.

The exact prompts, output schemas, character/token bounds, tie/invalid rules,
role salts, and implementation hashes for all anchors and comparators are
`FREEZE-BEFORE-GOLD`.  Comparator prompt development may use only synthetic or
exposed-development data.  Baselines receive a documented bounded tuning
opportunity or a cited canonical prompt adaptation; a deliberately weak
single prompt is not admissible.

D1–D8 also define the frozen direct/self-consistency prefix curve
`SC-k, k=1,...,8`, using the same plurality and tie-to-D1 rule.  Every point is
published.  `SC-4` remains a named response-capped comparator even when another
prefix is selected by the gold-free measured-cost rule below.  Sharing model
outputs controls candidate luck but does not make arm estimates independent;
all analysis remains paired.  Every shared call and token is counted in full
for each deployable arm, never at its marginal campaign cost.

The exact historical `test37` ICR graph (one initial plus three
suggestion/revision/memory cycles, ten calls) is a predeclared supplementary
cost-curve comparator over the same reserve.  Its tenth memory update does not
affect the returned ninth-call revision but is retained for architectural
fidelity.  Because Luna does not expose the original temperature schedule, it
is a task-adapted prompt/call-graph reconstruction, not an exact runtime or
historical-prompt replication.
The old 10/10 was one development question and is not pooled with this result.

## Nested secondary Mini-5

After D1–D3, both a label-only blind package and a role-exposed strict package
are generated and hash-frozen before either verifier runs.  The strict and
blind calls use separate threads/workspaces and may run in parallel.  The
blind package cannot read the strict package or even learn that it exists.

The strict verifier may return only
`VALID_EXACT_PROPOSAL|KEEP_INCUMBENT|ABSTAIN`; it cannot add atoms, discover
paraphrase overlap, synthesize another outcome, or change the exact proposal.
Mini-5 switches only when the exact Mini trigger holds, strict returns
`VALID_EXACT_PROPOSAL`, and the blind judge does not explicitly prefer the
incumbent.  Mini-4 is reproducible from G1/G2/G3/blind alone.  Mini-5 is a
secondary safety/accuracy operating point and cannot rescue the primary claim
or be selected posthoc as the headline system.

## Analysis order and endpoints

The order is mandatory: finish and validate all public calls; publish complete
gold-free arm outputs; hash all outputs, traces, receipts, role maps and cost
ledgers; run an independent gold-free audit; then open the private commitment
once and score every frozen arm.

Freezing is deliberately two-phase:

1. Before any fresh solver call, the Git-anchored phase-A source
   freeze binds the public artifact/builder/audit receipts, label-independent
   ID construction, all anchor/comparator prompts and schemas, D1–D8 packet
   templates, blind prompt template, execution/cost settings, singleton runner,
   hash-interleaved scheduler, statistics code, carrier/rotation seeds, and
   blind-package derivation contract and code hashes.
2. After authenticated singleton D1–D3 first attempts are frozen for every item
   but before any blind call, a second Git-anchored phase-B
   blind-package manifest binds their artifact/raw/trace/receipt/validation/
   attempt/token hashes, the exact ordered answer-conflict inventory, every
   instantiated singleton blind stdin-packet hash/output-schema hash, and the
   hidden role-map hash.  Packet bytes are reproduced by replacing the
   template's single
   `{{BLIND_ITEMS_JSONL}}` marker with ordered canonical public/LEFT/RIGHT
   JSONL.  Under singleton execution the corresponding schema instance has one
   item; the aggregate manifest also binds the total conflict count.
3. Before combination and gold opening, the campaign manifest binds both
   external anchors plus every arm output, eligibility result, cost ledger,
   deterministic cost-matched-prefix selection, and all post-call evidence.

Thus the phase-A freeze never pretends to bind a blind packet that depends on
later D1–D3 outcomes.  `goldAccess`, blind provenance, and authentication non-
exposure through the model tool surface are derived from validated receipts,
not hard-coded by the combiner.  Comparator-wide budget/fairness validation
remains a separate mandatory top-level audit.  Its code and acceptance contract
are phase-A frozen; its observed report is necessarily
`PENDING_GOLD_FREE_OUTPUTS` until all token receipts exist.

Primary denominator is all N accepted reserve cases.  Missing, abstained,
unparsed, malformed, duplicated, or out-of-order output is wrong and never
dropped.  The authenticated raw first attempt is preserved; no selective retry
may replace a bad row.  Full-denominator scientific files contain a null outcome
for such a row, while any operational fallback is emitted to a separately named
deployment file.

The primary endpoint is full-denominator **macro-balanced accuracy**:

`MBA = (Acc[civil,grant] + Acc[civil,dismiss] + Acc[tax,grant] + Acc[tax,dismiss]) / 4`.

Each of the four domain/label cells therefore receives 25% weight regardless
of the availability-driven civil/tax sample-size ratio.  Unweighted raw
full-denominator accuracy on the fixed 440–480-case reserve is secondary.  For
every paired comparison report MBA and raw risk differences, rescues, harms,
the four cell results, domain label-balanced results, exact one- and two-sided
McNemar p-values for the raw endpoint, and a stratified paired bootstrap risk-
difference interval.  The bootstrap seed, replicate count, interval method,
and implementation hash are `FREEZE-BEFORE-GOLD` and may be tested only on
synthetic/exposed data.

The MBA superiority test is a preimplemented one-sided stratified paired
sign-flip/randomization test that preserves the four fixed strata and the full
paired outcome vector.  Its exact conditional convolution or frozen Monte
Carlo implementation, statistic, seed, replicate count, plus-one correction,
and numerical tolerance are `FREEZE-BEFORE-GOLD`.  Singleton fresh execution
is mandatory for treating reserve items as the analysis units; no item-level
test may be substituted for clustered batch output.

The primary superiority statement uses one fixed intersection–union test
(IUT), not a post-output choice between max-T and Holm.  Let the phase-A set
`J` contain:

1. `Plain-Luna-1`;
2. `Structured-Direct-1`;
3. `SC-4`;
4. `Bo3+J`;
5. `CR-4`;
6. `task-adapted-ICR-4`; and
7. `answer-only-veto-4`.

For every `j in J`, test `H0_j: MBA(Mini-4)-MBA(j) <= 0` against the one-sided
alternative at `alpha=.05`.  The joint claim is authorized only if **every**
comparison has a valid one-sided p-value below .05 and its frozen one-sided 95%
lower confidence bound exceeds zero.  This conjunction is the primary IUT and
does not receive a Holm penalty.  Holm-adjusted p-values and corresponding
individual-comparison interpretation are reported secondarily; two-sided
tests are descriptive.  No comparator may be removed because its result is
unfavorable or its authenticated first attempt is malformed.

Domain guards are also frozen conjunctive requirements.  Within civil and tax,
use label-balanced accuracy and require the one-sided 95% lower bound for
`Mini-4 - comparator` to exceed `-delta_NI` for every primary comparator.
`FREEZE-BEFORE-GOLD`: the common noninferiority margin `delta_NI`, its scientific
rationale, and test/interval implementation.  An eligible SC-k* is also subject
to both domain guards.  The margin may be selected only from exposed development
evidence and substantive tolerance, never from a fresh prompt, output, or gold
score.  If a domain guard is not met, only a narrower aggregate description is
allowed; domain-wide no-harm is not claimed.

Mini-5, ICR-10, raw-accuracy tests, individual SC-curve points other than the
predeclared cost-matched point, and error taxonomy are secondary and cannot
rescue the primary IUT.

Mechanism reporting includes raw answer-conflict count, exact atom-overlap
coverage, pre-veto and post-veto rescue/harm, beneficial-switch precision,
rescue retention, harm leakage, blind preferences, and the paired difference
between Mini-4 and answer-only-veto-4.  Error categories may describe frozen
outputs but cannot retune the atom enum, overlap threshold, action, or reserve.

## Cost and reporting

For every singleton item-stage and deployable arm, the authenticated cost ledger
reports semantic responses, actual process/model invocations, input tokens,
cached input tokens, `uncachedInput = input - cachedInput`, output tokens,
reasoning tokens, total tokens, any permitted pre-model transport attempts,
elapsed time, end-to-end critical path, and billable cost when derivable.
Reasoning tokens are reported separately but are a subset of output tokens and
must never be charged twice.

`FREEZE-BEFORE-GOLD`: the exact contemporaneous price/version source and hash,
or, if billable price cannot be attested, the frozen token-equivalent weights.
For the same model, the preferred attributed cost is

`C = p_uncached*(input-cachedInput) + p_cached*cachedInput + p_output*output`.

Every shared D call is counted in full for every arm that would deploy it.
Research-campaign marginal cost is never used as arm cost.  Conditional blind
calls and all tokens of authenticated abandoned transport attempts are charged
to the arm whose frozen policy would invoke them.

Four responses alone are **not** called equal compute.  A comparator is called
`measured-cost-matched` only when its fully attributed gold-free cost satisfies
`0.80 <= C_comparator/C_Mini <= 1.25`.  The same report must show the complete
cached/uncached/reasoning/output token vector so that monetary matching is not
misrepresented as hidden-compute identity.  Comparisons outside the window are
described only as same-maximum-response-count, lower-cost, or higher-cost as
applicable.

After all D1–D8 outputs, Mini blind outputs, and their complete attributed cost
ledgers are frozen but before gold is opened, the phase-A-frozen selector
chooses `SC-k*` from the curve points inside the 0.80–1.25 window by minimum
absolute log cost ratio to Mini; an exact tie goes to smaller k.  The comparison
uses aggregate deployable cost across the same N items.  All eight points are
reported regardless.  If no prefix lies in the window, no equal-cost SC claim
is authorized and no extra draw may be added.  If eligible,
`Mini-4 > SC-k*` is an additional one-sided IUT requirement for the measured-
cost-matched statement; the selector cannot inspect labels or scores.

The exact cost-ledger schema, arithmetic tests, selector code/hash, price
weights, and rounding tolerance are `FREEZE-BEFORE-GOLD`.

If all applicable gates pass, the narrow permitted claim is that on this
precommitted 440–480-case, four-cell-macro-balanced Korean civil/tax reserve,
the frozen Luna Mini at-most-four-response policy had higher full-denominator
MBA than both fresh one-response anchors and each named selected response-
capped comparator.  Only if the cost window and additional SC-k* gate pass may
the paper add that it beat the preregistered measured-cost-matched SC prefix.

The paper must say `selected frozen baselines`, not `all known methods`, and
`same maximum response count`, not `equal compute`, unless the measured-cost
condition is explicitly named.  No Universal, cross-model, model-agnostic,
temporal-holdout, contamination-free, broad legal-generality, deployment-
safety, or exact historical-ICR claim follows from one Luna snapshot and two
related Korean legal domains.  A later independently sealed task family is
required for any such extension.

## Fields required to freeze

- DB, schema, builder, exposure-ledger and prior-input hashes;
- excluded source datasets and counts at every exact/semantic/leak gate;
- provisional pool and audited-reserve counts/hashes, `q_civil`, `q_tax`, and
  exact N in the permitted 440–480 range;
- audit model/config/instructions/receipts and agreement statistics;
- sample/shuffle/opaque-ID/role-rotation commitments;
- public questions, clause map, expected IDs and private commitment hashes;
- D1–D8, plain-direct, every judge, CR and task-adapted ICR instruction and JSON
  schema hash, including every bounded field;
- preparer, runner, validator, combiner, scorer and statistics-code hashes;
- singleton runner and dependency-aware hash-interleaved execution schedule,
  salt, manifest and code hash;
- exact model/runtime/CLI/features/output/token/time/pre-model-transport limits;
- IUT membership, alpha, stratified test specification, bootstrap seed and
  replicate count, Holm-secondary procedure, and domain-NI margin/rationale;
- cost-ledger arithmetic, price/weight source hash, D1–D8 SC-prefix selector,
  0.80–1.25 eligibility rule and rounding tolerance;
- zero-web and isolation audit rules; and
- frozen handling of every missing, tie, abstain and malformed state.

The final frozen copy must contain no unresolved `FREEZE-BEFORE-GOLD` marker.
Resolving a marker with fresh-reserve model behavior, output, or gold is
prohibited except for the explicitly gold-free deterministic cost/phase-B
derivations whose rules and code were already phase-A frozen.
