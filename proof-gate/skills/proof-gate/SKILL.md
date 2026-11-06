---
name: proof-gate
description: Evidence-first bug fixing. Use when asked to fix bugs, audit a repo, or claim that something is fixed. Every fix needs a test that fails before and passes after; existing tests are never edited; intentional behaviour is never "fixed".
always: false
triggers: fix bugs, find bugs, audit this repo, proof gate, prove the fix
---

# Proof Gate: fix bugs with evidence, not confidence

An agent's word is not evidence. This skill is the discipline the Proof Gate app checks for.

## The loop, per bug
1. Read the code. Name the suspected bug in one sentence.
2. Write a NEW test in a NEW file under `tests/` that exposes it. Run it. It must FAIL (RED).
   - A test that passes on the old code proves nothing and will be marked `vacuous`.
   - A test that errors (import error) instead of failing is `invalid`.
3. Fix the code with the smallest change. Run the new test. It must PASS (GREEN).
4. Run the whole suite. Nothing that passed before may fail now.

## Never
- Edit, delete, skip, `xfail` or weaken an existing test. The gate re-runs the ORIGINAL tests on your new code, so this can only hurt you.
- "Fix" code whose comment says it is intentional, policy-required, or by design. Those are decoys, not bugs.
- Claim a fix you did not prove with a failing test.

## Final report format
```
FIXED: <n>
- <bug> -> proven by tests/<file>::<test>
NOT FIXED:
- <thing> -> <reason>
```

## How the Proof Gate judges you
1. Tamper scan: edits or deletions of existing tests, removed assertions, added skips.
2. Pristine run: the original tests against your new code.
3. New-test proof: RED twice on the old code, GREEN on the new.
4. Ground truth: a hidden suite you never see, for real fixes and for intentional behaviour you broke.
