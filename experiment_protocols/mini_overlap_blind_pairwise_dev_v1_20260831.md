# Mini/Universal Artichoke blind pairwise falsification — development v1

## Status and scientific boundary

This document freezes a **result-aware development** experiment before its
single semantic model invocation.  The questions, three candidate artifacts,
V3 decisions, and their private performance were already inspected while
developing the mechanism.  Consequently, every accuracy estimate and p-value
from this arm is a development diagnostic.  It cannot serve as confirmation,
regardless of effect size.

The scientific question is narrower than an infrastructure claim:

> When two separately sampled Luna candidates agree on a canonical option
> different from a stronger incumbent, can a provenance-blind, symmetric
> falsification certificate distinguish useful corrections from harmful ones
> better than raw candidate majority and the existing role-exposed V3
> verifier?

Hashes, isolation, ledgers, and validators are evidence-quality controls only.
They are not research contributions or performance outcomes.

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
- Frozen candidates d1/d3/d4:
  - d1: `6f4e50d3e9901b10fbb4cd8db0d7d5e835a234bf63196efe303d8163e6536c95`
  - d3: `64b6ac1eda02333ed53f2c3e3c15928533e8af559dde18411697e03937d4bd48`
  - d4: `954ba0407d86fa0dc307271b62b45c635409cc78dc995fd225208c5a2459dd1e`
- Collision-safe eligible-ID SHA-256:
  `c5fe505dde1c2422dbc9eefc2c71859fe7ccbb801eb372ca1d9e0f789dc69f29`
- V3 receipt/answers/decisions/trace SHA-256:
  - `8d52c3082c313cae26516b6faf38553a636bdffea708c9e3a2365e843a0ac99e`
  - `c03291e2fe58a365306433059e0201298a7b4faf25f652b113f0361ad5c03c84`
  - `59e217ebeae26fe4d0e3ce5faa75a2c4282cbf8d62f75abdc11263779b8b1eff`
  - `84450113ed71b50641045b3e020d0e35a65872360a7b5ee260accc4baf821ae4`

The three source candidates are distinct, accepted, complete-file,
one-invocation `gpt-5.6-luna/high/low/default` artifacts over the same public
question freeze.  Their role assignment is historical and therefore not
confirmatory.

## Frozen blind campaign

- Campaign:
  `runs/mini-overlap-confirm1-dev-v6-blind-pairwise-20260831`
- Protocol: `mini_artichokes_blind_pairwise_veto_v1`
- Freeze SHA-256:
  `3bfe5d0f5bb3a8a18878be86797c0f9a8b4bb6f33a5cb7729269e3e5c02268b5`
- Public questions SHA-256:
  `fe2ce02ae76cff2c59b1f09fd43740a2b4f1254ae590ce1b2519c386c41e079c`
- Candidate-pairs SHA-256:
  `7634f48afd775de0dbe420e3379034bfa9e6b95028ee03f68183cb8281c695b2`
- Expected-certificate file SHA-256:
  `c16ca537687d1e7a94a9f57fb64e7f0fc26138445ad48c500d309a67cbea22c3`
- Instructions SHA-256:
  `7983e94a0b189376f5e1181cfae0eef105948bc5c7eae493c8064650480bd9f5`
- Hidden role-mapping SHA-256:
  `53c06297afdbee0cf7221f885c33aa3eab96900adadd5ecd243a3d91ffbee001`
- Hidden rotation-control SHA-256:
  `2fe16534348d177bfd94a0520968a3473ba044e1f9c357353d272a17b342afd7`
- Rotation-seed SHA-256:
  `c34c953aacfb304b7941a05126355b3a4542b4341c35d71ea1f6ed6ab25a6981`
- Inventory: 1,309 questions; 247 canonical MCQ conflicts; incumbent on
  LEFT 134 times and RIGHT 113 times.
- Code checkpoint at preparation: `f33ce5e` (with runner network audit in
  `3e401cc` and gold-free combiner in `7b641ab`).

The model-mounted input contains only the four public files in `veto/input/`.
It contains no private label, correct option, source role, third auxiliary,
agreement count, V3 decision/reason, historical score, or control seed.  Each
ID's LEFT/RIGHT orientation is deterministic but hidden from the model.

## Frozen invocation

Exactly one complete-file semantic invocation is allowed:

- authentication source: `CODEX_HOME=/home/pineapple/.codex-new-account`
- model: `gpt-5.6-luna`
- reasoning effort: `high`
- verbosity: `low`
- service tier: `default`
- native web search: disabled
- database, skills, MCP, apps, memory, and multi-agent: disabled
- local shell: limited to staged input/output file management
- outbound network-capable shell commands: prohibited and trace-audited
- runner timeout: 900 seconds
- development-promotion runtime ceiling: 650 seconds

The longer process timeout preserves a completed diagnostic artifact if the
certificate is slow; it does not relax the 650-second promotion ceiling.  A
timeout, malformed output, policy violation, second thread, partial ledger,
or implementation/input hash mismatch is preserved as incomplete and is not
silently repaired or retried under this campaign.

## Frozen certificate and action contract

The verifier must issue one ordered certificate for every one of the 247
conflicts.  It sees only LEFT and RIGHT.  For both candidates it must state an
atomic claim, a falsification test, the outcome, the strongest countercase,
and a tagged evidence receipt.  It must also quote the requested question
polarity and establish whether exactly one candidate remains suitable.

Resolved preference requires one candidate to be `SUPPORTED` and the other
`REFUTED`; ambiguous, unsupported, or internally inconsistent cases are
`TIE`.  `MODEL_KNOWLEDGE` receipts are transparent model assertions, not
externally verified evidence.  Structural validation therefore establishes
contract compliance, not factual truth.

After an accepted certificate is sealed, the gold-free combiner publishes
four full 1,309-row policies, copying only exact d1 or d3 answers:

1. `base`: never switch.
2. `blind_only`: switch iff the hidden-role interpretation of the blind
   certificate prefers d3.
3. `intersection`: switch iff V3 records `VALID+SWITCH` **and** the blind
   certificate prefers d3.
4. `union`: switch iff either V3 records `VALID+SWITCH` or the blind
   certificate prefers d3.

`TIE`, malformed, missing, or inconsistent evidence never authorizes a blind
switch.  The combiner has no gold access and no synthesis path.

## Frozen analysis order and cohort

The order is mandatory:

1. finish and hash the one blind invocation;
2. rerun strict certificate and trace validation;
3. mechanically publish and hash all four policies without private data;
4. verify the combination receipt and policy files;
5. only then open the frozen private registry and score.

The denominator is the same sorted fixed cohort used for V3: every public MCQ
row with a nonempty private `correctOptionId`; missing or unmapped answers are
wrong.

- M = 941
- sorted M-ID SHA-256:
  `2e46b0c759c185ed743d1109da1095f17643ebdd3c45bc4a30b08edbeb2b4047`
- private registry SHA-256:
  `b761dbcc274b034bfcc13c666b79e0235d8d6d092d2f53e9cc5343fc86c712f3`

Known result-aware development references on M are:

- d1 base: 566/941;
- raw three-draft canonical majority (switch all 247 d3=d4 conflicts):
  484/941, with 39 rescues and 121 harms;
- existing Universal adjudicator: 503/941;
- V3 strict verifier: 587/941, with 30 rescues, 9 harms, and 15
  wrong-to-wrong switches.

The analyzer also reports the private-gold `pass@3` oracle ceiling, clearly
labelled non-deployable and excluded from policy selection.

## Metrics and fixed development selection

For each derived policy report full-cohort accuracy, switch count, unmapped
count, rescue (base wrong to policy correct), harm (base correct to policy
wrong), wrong-to-wrong, correct-to-correct, net rescue minus harm, per-domain
deltas, and exact one- and two-sided McNemar diagnostics versus d1.  Also
report paired discordance versus V3.

Only `blind_only`, `intersection`, and `union` are development-promotion
candidates.  A policy is eligible only if every condition holds:

1. all source, freeze, implementation, isolation, trace, receipt,
   certificate, combination, answer, ID, and order audits pass;
2. score is at least 588/941, strictly above V3's 587;
3. net rescue minus harm is at least 22;
4. harm is at most 4;
5. harm is at most `floor(rescue/4)`;
6. one-sided exact McNemar p versus d1 is at most .05;
7. no frozen benchmark domain has a negative absolute score delta versus d1;
8. blind verifier elapsed time is at most 650 seconds.

If several policies satisfy all conditions, select highest score, then lowest
harm, then fewer switches, then the fixed priority `intersection`,
`blind_only`, `union`.  Candidate majority and the oracle ceiling are never
promotion candidates.  Because three policies are screened on reused data,
these p-values do not support a confirmatory or multiplicity-adjusted paper
claim; the selected mechanism, if any, must be frozen and tested once on a
new source-disjoint reserve.

If no policy is selected, preserve the arm as an accuracy/safety/mechanism
ablation and continue with the next precommitted challenger.  This disposition
does not terminate the broader research goal.

## Required successor before publication claims

Any promoted mechanism must be rebuilt for a fresh, case-level-disjoint,
sealed benchmark with new candidate sampling and no result-aware role choice.
The confirmatory comparison must include the same Luna snapshot and explicit
budget accounting against: one-call Luna, equal-call direct sampling or
self-consistency, and a generic verifier/reranker using the same candidates
and adjudicator-call budget.  Calls, input/output/total tokens, latency, and
coverage must all be reported.  Primary paired tests and multiplicity control
must be fixed before opening that reserve's labels.
