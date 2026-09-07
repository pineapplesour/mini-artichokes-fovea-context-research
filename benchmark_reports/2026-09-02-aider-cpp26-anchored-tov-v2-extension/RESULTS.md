# Aider C++26 anchored TOV-v2 extension

## Outcome

The unchanged anchored TOV-v2 policy solved 17/26 exercises on the complete
official Aider C++ track. It beat Plain by 13 tasks (+50.0 percentage points)
and matched generic verified-union adjudication by 3 tasks (+11.5 points),
with no harms. Every standalone extension gate was met.

| Arm | Correct | Accuracy | Agent seconds | Input / cached / output tokens |
|---|---:|---:|---:|---:|
| Plain | 4/26 | 15.4% | 382.375 | 817,539 / 760,320 / 16,255 |
| Graph | 8/26 | 30.8% | 518.188 | 1,732,124 / 1,644,544 / 20,981 |
| Ordinary repair | 13/26 | 50.0% | 263.285 | 780,696 / 713,216 / 11,459 |
| Generic verified union | 14/26 | 53.8% | 404.511 | 1,697,312 / 1,603,840 / 13,693 |
| **Anchored TOV v2** | **17/26** | **65.4%** | **439.527** | **2,415,795 / 2,284,288 / 17,807** |

The two final arms shared byte-identical candidate patches, outcomes, bounded
failure evidence, verified union, anchor map, model, effort, call cap, and one
final call. TOV spent 35.0 more agent seconds and 718,483 more input tokens in
this realization.

## Paired results

| TOV comparison | Rescues / harms | Difference | Exact p, one/two-sided | Paired bootstrap 95% CI |
|---|---:|---:|---:|---:|
| Plain | 13 / 0 | +13/26 (+50.0 pp) | .000122 / .000244 | [+30.8,+69.2] pp |
| Graph | 9 / 0 | +9/26 (+34.6 pp) | .001953 / .003906 | [+15.4,+53.8] pp |
| Ordinary repair | 4 / 0 | +4/26 (+15.4 pp) | .0625 / .125 | [+3.8,+30.8] pp |
| Generic verified union | 3 / 0 | +3/26 (+11.5 pp) | .125 / .250 | [0,+23.1] pp |

Bootstrap intervals use 200,000 paired resamples with seed `20260902`. The
three matched rescues were `complex-numbers`, `robot-name`, and `yacht`.

## Integrity

The pre-adjudication verified union contained 13 tasks and 26 solution files.
Post-run checks found zero anchor byte mismatches, byte-identical evidence and
anchor maps across final arms, exactly 13 ledger rows in unresolved-task order,
and zero forbidden changed paths in every arm.

The complete C++ build command configured each official exercise with
`EXERCISM_RUN_ALL_TESTS=1`; its `ALL` target compiled and ran the official Catch
tests. Starter code passed 0/26. This execution machinery is provenance, not a
scientific contribution.

## Receipts

- Protocol SHA-256:
  `c5ca6ee814926281b4a3cda08702f0081742742daa86cedace67c24548d1869d`
- Freeze SHA-256:
  `a3feff3bc378bf453c4f11d65221a9761c54b50333364350d0b9ca00da1e2e08`
- Runner SHA-256:
  `b9336d6a8503b0c41f9303a3241b0cc039f9c387c9ca1060484e15f37cb2fb93`
- Plain result SHA-256:
  `f58a5575b86d72a4492857175c58c3709af49708432874cc1ba575a1ae9b98f3`
- Graph result SHA-256:
  `fbd3e9c3b0db8856b22d88f33af3090edebe91a5b72e9636c04e775082ee0d86`
- Ordinary-repair result SHA-256:
  `10c53ec4c43a60d1e97c934963df6072f995792075e958bda8ef72f35009f2a9`
- Generic result SHA-256:
  `16e05e28d572bef811fc961bedc59fae4cd7161411fe90b90b600d29db0d9d6c`
- TOV result SHA-256:
  `f2f1f24ded5107b72eb4134221ae6189b1ad3dc1963921f843f4920fc186c50b`
- Decision-ledger SHA-256:
  `f1612f6ee2312c224593505201a2369330fc392f2adf4572903a49ef58c37f62`
