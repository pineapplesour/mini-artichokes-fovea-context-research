# Full ClassEval-Pro300 code-output comparison, v2

Inherit the complete scientific protocol and constraints of
`2026-09-05-classeval-text-overlap-v1.md`, frozen at46d5f53. The ONLY change is
an identical output-format instruction in all generation and repair prompts:
write every def signature on one line, with self/cls on the same line where
applicable. Keep model, effort,120-second cap, full300 inventory, source
operator,16-trial cap, shared-identical-repair rule and evaluation unchanged.

Reason: the author's line-based staticmethod preprocessing interprets
`def __init__(` without self on that physical line as a static method. In
textv1 ClassEval_0/A and repair-0, the original valid Python multiline
initializer had no decorator, but the submitted author-preprocessed program
had an added @staticmethod and failed construction. This is a formatting
compatibility issue, not a discovered task-specific answer or algorithm win.
Do not remove or patch the author preprocessor or official tests. Do not fix
returned code on the host. A model that ignores the common formatting
instruction remains subject to the unchanged evaluation.

Textv1 session11125 was stoppedexit130, after3 completed tasks (all final
systems2/3); ClassEval_3/B was interrupted. Preserve every initiated call and
partial outcome, including7 initiated calls /6 completed receipts. Do not
rescore, reuse or count any v1 answers as part of this fresh full300 v2.
Old nativev2 session34880 is separately closedexit130 after23/300, all
composition policies13/23, Plain10/23,37 initiated calls /36 receipts with
14 timeouts. Neither incomplete run is a full benchmark result.

This remains development. No added scientific claim, model change, scoring
leniency or permission to select a subset follows from this compatibility fix.
