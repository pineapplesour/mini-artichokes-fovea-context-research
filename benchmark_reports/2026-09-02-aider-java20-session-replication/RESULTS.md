# Aider Java20 five-session replication

## Result

On one frozen official Aider Java20 hidden-test set, the matched structured
second pass outperformed both direct Luna and Graph alone in all five newly
initialized whole-batch sessions. The prior Java pilot was excluded from all
confirmatory tests.

| New session | Plain | Graph | Matched repair | Matched - Plain | Matched - Graph |
|---:|---:|---:|---:|---:|---:|
| 1 | 4/20 | 1/20 | **5/20** | +1 task (+5 pp) | +4 tasks (+20 pp) |
| 2 | 2/20 | 2/20 | **6/20** | +4 tasks (+20 pp) | +4 tasks (+20 pp) |
| 3 | 2/20 | 3/20 | **6/20** | +4 tasks (+20 pp) | +3 tasks (+15 pp) |
| 4 | 2/20 | 3/20 | **4/20** | +2 tasks (+10 pp) | +1 task (+5 pp) |
| 5 | 2/20 | 2/20 | **4/20** | +2 tasks (+10 pp) | +2 tasks (+10 pp) |

The predeclared fixed-sequence tests both rejected at one-sided alpha .05:

- Versus Plain: five positive, zero tied, and zero negative session
  differences; exact one-sided sign-test `p=.03125`; mean difference +13
  percentage points, median +10, paired whole-session bootstrap 95% CI
  [+8,+18].
- Versus Graph: five positive, zero tied, and zero negative session
  differences; exact one-sided sign-test `p=.03125`; mean difference +14
  percentage points, median +15, paired whole-session bootstrap 95% CI
  [+9,+19].

Across the repeated task-session outcomes, matched repair produced 15 rescues
and 2 harms relative to Plain (net +13/100) and 15 rescues and 1 harm relative
to Graph (net +14/100). These are descriptive counts, not 100 independent
tasks, because the same 20 tasks recur in every session.

## Confirmatory interpretation

The independently initialized whole-batch session is the inferential unit.
The result establishes repeatability of the complete structured-repair policy
on this fixed official Java20 set. It does not establish performance on new
tasks, full Aider-leaderboard superiority, or a causal contribution from
overlap metadata. Matched repair is a bundled second pass using a frozen Graph
patch, official failure output, counterexample construction, preservation,
and a double completion audit.

The machinery that ran and scored the experiment is provenance only. It is
not a scientific contribution.

## Compute boundary

Across the five new sessions, Plain used 2,056.922 agent seconds, 3,869,510
input tokens, and 84,137 output tokens. Graph used 2,430.984 seconds,
4,690,002 input tokens, and 99,608 output tokens. The matched repair calls
alone used 1,975.104 seconds, 6,557,770 input tokens, and 78,114 output tokens.
The complete proposed path is Graph plus matched repair: 4,406.088 agent
seconds, 11,247,772 input tokens, and 177,722 output tokens. It is a
quality-oriented two-call policy, not an efficiency improvement.

## Frozen receipts

- Protocol SHA-256:
  `d26ce9ce1896cd5c144559425efafcf37b9f6128d5482f22436fbd029a6ca072`
- Scorer SHA-256:
  `9bfc70b60899c2dc0f205b9d2e484a3d3dd82499db5db50c280d8274bfb1fbe5`
- Result SHA-256:
  `75eb1d868b5d5663b77d5730107b01e91f372fb4d58d180caef812e7c7b7be9b`
- Benchmark freeze SHA-256:
  `b12e7d7a4904084b35cae8bca1f492d9173a46d7ee6c8dcfe8165cd3a27111c0`
- Public task SHA-256:
  `69e2e1d2220ff21651d7ac266ab0828695a769c4740dbc2b85baa0b0a9981942`
- Private evaluator SHA-256:
  `997e254b413c4ca248cf68162541843a9a92c0c561539649ab3fc9d681d1475c`

## Review-triggered generic-repair control

After the matched-repair results and v6 MAC-n-CHEESE review were known, we
froze and added exactly one short ordinary-repair call to each of the same five
Graph sessions. Both repair arms therefore received the identical
session-specific Graph patch, original task packet, and official failure
stdout. Because the control was added after the matched outcomes were known,
this is a secondary diagnostic rather than a fresh confirmatory contrast.

| Session | Matched structured repair | Ordinary repair | Matched - ordinary |
|---:|---:|---:|---:|
| 1 | 5/20 | 4/20 | +1 |
| 2 | 6/20 | 6/20 | 0 |
| 3 | 6/20 | 8/20 | -2 |
| 4 | 4/20 | 4/20 | 0 |
| 5 | 4/20 | 5/20 | -1 |

Matched repair did not outperform ordinary repair: session differences were
`[+1,0,-2,0,-1]`, with one positive, two ties, and two negative sessions;
mean -2 percentage points, median 0, paired whole-session bootstrap 95% CI
[-7,+2], one-sided exact sign `p=.875`, and two-sided `p=1.0`. Repeated
task-session accounting gave 3 matched rescues and 5 harms (net -2/100).

Ordinary repair totaled 27/100 repeated outcomes versus matched repair's
25/100. As an unplanned descriptive check, ordinary repair averaged +15 points
over Plain (four positive sessions and one tie; sign `p=.0625`) and +16 over
Graph (five positive sessions; `p=.03125`). These comparisons reinforce the
narrow end-to-end interpretation: a separate call using real failure feedback
is the supported coding mechanism at this resolution. The explicit structured
operations did not add measurable value over a short generic repair prompt,
and no individual repair component is identified as causal.

The five ordinary calls used 2,378.479 agent seconds, 9,000,911 input tokens,
and 91,415 output tokens. Their cost is reported, not claimed as an efficiency
or execution contribution.

Frozen extension receipts:

- Protocol SHA-256:
  `9bd15311378024d798ceef3e1b26ad90135d791f94b852551153b904984de95d`
- Scorer SHA-256:
  `4a0447c816738f6619a7eafe23a83ee3f07036992ce86b12911409e331aee430`
- Result SHA-256:
  `2f9240417643e193e932d8979052ab137e5450808dbd42e0b6040913d0e03676`
