# ClassEval-Pro mixed Luna/Gemma E/O development

Status: terminal development result only; no paper, review, promotion, or fresh-confirmation claim.

## Run integrity

- Session `36189`, PID `2932315`, exit `0`; terminal `result.json` is authoritative:
  `status=complete`, `completed=total=300`, ordered IDs `ClassEval_0..299`, and
  `pairedTasks=32`. `error.json` is absent. The preserved `progress.json` still
  says `running/300`; that stale field is not used as the terminal status.
- The official denominator is 300: ordinary prefix passed 268 and U32 were run
  in both arms. No task subset or selective retry was used.
- Contract SHA-256:
  `59477124e357180843531eea2f0b4370495880f3d6994f2f9776d70c74fbe2c4`.
  Result SHA-256:
  `5442238ecccdd10ae1cf599641047f4d581be5fd2acaae63ce3f6eda85343292`.

## Scores and paired comparisons

| Full-300 vector | Passed |
|---|---:|
| ordinary parent | 268 |
| reused Luna-only E (`LL_E`) | 278 |
| reused Luna-only O (`LL_O`) | 278 |
| mixed E (`LG_E`) | 277 |
| mixed O (`LG_O`) | 278 |

Primary exact two-sided McNemar tests use all 300 tasks and Holm correction over
the two primary comparisons:

- `LG_O − LG_E`: rescue `ClassEval_153,191,241`; harm
  `ClassEval_239,295`; net `+1`; exact `p=1.0`, Holm-2 `p=1.0`.
- `LG_O − LL_E`: rescue `ClassEval_153,241,265`; harm
  `ClassEval_239,263,295`; net `0`; exact `p=1.0`, Holm-2 `p=1.0`.

Secondary `LG_O − LL_O` has rescue `ClassEval_191`, harm `ClassEval_286`,
net `0`, exact two-sided `p=1.0`. The predeclared advancement rule (net at
least four against each primary control, with no integrity failure) therefore
does not pass.

## Calls, receipts, evaluation, and cost scope

- Fresh physical model calls: `96/96` valid receipts: E/C Luna `32/32`, O/B
  Gemma `32/32` (`gemma-4-26b-a4b-it`, minimal, STOP, HTTP 200, model matched),
  and O/C Luna `32/32` (medium, exit 0, non-timeout, source-safe). No fresh
  model receipt was invalid.
- Receipt-summed durations (not end-to-end elapsed): E/C Luna `928.321263s`,
  O/B Gemma `1056.387230s`, O/C Luna `913.362203s`, combined `2898.070696s`.
- Actual current-run evaluator accounting is E canonical `96` + fresh raw
  `32` = `128`; O canonical `95` + fresh raw `64` = `159`; total `287`.
  Planned total was `288` (cache verification `96`, fresh raw `96`, fresh
  canonical `96`). Frozen `rawEvalCalls` is not used as current cost because it
  includes historical raw validity for cached candidates. O canonical count is
  `95` because the frozen O projection rejected one candidate on
  `ClassEval_239`; its O/B model receipt was valid, so this is not a transport
  invalidity. Cached candidate slots were E `64`, O `32`; planned cache
  verification evaluations were E `64`, O `32`.
- Luna usage for E/C + O/C: input `868562`, cached input `296704`, output
  `83411`, reasoning output `15441`, cache-write input `0`. Gemma O/B usage:
  prompt `138338`, candidate `44361`, total `182699`. The earlier minimal
  screen, high-thinking screen, and smoke calls are separate scopes.

Cached paths were byte/hash-bound and used exactly 32 times each: E/A from the
old E cache, E/B from the completed minimal screen, and O/A from the graph O
cache. Fresh paths were E/C Luna `32`, O/B Gemma `32`, and O/C Luna `32` under
this run root. The unchanged frozen selector/projection and full-300 inputs
were retained.

## Known benchmark-evaluation limitation and conclusion

The eight tasks `ClassEval_24,80,124,133,147,157,201,227` retain the same
declared-test-class inventory failure across the parent/old controls and new
arms, while their candidate receipts remain valid. Exact fatal strings are:
`Test09_PerformanceBehavior` for 24, 80, 133, 147, 157, 201; `Test07_AnalyticalComputation`
for 124; and `Test05_SpecialTokenHandling` for 227, each followed by
`ValueError: empty or duplicate declared test-class inventory`.
They remain in the denominator and are not removed or treated as model
invalidity. This mixed development result does not establish overlap or model
mix superiority and does not authorize another campaign.

Artifacts: [terminal run](../../runs/classeval-pro300-gemma-luna-paired-20260906-development-v1/),
[contract](../../runs/classeval-pro300-gemma-luna-paired-20260906-development-v1/contract.json),
[result](../../runs/classeval-pro300-gemma-luna-paired-20260906-development-v1/result.json),
[analysis.json](analysis.json).
