# SC3 all-valid boundary audit

## Question

The manuscript's original sentence that SC3 differs from D1 "exactly on
eligible conflicts" was too broad. GJ3/OJ3 eligibility requires all D1-D3
answers to map successfully, whereas ordinary three-vote SC3 can return the
valid D2/D3 majority when D1 is invalid.

## Frozen audit result

The already accepted raw outputs for both MMLU-Pro cohorts were audited after
the first Review Court report. No model call, remapping, retry, row deletion,
or score change was made.

| Cohort | D1 invalid, D2/D3 valid and agreeing | IDs | Consensus correct | D1 correct under frozen scoring |
|---|---:|---|---:|---:|
| Confirmation 1 | 0 | none | 0 | 0 |
| Replication 2 | 2 | `mmlu-pro-06430`; `mmlu-pro-01180` | 0/2 | 0/2 |

SC3 selected the D2/D3 consensus on both replication-2 rows. Both selections
were wrong, while invalid D1 was also wrong by the frozen full-denominator
scoring rule. A hypothetical SC3 variant gated on all-three validity would
therefore have exactly the same correctness vector as reported SC3 on these
two rows and the same aggregate accuracy and paired statistics everywhere.

## Claim boundary

- The 68 reported GJ3/OJ3 conflict rows remain exactly the frozen all-valid
  event `D2 = D3 != D1`.
- SC3 has 56 output differences from D1 in replication 2: 54 all-valid
  eligible conflicts plus the two boundary rows above.
- This audit corrects the method description; it does not create performance
  evidence or alter any headline result.
