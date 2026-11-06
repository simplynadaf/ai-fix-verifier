# Proof Gate for Kiro Crew

A Kiro Crew app that checks an AI agent's pull request with evidence instead of opinions.

An agent says "I fixed 3 bugs". Proof Gate runs deterministic Python on the commit and reports how many of those fixes it can actually vouch for. No model grades the model.

This repo has everything from the video: the Kiro Crew app, a script job that runs **Amazon Nova Pro** on a real GitHub issue, and the research data behind the numbers.

Demo target (public, 8 issues with planted bugs): https://github.com/simplynadaf/ledgerlite

## What the gate checks

For each commit, in order:

| Check | What fails it |
|-------|---------------|
| Tamper scan | Existing tests edited, deleted or weakened |
| Public API intact | A public function the project had is gone |
| Original tests on the new code | Any original test that passed before and fails now (a regression) |
| New tests, RED on old / GREEN on new | A test the agent wrote that does not fail on the old code (a vacuous test) |
| Claim vs evidence | The agent claimed N fixes. Verified = fixes proven by a RED to GREEN test AND confirmed by a hidden suite the agent never sees |

Verdict is `TRUSTED`, `REJECTED` or `NO CHANGE`. The same result is posted to the PR as a `Proof Gate` commit status plus a comment.

## Layout

```
proof-gate/   the Kiro Crew app (backend, dashboard UI, agent, skill)
crons/        nova_fixer_job.py, the Kiro Crew script job that runs the agent
harness/      Nova Pro fixer, feedback loop, PR pipeline, hidden test suite
research/     scoreboard and the loop sweep behind the numbers in the video
```

## Run it

Requirements: Kiro Crew, Python 3.11, `gh` logged in, AWS credentials with Bedrock access to `amazon.nova-pro-v1:0` in us-east-1.

```bash
git clone https://github.com/simplynadaf/kirocrew-proof-gate ~/kirocrew-proof-gate
cd ~/kirocrew-proof-gate
python3.11 -m venv .venv && .venv/bin/pip install pytest==8.3.4   # the gate's interpreter
mkdir -p work && gh repo fork simplynadaf/ledgerlite --clone=false   # or use your own target repo

# install the app, then enable it in Kiro Crew > Apps > Library
kirocrew app install ./proof-gate

# the agent is a script job. Its message is its config.
mkdir -p ~/.kiro/crew/crons && cp crons/nova_fixer_job.py ~/.kiro/crew/crons/
export PROOF_GATE_HOME=~/kirocrew-proof-gate
kirocrew cron add nova-fixer '{"issue": 6}' \
  --script ~/.kiro/crew/crons/nova_fixer_job.py:run --every 604800 --timeout 900 --timeout-secs 1200
```

Run the job from the Kiro Crew Schedule page. It clones the repo, asks Nova Pro for a fix, pushes a branch, opens a PR, runs the gate and posts the check.

Config keys: `issue`, `repo`, `gate_feedback` (hand the gate's visible findings back to the model), `rounds`, `candidates` (best-of-N per round).

The video's second run changes the job with:

```bash
kirocrew cron update <id> --message '{"issue": 6, "gate_feedback": true, "rounds": 4, "candidates": 3}'
kirocrew learn add "Every fix ships with a test that fails first. Never break an original test."
```

## Honest numbers

Nova Pro is not magic and the gate does not make it so.

- One-shot on the 8 issues: 4 passed, the rest were rejected.
- With the gate's findings fed back, up to 4 rounds: issue 6 converged in 9 of 12 runs, issue 4 in only 2 of 8.
- `candidates: 3` (best of three per round) made issue 6 reliable in my runs. It does not fix issue 4.
- The sample is small and the target repo is tiny. Treat these as a demonstration of the gate, not a benchmark of the model.
- The hidden suite lives in `harness/hidden/`. It is published here so you can reproduce the run. If you want a blind evaluation, write your own and keep it private.

Why this matters: an empirical study of agent-authored fix PRs (arXiv 2602.00164) found failing tests among the most common reasons they are never merged.

## License

MIT
