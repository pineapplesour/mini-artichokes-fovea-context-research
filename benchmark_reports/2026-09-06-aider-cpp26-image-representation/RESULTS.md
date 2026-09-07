# Aider C++26 image-representation assay — terminal record

## Terminal status

- Run root: runs/aider-cpp26-image-representation-20260906-development-v1/
- Driver command: python -m tools.run_aider_cpp26_image_representation --run-root runs/aider-cpp26-image-representation-20260906-development-v1 --execute
- Driver PID 2155965, owned exec session 97466, exited 0.
- result.json status=complete; plannedSessions=12, recordedSessions=12; operationalComplete=true, inventoryComplete=true, integrityValid=true.
- Every session evaluated the same 26 ordered task IDs (count=26, unique=true, complete=true). No task selection, retry, or omission was used.
- This is an official-test-feedback development assay. It is not a sealed held-out end-to-end test, an image-only cognition test, or a paper/superiority result. Both arms retain the same original-source lookup opportunity; image source-read records are best-effort exposure evidence only.

## Frozen contract

- Freeze commit: 07d513269ff956466014a6122f63c9e0b7c89430; source commit: 7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f.
- Model: gpt-5.6-luna, medium effort; agent cap 900 s; evaluator cap 1800 s; named paired permission profile; 41 image pages / 51,417 image text characters.
- Fresh whole-track sessions: T1,T2 text and I1,I2 image. Reconciliation order and policy order were fixed as TT_G,TT_O,II_O,II_G,TIa_O,TIa_G,TIb_G,TIb_O.
- Pair-input package hashes were preserved across each G/O pair: TT=fa7708f6873bffff805c142f81af9e713d40f6a6bc31793b651b7a584bcd148f, II=b638c8cfca791265ed5bacb4ac13c2eec9dbc322921d57bb0a125558e08d5625, TIa=f8bded60702604a1c9fa8013bcd3adf88fc7291326be6bb55ecc96c264b3f0ec, TIb=f1875cd26a55427eb9b0d7e77768890792b9d48c89229b75ccb6809871c347db.

All 12 sessions had agent exit 0, agentTimedOut=false, evaluator exit 1 (normal nonzero outcome for failing benchmark tasks), evaluatorTimedOut=false, observed usage, full evaluator inventory, scopeValid=true, integrity.valid=true, no forbidden files, and matching immutable-file/anchor hashes.

## Scores, time, and observed usage

| session | passed/26 | agent s | evaluator s | input | cached input | output | reasoning |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 5 | 363.638 | 266.043 | 560,447 | 515,840 | 15,874 | 3,130 |
| T2 | 3 | 412.072 | 247.241 | 837,020 | 776,192 | 17,253 | 3,175 |
| I1 | 7 | 610.462 | 305.271 | 3,855,983 | 3,683,328 | 21,994 | 3,305 |
| I2 | 6 | 635.639 | 286.938 | 2,872,248 | 2,711,040 | 17,727 | 2,480 |
| TT_G | 17 | 487.293 | 317.690 | 2,459,562 | 2,336,512 | 19,651 | 3,344 |
| TT_O | 14 | 522.126 | 227.365 | 2,836,752 | 2,718,464 | 21,888 | 3,267 |
| II_O | 15 | 437.524 | 238.090 | 1,720,369 | 1,625,856 | 18,848 | 3,226 |
| II_G | 11 | 408.977 | 216.391 | 2,402,702 | 2,296,832 | 16,851 | 3,162 |
| TIa_O | 13 | 372.005 | 215.730 | 771,889 | 714,752 | 16,548 | 2,625 |
| TIa_G | 15 | 488.906 | 251.054 | 3,147,361 | 3,034,368 | 19,896 | 4,101 |
| TIb_G | 8 | 498.322 | 190.987 | 1,171,327 | 1,050,368 | 20,997 | 2,768 |
| TIb_O | 13 | 511.995 | 237.030 | 2,627,989 | 2,507,520 | 21,223 | 4,482 |
| **sum** | — | **5,748.958** | **2,999.830** | **25,263,649** | **23,971,072** | **228,750** | **39,065** |

cache_write_input_tokens=0. Duration totals are sums of per-session agent/evaluator durations, not end-to-end wall-clock time. No currency cost is available in the recorded contract; token usage is reported exactly as observed.

## Full 26-task vectors

The bit positions below are the authoritative result.json order:

01 aider-cpp/all-your-base; 02 aider-cpp/allergies; 03 aider-cpp/bank-account; 04 aider-cpp/binary-search-tree; 05 aider-cpp/circular-buffer; 06 aider-cpp/clock; 07 aider-cpp/complex-numbers; 08 aider-cpp/crypto-square; 09 aider-cpp/diamond; 10 aider-cpp/dnd-character; 11 aider-cpp/gigasecond; 12 aider-cpp/grade-school; 13 aider-cpp/kindergarten-garden; 14 aider-cpp/knapsack; 15 aider-cpp/linked-list; 16 aider-cpp/meetup; 17 aider-cpp/parallel-letter-frequency; 18 aider-cpp/perfect-numbers; 19 aider-cpp/phone-number; 20 aider-cpp/queen-attack; 21 aider-cpp/robot-name; 22 aider-cpp/space-age; 23 aider-cpp/spiral-matrix; 24 aider-cpp/sublist; 25 aider-cpp/yacht; 26 aider-cpp/zebra-puzzle.

Each vector is a 26-character 0/1 string in that order:

| session | vector | count |
|---|---|---:|
| T1 | 00000010010001100100000000 | 5 |
| T2 | 00000000000001100000000001 | 3 |
| I1 | 00100000100100100000011001 | 7 |
| I2 | 00000000000101100000111000 | 6 |
| TT_G | 00101011110011100110111111 | 17 |
| TT_O | 00101010110001101110010111 | 14 |
| II_O | 01101000100111101110011011 | 15 |
| II_G | 00100000100101100110111001 | 11 |
| TIa_O | 00101010110101100100111001 | 13 |
| TIa_G | 01100010110101100110111011 | 15 |
| TIb_G | 00100000100101100000011001 | 8 |
| TIb_O | 00100000100111101100011111 | 13 |

## Predeclared gate and paired contrasts

| pair | G | O | O−G count | rescues (O=1,G=0) | harms (O=0,G=1) |
|---|---:|---:|---:|---|---|
| TT | 17 | 14 | -3 | parallel-letter-frequency | crypto-square, kindergarten-garden, robot-name, spiral-matrix |
| II | 11 | 15 | +4 | allergies, circular-buffer, kindergarten-garden, parallel-letter-frequency, yacht | robot-name |
| TIa | 15 | 13 | -2 | circular-buffer | allergies, phone-number, yacht |
| TIb | 8 | 13 | +5 | kindergarten-garden, parallel-letter-frequency, perfect-numbers, sublist, yacht | none |

The predeclared integer/fraction calculations are:

- dTI = (-2 + 5) / 52 = 3/52 = 0.0576923, below the required 2/26.
- dHomogeneous = (-3 + 4) / 52 = 1/52 = 0.0192308.
- Interaction I = dTI - dHomogeneous = 2/52 = 1/26 = 0.0384615, meeting the interaction threshold exactly.
- Mixed O mean is (13+13)/52 = 0.5000000; homogeneous O means are TT=14/26=0.5384615 and II=15/26=0.5769231. Mixed O is below both.
- Therefore dTIAtLeast2Over26=false, interactionAtLeast1Over26=true, mixedONotBelowHomogeneous=false, and the development advanceGate.eligible=false.

This is a development gate, not a significance claim. No per-task iid p-values, paper update, promotion, or automatic follow-up is justified by this run.

## Artifact and interpretation boundary

Authoritative raw result: runs/aider-cpp26-image-representation-20260906-development-v1/result.json. Progress/process monitoring artifacts remain preserved. The campaign is operationally and integrally complete, but the declared scientific advance gate failed; the result does not establish image-representation or overlap superiority.
