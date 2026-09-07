# Evidence scope for Mini Artichokes review

This bundle distinguishes scientific evidence from execution QA. Hashes,
receipts, isolation checks, and validators establish provenance only; they are
not a scientific contribution. The current paper's central claim is the
end-to-end effectiveness of verifier-backed preservation and heterogeneous
route union for modular, test-available program repair. It does not claim that
semantic overlap alone is universally or causally superior.

## Complete official coding evidence

All evaluated Aider tasks come from `Aider-AI/polyglot-benchmark` commit
`7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`. The paper retains every task in
five complete language tracks: Rust30, Python34, C++26, Go39, and
JavaScript49. No task is ranked, screened, removed, replaced, or topped up.
Across these 178 tasks, Mini Artichokes solves 139/178 (78.1%), versus 59/178
(33.1%) for one-call Plain and 112/178 (62.9%) for two-call ordinary
execution-feedback repair. This pooled total is descriptive because it combines
development, prospective, and sensitivity stages.

The corresponding same-five-call inventory sensitivity is 139/178 for Mini
versus 132/178 for Direct∪Generic: eight rescues, one harm, +3.93 percentage
points, conditional one-sided exact p=.01953125, paired task bootstrap
`[+1.12,+7.30]`. Track net differences are positive on Python, C++, and Go
and tied on Rust and JavaScript; the three-nonzero-track sign value is `.125`.
This is not a prospective multi-track endpoint: the original union was chosen
post hoc, Go uses a post-primary replacement, and clean prospective JavaScript
is tied.

The cleanest before-call-frozen result is the complete JavaScript49 track.
Mini scores 47/49, versus 27/49 for Plain and 42/49 for ordinary repair. The
paired differences are +20/49 (+40.82 percentage points; 20 rescues, zero
harms; one-sided exact p=9.537e-7) and +5/49 (+10.20 points; 5:0;
p=.03125). The equal-five-call Mini and Direct-union-Generic systems both
score 47/49, and TOV and Generic have identical task vectors. This supports
the complete verified system over the smaller nested baselines, not an
overlap-specific advantage.

The original Rust30/Python34/C++26 construction is development-to-extension
evidence. Mini scores 59/90 versus 15/90 Plain, 45/90 ordinary repair, and
54/90 for the equal-five-call non-overlap union. The last contrast was chosen
after route crossovers were observed and is explicitly post hoc.

Go39 was frozen before calls, but the preregistered Generic invocation produced
no model response after endpoint errors. The primary equal-call endpoint is
therefore unavailable. A later, separately identified same-prompt replacement
gives sensitivity-only scores of 33/39 Mini versus 31/39 non-overlap. Mini
scores 17/39 above Plain and 8/39 above ordinary repair. The official `counter`
task reports `no tests to run`; a test-covered Go38 sensitivity subtracts the
same pass from every arm and leaves every rescue/harm count and exact test
unchanged.

## Independent-family ceiling boundary

The complete BigCode HumanEvalPack `HumanEvalFixDocs` Python configuration is
pinned at revision `9a41762f73a8cb23bb5811b73d5aab164efcf378`; all 164 tasks are
retained. Mini scores 164/164 versus 157/164 Plain, but ordinary repair and all
later systems also reach 164/164. This is a useful ceiling and portability
boundary, not evidence for a final-route or overlap advantage.

The actual freeze manifest and evaluator used Python 3.13.11, not the
protocol's predeclared 3.13.5 or the benchmark paper's Python 3.9.13 reference.
The complete run is retained and labelled runtime-deviating rather than strict
protocol confirmation.

## Prospective completion-lock confirmation

Completion locking was developed from already observed complete HumanEvalPack
JavaScript164 and Go164 failures, then frozen on the previously unused complete
Java164 track. It requires a concrete final-code witness for every literal
observed failure atom after semantic comparison. All 164 Java tasks are
retained. The same-five-call Mini system scores 164/164, versus 163/164 for
Direct∪Generic and 163/164 for semantic-free Direct: one rescue, zero harms,
`+0.610` percentage points, one-sided exact `p=.5`. The sole candidate repair
is byte-identical to the official canonical solution. This is positive
prospective case evidence but not standalone statistical significance.

All three final arms have the same candidate evidence and 163-anchor map, and
489/489 anchor comparisons are exact. Two reruns reproduce 164/164 with the
same stdout hash. The local evaluator uses OpenJDK 17.0.17 instead of OctoPack's
reported Java 18.0.2, so the policy/population freeze is prospective while the
runtime is explicitly deviating.

## Mechanism evidence boundary

Under the stated A1--A5 assumptions, promoting complete test-passing task
states makes Mini's task vector the verifier union of its included routes. A
minimal offline task-wise union over the same stored outputs and test labels is
algebraically identical. The contribution is the enforced systems composition:
immutable passing anchors, unresolved-only branching, heterogeneous final
routes, fail-closed verification, and recursive promotion. It is not a novel
selector over fixed outputs.

Repeated Python34 and C++26 TOV-versus-semantic-free sessions have small,
uncertain mean differences. The Go sensitivity is positive but nonsignificant,
JavaScript49 is tied, and HumanEvalFix Python is a ceiling tie. Java164 supplies
a 1:0 prospective result for the revised completion-lock policy, but its task
test is nonsignificant. Natural-language TOV ledgers were not independently
annotated. Accordingly, the manuscript must not claim a repeatable standalone
semantic-relation effect, a universal 20-point overlap effect, or
population-level causal superiority of TOV over Generic.

The official LEET 20-case prompt-method screen and the earlier 40-task Aider
transfer are development evidence only. The legacy MMLU-Pro OJ3, Korean legal,
PSAT, Putnam, AIME, and other supplied experiments are historical evidence for
the broader Artichokes research program and are not pooled into the program-
repair paper's headline coding results.

## Compute and inference boundary

Every semantic call uses `gpt-5.6-luna` at medium reasoning, and each call
processes a whole track. Plain, ordinary repair, and Mini contain one, two, and
five nominal calls, respectively. Their large differences establish
effectiveness under the stated bounded-compute systems, not fixed-resource
efficiency. The equal-five-call comparator matches call count and hard caps but
not realized tokens or latency.

Task-level paired statistics condition on one realized whole-track trajectory
per arm. They are not cluster-robust evidence over independent model sessions
or language populations. The paper evaluates one model/runtime and does not
benchmark a full contemporary external repair agent under matched evaluator
access and compute.

## Integrity evidence

For JavaScript49 and HumanEvalFix Python164/Java164, all scored calls completed without retry
or replacement. Candidate evidence and anchors were byte-identical across final
routes; 126/126 and 492/492 route-by-anchor comparisons were exact. Directly
materialized unions were evaluated, and two post-result re-evaluations
reproduced the same JavaScript 47/49 task vector and both HumanEvalFix 164/164
stdout. Manifest audits found unique, non-nested task roots and no multiply
owned declared solution path. These checks support noninterference and
reproducibility; they do not enlarge the scientific claim.

## Required review discipline

- Use full denominators; unmapped outputs are wrong.
- Distinguish development, prospective, sensitivity-only, and runtime-deviating
  evidence.
- Report paired rescue/harm counts and exact tests, not unpaired tests.
- Do not turn nested additional-compute gains into efficiency or causal claims.
- Do not claim the coding system beats a full external SOTA agent.
- Do not infer that semantic overlap is true, causal, universal, or superior
  from a route tie or from verifier union.
- Preserve transport failures, forbidden artifacts, no-test rows, ceiling
  results, and protocol deviations in the record.
