# Aider90 online-freeze versus offline-portfolio ablation: invalid pre-analysis stop

The frozen Aider90 control protocol stopped after the two Rust30 calls, before
Python34 or C++26 began.  Neither Rust score is eligible for a matched-method
comparison.

The new runner exposed
`/home/pineapple/.rustup/toolchains/stable-x86_64-unknown-linux-gnu` to both
offline calls.  The historical online calls did not receive this toolchain
binding.  Thus tool availability was not matched.  In addition, the offline
overlap call ran Cargo and left 30 unallowlisted `Cargo.lock` files, producing
`safe=false`.  The frozen protocol required a stop on any integrity failure.

For audit only, the semantic-free and overlap outputs scored 22/30 and 24/30,
respectively.  These values must not be pooled with or contrasted against the
historical online results.  There was no retry, cleanup, selective top-up, or
replacement under the stopped protocol.  A separate protocol tests the same
mechanism on complete Python34 and C++26 tracks whose original tool exposure
can be matched exactly.

Frozen protocol SHA-256:
`85e196601ba1253b9666fb37894b7ff64d4c09b31e7738437f112dd625f75ee0`.

Rust semantic-free result SHA-256:
`f47f4049c5d09be4730d2b4cc9e1f16d9b947be39dcd39ba5e7f11e6f68dd0b8`.

Rust overlap result SHA-256:
`b14157fc765ee9cc42453d77347cca0f579bded578b9f30a32181e24617faf22`.

This is an execution-validity record, not a paper contribution or a scientific
result.
