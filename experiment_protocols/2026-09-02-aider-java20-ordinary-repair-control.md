# Frozen extension: generic repair control for five Java20 sessions

Status: frozen after the v6 MAC-n-CHEESE review and before any
`ordinary_repair` call or outcome in the five sessions below.

## Review-triggered question

Does the bundled matched structured-repair prompt improve over a short generic
second-pass repair instruction when both receive the identical session-specific
Graph patch, original task packet, and complete official failure stdout?

This is the smallest direct response to the review question asking for a
compute-matched generic repair control. It adds exactly five Luna/medium calls
and no new benchmark or execution machinery. Because the matched-repair
outcomes were already known when this control was commissioned, the comparison
is a secondary diagnostic rather than a fresh confirmatory treatment test.

## Frozen inputs and control

- Official source: `Aider-AI/polyglot-benchmark` commit
  `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`.
- Java20 benchmark freeze SHA-256:
  `b12e7d7a4904084b35cae8bca1f492d9173a46d7ee6c8dcfe8165cd3a27111c0`.
- Public task SHA-256:
  `69e2e1d2220ff21651d7ac266ab0828695a769c4740dbc2b85baa0b0a9981942`.
- Arm runner SHA-256:
  `e0a51ce1c743f74760eb7f7c47104299d2ac1564b34e9e86d6594ca2a5a8236a`.
- Frozen ordinary-repair lead SHA-256:
  `cabf19eddd71ce33835cda1419c849684cb7c4becabd9ce23f018368eeba2951`.
- Frozen scorer SHA-256:
  `4a0447c816738f6619a7eafe23a83ee3f07036992ce86b12911409e331aee430`.
- Model and effort: `gpt-5.6-luna`, medium.
- Each arm costs one repair call after Graph; official test source and gold
  implementations remain hidden.

The generic control instruction is the pre-existing `ORDINARY_REPAIR` constant
in the frozen runner:

```text
This is an ordinary second-pass test-feedback repair baseline. Continue from
the frozen Graph implementation. Use the supplied official failure output to
fix every failing task, without changing tasks that passed unless required by
a shared concrete defect. Edit only listed solution files. The hidden tests
remain unavailable.
```

The five immutable Graph result SHA-256 values, in session order, are:

1. `4efe9488b9fe066269ceb4d68818e27b0d5f791ab3eddca478bf0c278d2d6834`
2. `935b4ba75fe6eef794608ec6d4667e66516d0766eb423bb3ac2361407c660db9`
3. `0a1d2e24691ba746e8d42eae9ef1793f2ea767a4df10ada20e13fe98966cc65f`
4. `96b953366f3da9f39518bd9c9ee23680d5ac3be70fdbce00af86690cb50cc6f4`
5. `90d3980b1d5dad62401e228bf97e78b71d6539c0922e198dbcb82a7646719a38`

## Frozen execution and analysis

Run one `ordinary_repair` arm in each existing session root, in session order
1 through 5. No rerun, top-up, prompt change, task deletion, or additional
control session is allowed. An unsafe, incomplete, or timed-out call remains
in the denominator as 0/20.

Report matched and ordinary correct counts for every session. The predeclared
contrast is matched structured repair minus ordinary repair. Report positive,
tied, and negative session differences; exact one- and two-sided sign tests;
mean and median percentage-point differences; a paired whole-session bootstrap
interval; repeated task-session rescues and harms; and full control-call cost.

Regardless of the numerical result:

- do not call the comparison confirmatory, because matched outcomes were known;
- do not treat the repeated 100 task-session outcomes as independent tasks;
- do not attribute any difference to a single structured component; and
- do not treat run or scoring machinery as a paper contribution.
