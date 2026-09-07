# Dependency-separator overlap: ClassEval-Pro full-300 development

Status: complete development evidence; not a fresh confirmation and not a paper or infrastructure claim.

- Run: `runs/classeval-pro300-dependency-separator-overlap-20260905-development-v1/`
- Terminal result: exit `0`, `complete`, `300/300`; result SHA `a658ed01393666ca4f397dd5add4d719f65837f4eb44da64fa3ffd70465964f5`; contract SHA `7f750454dfff52e5e4b39eece441714d90f6f1e1cb53b29b1523ffbfb909a7ad`.
- Model contract: `gpt-5.6-luna`, medium, 120 seconds; new O made exactly `96/96` valid, exit-0, non-timeout receipts. Raw evaluation calls `96`, canonical evaluation calls `96`, suite evaluations `192`.

## Primary full-300 comparison

| Arm | Passed |
|---|---:|
| E | 278/300 |
| D | 277/300 |
| New O | 278/300 |

- O−E: rescues `ClassEval_153,241,265,286`; harms `ClassEval_191,239,263,295`; net `0`, exact two-sided `p=1.0`, Holm-2 `p=1.0`.
- O−D: rescues `ClassEval_153,265,286`; harms `ClassEval_191,231`; net `+1/300` (`+0.333pp`), exact two-sided `p=1.0`, Holm-2 `p=1.0`.
- Every discordant task had nonempty `plan.shared`. The four S0/effective-D ordinary failures were `ClassEval_30,51,195,223`; all remained failures, so there was no S0-only win.

## Usage and cost scope

- New O receipt-summed usage: input `1,055,815`, cached input `413,696`, output `132,708`, reasoning output `32,715`; duration sum `2,879.965s` (not end-to-end elapsed).
- Scope distinctions: `629 = common533 + newO96` is a per-system branch count; full three-way E/D/new-O comparison is `821 = common533 + oldE96 + oldD96 + newO96`. Parent plus new graph is `635 = parent539 + newO96`; historical parent+old tail+new graph is `923 = 539+288+96`. Historical old O96 is outside the current E/D/new-O comparison.

The E/D controls were reused development artifacts. The result shows no statistically supported superiority; MAC remains 3/6 and no paper update or promotion follows.
