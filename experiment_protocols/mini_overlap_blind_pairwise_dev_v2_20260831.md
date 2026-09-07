# Mini/Universal Artichoke blind pairwise falsification — development v2

## Status and scientific boundary

This document freezes a new **result-aware development** arm before its only
semantic model invocation.  It is not a confirmatory experiment: the source
questions, candidates, V3 decisions, and prior development scores are known to
the research process.  Any accuracy estimate or p-value from this arm is a
development diagnostic and cannot support the paper's final superiority claim.

The scientific question is unchanged from development v1:

> When two separately sampled Luna candidates agree on a canonical option
> different from a stronger incumbent, can a provenance-blind, symmetric
> falsification certificate distinguish useful corrections from harmful ones
> better than raw majority and the role-exposed V3 verifier?

Hashing, isolation, parsing, receipts, and validators are evidence-quality
controls only.  They are not scientific contributions or performance results.

## Prior-arm disposition fixed before scoring

The v1 campaign at
`runs/mini-overlap-confirm1-dev-v6-blind-pairwise-20260831` completed one Luna
invocation, but it was rejected before private labels or policy accuracy were
opened.  Two output-independent contract defects caused that disposition:

1. all 78 `TIE` certificates with an unresolved side used a reasonable but
   unstated uniqueness interpretation that the validator rejected; and
2. the inherited JSONL trace parser treated JSON-valid U+0085 characters
   inside strings as record boundaries, yielding false invalid-line counts.

V6 remains immutable and is not silently repaired, resumed, retried, combined,
or scored.  Its certificates, preferences, prose, and trace are not present in
the V7 model-mounted input.  V7 changes only the public logical contract and
trace parsing needed to resolve those defects:

- `BOTH_PLAUSIBLE` now requires two `SUPPORTED` sides;
- `NEITHER_PLAUSIBLE` now requires two `REFUTED` sides;
- if either side is `UNRESOLVED`, uniqueness must be `UNRESOLVED` and the
  preference must be `TIE`; and
- U+0085, U+2028, and U+2029 are escaped only for the legacy trace-audit view,
  while LF remains the sole JSONL record delimiter and malformed ASCII control
  characters still fail closed.  The original trace remains byte-identical and
  hash-bound; separator counts are recorded in the run receipt.  The runner,
  gold-free combiner, and private analyzer all use the same LF-only record
  interpretation.

The policy definitions, private analysis order, promotion thresholds, model,
and compute limits below are unchanged from development v1.

## Frozen source evidence

- Strict source campaign:
  `runs/mini-overlap-confirm1-dev-v3-20260831`
- Source protocol: `mini_artichokes_candidate_overlap_adjudication_v2`
- Source freeze SHA-256:
  `45d03ecb89c67242e0f98bf522afb524dd758b04f57bd0ab00e71b8909b39ae7`
- Source question SHA-256:
  `f2d92bbdd6f0ea30693dcd70ff1846f5c0b2fe50e42f1e71705a398cc0ad9d5e`
- Source overlap-manifest SHA-256:
  `cc3f6130dfcec8326562b1cb3a3f6137502b9bb583a6c8e1965c5906823db5ca`
- Frozen candidate-answer SHA-256 values:
  - d1/base: `6f4e50d3e9901b10fbb4cd8db0d7d5e835a234bf63196efe303d8163e6536c95`
  - d3/auxiliary_1: `64b6ac1eda02333ed53f2c3e3c15928533e8af559dde18411697e03937d4bd48`
  - d4/auxiliary_2: `954ba0407d86fa0dc307271b62b45c635409cc78dc995fd225208c5a2459dd1e`
- Collision-safe eligible-ID SHA-256:
  `c5fe505dde1c2422dbc9eefc2c71859fe7ccbb801eb372ca1d9e0f789dc69f29`

The three source candidates are distinct, accepted, complete-file,
one-invocation `gpt-5.6-luna/high/low/default` artifacts over the same public
question freeze.  Their historical role choice makes this arm developmental.

## Frozen V7 campaign

- Campaign:
  `runs/mini-overlap-confirm1-dev-v7-blind-pairwise-v2-20260831`
- Protocol: `mini_artichokes_blind_pairwise_veto_v2`
- Preparation code checkpoint: `4c135b5`
- Freeze SHA-256:
  `48e6db7da53a7333f63556d700a19b83b70a0f3ba694a3e9c2e320231f86f1e5`
- Public questions SHA-256:
  `fe2ce02ae76cff2c59b1f09fd43740a2b4f1254ae590ce1b2519c386c41e079c`
- Candidate pairs SHA-256:
  `cda9fb0f27cb49d4774db052c7ffde4933f1b7905292aaa915a21f223d11bfb8`
- Expected-certificate file SHA-256:
  `c16ca537687d1e7a94a9f57fb64e7f0fc26138445ad48c500d309a67cbea22c3`
- Instructions SHA-256:
  `031d83bf6f2d7789425af4d6a6b05f4ccc87b38d9a49d3acd3b6c087d1949ad3`
- Hidden role mapping SHA-256:
  `9ed8bec3f5c96423109162324bc23a3232d76165010957d53cc1177c85f0b7d3`
- Hidden rotation control SHA-256:
  `441cf15a72590b4275545cc9bf8c9bddc7e844fc895a44f9b6f69770d454bb09`
- Rotation-seed SHA-256:
  `d4d4579730d439a986d289a359c65c24433f175881473585da9af77ecd2370ff`
- Inventory: 1,309 questions; 247 canonical MCQ conflicts; incumbent on
  LEFT 128 times and RIGHT 119 times.

The model sees only the four files under `veto/input/`.  It receives no private
label, correct option, candidate provenance, third auxiliary, agreement count,
V3 decision or reason, prior blind output, historical score, rotation seed, or
role mapping.  LEFT/RIGHT orientation is deterministic and hidden.

The blind certificate and trace-audit protocol is v2.  The unchanged
deterministic rotation scheme remains
`sha256-domain-seed-nul-id-low-bit-v1`, and the downstream fixed four-policy
combination schema remains `mini_artichokes_blind_pairwise_veto_combination_v1`;
these version labels describe distinct layers rather than a fallback to V1.

## Frozen invocation and no-retry rule

Exactly one complete-file semantic invocation is allowed:

- authentication: `CODEX_HOME=/home/pineapple/.codex-new-account`
- model: `gpt-5.6-luna`
- reasoning effort: `high`
- verbosity: `low`
- service tier: `default`
- native web search: disabled
- database, skills, MCP, apps, memory, and multi-agent: disabled
- local shell: staged input/output file management only
- outbound network-capable shell commands: prohibited and trace-audited
- runner timeout: 900 seconds
- development-promotion runtime ceiling: 650 seconds

The process timeout preserves a complete diagnostic artifact; it does not
relax the promotion ceiling.  A timeout, malformed output, policy violation,
second thread, partial ledger, or hash mismatch is preserved as incomplete.
There is no same-campaign repair or retry.

## Frozen certificate and action contract

The verifier must produce one ordered certificate for each of the 247
conflicts.  It sees only LEFT and RIGHT and must test both symmetrically.  Each
side requires an atomic claim, falsification test and outcome, strongest
countercase and outcome, and a tagged evidence receipt.  The certificate also
records question polarity, uniqueness, preference, and a comparative reason.

Resolved preference requires one `SUPPORTED` and one `REFUTED` candidate.
Ambiguous or unsupported evidence yields `TIE`.  `MODEL_KNOWLEDGE` is a
transparent model assertion, not externally verified evidence.  Validation
therefore establishes schema and structural consistency, not external factual
truth, semantic correctness of the declared polarity, or entailment from an
evidence receipt to the atomic claim.

After acceptance, the gold-free combiner must publish four complete policies
using exact d1 or d3 answers only:

1. `base`: never switch;
2. `blind_only`: switch iff the hidden-role interpretation prefers d3;
3. `intersection`: switch iff both V3 `VALID+SWITCH` and blind preference favor
   d3; and
4. `union`: switch iff either V3 or blind preference favors d3.

`TIE`, missing, malformed, or inconsistent evidence cannot authorize a blind
switch.  The combiner has no private-label access and no synthesis path.

## Frozen analysis order and private cohort

The order is mandatory:

1. complete and hash the sole V7 invocation;
2. rerun certificate, trace, isolation, and receipt validation;
3. publish and hash all four policies without private data;
4. verify policy files and their self-hashed combination receipt; and
5. only then open the frozen private registry and score.

The fixed cohort contains every public MCQ row with a nonempty private
`correctOptionId`; missing or unmapped answers count as wrong.

- M = 941
- sorted M-ID SHA-256:
  `2e46b0c759c185ed743d1109da1095f17643ebdd3c45bc4a30b08edbeb2b4047`
- private registry SHA-256:
  `b761dbcc274b034bfcc13c666b79e0235d8d6d092d2f53e9cc5343fc86c712f3`

Known development references are d1 566/941; raw three-draft majority 484/941
with 39 rescues and 121 harms; existing Universal adjudicator 503/941; and V3
587/941 with 30 rescues, 9 harms, and 15 wrong-to-wrong switches.  A private
`pass@3` oracle may be reported only as a non-deployable ceiling.

## Frozen metrics and development selection

For each policy report full-cohort accuracy, switch and unmapped counts,
rescue, harm, wrong-to-wrong, correct-to-correct, net rescue minus harm,
per-domain deltas, exact one- and two-sided McNemar diagnostics versus d1, and
paired discordance versus V3.

Only `blind_only`, `intersection`, and `union` are promotion candidates.  A
policy is eligible only when all of the following hold:

1. every source, freeze, implementation, isolation, trace, receipt,
   certificate, combination, answer, ID, and order audit passes;
2. score is at least 588/941, strictly above V3's 587;
3. net rescue minus harm is at least 22;
4. harm is at most 4 and at most `floor(rescue/4)`;
5. one-sided exact McNemar p versus d1 is at most .05;
6. no frozen benchmark domain has a negative absolute score delta versus d1;
7. verifier elapsed time is at most 650 seconds.

Tie-breaking is highest score, then lowest harm, then fewer switches, then the
fixed priority `intersection`, `blind_only`, `union`.  Raw majority and the
oracle are never selectable.  Screening three reused-data policies means the
development p-values are not confirmatory or multiplicity-adjusted claims.

If no policy is selected, preserve V7 as an ablation and precommit the next
challenger.  That disposition does not terminate the broader research goal.

## Required confirmation before publication

Any promoted mechanism must be frozen and evaluated once on a fresh,
case-level/source-disjoint sealed reserve with newly sampled candidates and no
result-aware role choice.  Under the same Luna snapshot, the confirmatory
comparison must include one-call Luna, equal-call direct sampling or
self-consistency, a generic verifier/reranker using the same candidates and
adjudicator-call budget, and the proposed overlap-gated system.  Calls,
input/output/total tokens, latency, and coverage must be reported.  Primary
paired tests and multiplicity control must be fixed before reserve labels are
opened.
