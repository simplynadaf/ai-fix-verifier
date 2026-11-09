<div align="center">

<img src="docs/github-cover.png" alt="AI Fix Verifier: an AI agent opens a pull request claiming a fix, a deterministic Python gate reads the commit and decides REJECTED or TRUSTED. No test weakened, no regression, and the fix is backed by a test that fails first and passes after. Powered by Amazon Nova Pro as a Kiro Crew job." width="100%" />

# 🛡️ AI Fix Verifier checks whether your AI agent actually fixed the bug

### An AI agent says "fixed it" and opens a pull request. This gate reads the commit, not the promise: it checks that no test was weakened, no function was deleted, nothing regressed, and that the fix is backed by a test which fails on the old code and passes on the new. Deterministic Python decides. No model grades the model. The result posts straight to your PR as a status check.

[![Amazon Nova Pro](https://img.shields.io/badge/Agent-Amazon%20Nova%20Pro-FF9900?logo=amazon&logoColor=white)](https://aws.amazon.com/bedrock/nova/)
[![Kiro Crew](https://img.shields.io/badge/Runs%20in-Kiro%20Crew-8b5cf6)](https://kiro.dev)
[![Deterministic](https://img.shields.io/badge/Verdict-deterministic%20Python-38bdf8)](#-what-the-gate-checks)
[![No LLM judge](https://img.shields.io/badge/No%20model%20grades%20the%20model-2fd27a)](#-the-rule-it-never-bends)
[![License: MIT](https://img.shields.io/badge/License-MIT-8b5cf6)](LICENSE)

[![Watch the demo](https://img.shields.io/badge/▶%20Watch%20the%20live%20demo-FF0000?logo=youtube&logoColor=white)](#-links)

> ### Most agent tools stop at "the tests passed". AI Fix Verifier asks the harder question: did the agent prove the fix, or just claim it? Then it rejects or trusts the PR, with the evidence on the table.

[What It Does](#-what-it-does) · [See It Decide](#-see-it-decide) · [What the Gate Checks](#-what-the-gate-checks) · [How It Works](#-how-it-works) · [Honest Numbers](#-honest-numbers) · [Getting Started](#-getting-started)

</div>

---

## 🤔 What It Does

An AI coding agent opens a pull request and says it fixed the bug. You cannot see, at a glance, whether it really did. It might have edited a test to make it pass, deleted the function that was failing, broken something else, or written a test that would have passed anyway.

AI Fix Verifier treats the agent's "I fixed it" as a claim to be checked, not a fact. For every commit it runs deterministic Python over the code and reports how many of the claimed fixes it can actually vouch for. The verdict, `TRUSTED` or `REJECTED`, is posted to the pull request as a commit status named `Proof Gate` plus a comment with the full table.

> The key idea: **the agent proposes, Python decides.** An LLM never grades another LLM's work here.

This repo is the whole thing from the demo: the Kiro Crew app that runs the gate, a Kiro Crew job that runs an **Amazon Nova Pro** agent on a real GitHub issue, and the research data behind the numbers.

---

## 👀 See It Decide

The agent ran twice on the same issue and the same pull request. The gate posted a different verdict each time, straight to GitHub.

<div align="center">

**Run 1, one shot: REJECTED.** The agent's change made an existing test fail, and it proved nothing. 1 fix claimed, 0 verified.

<img src="docs/screenshots/pr-comment-rejected.png" alt="GitHub PR comment: Proof Gate REJECTED. A table shows tamper scan pass, public API intact pass, original tests 16/17 pass with one failure, new tests 0 proven of 0 added, claimed 1 verified 0. Reasons: 1 original test fails on the new code." width="760" />

**Run 2, same PR, after gate feedback and best-of-3 candidates: TRUSTED.** Every check green, and the fix is backed by a test that failed on the old code. 1 claimed, 1 verified.

<img src="docs/screenshots/pr-comment-trusted.png" alt="GitHub PR comment: Proof Gate TRUSTED. The table shows all checks pass, 17/17 original tests, 1 proven of 3 added, claimed 1 verified 1. The three tests the agent added are listed, two vacuous and one proven." width="760" />

</div>

The Kiro Crew dashboard shows both verdicts at once, live from the app:

<div align="center">
<img src="docs/screenshots/dashboard-both.png" alt="Proof Gate dashboard: a stat bar reading Trials 2, Rejected 1, Claimed vs Verified 2 of 1. A Version 1 card is rejected with 0 verified of 1 claimed at 0 percent precision; a Version 2 card is trusted with 1 verified of 1 claimed at 100 percent precision. A detail panel lists every check and the hidden ground-truth cells." width="860" />
</div>

---

## 🔍 What the Gate Checks

For every commit, in order. Any failure makes the verdict `REJECTED`.

| ✅ Check | ❌ What fails it |
|---|---|
| 🧪 **Tamper scan** | An existing test was edited, deleted, or weakened to make it pass |
| 🧩 **Public API intact** | A public function the project had is now gone (the agent once "fixed" a bug by deleting the function) |
| 🔁 **No regressions** | An original test that passed before fails on the new code |
| 🔴🟢 **Tests fail first** | A test the agent wrote passes on the OLD code too, so it proves no bug existed (a vacuous test) |
| 🎯 **Claim vs evidence** | The agent claimed N fixes, but fewer are proven by a red-to-green test AND confirmed by a hidden suite it never sees |

Verdict is `TRUSTED`, `REJECTED`, or `NO CHANGE`.

---

## 🧠 How It Works

<div align="center">
<img src="docs/architecture.png" alt="Architecture: a GitHub issue goes to Amazon Nova Pro, which edits the code, writes tests and opens a pull request (the proposal). Proof Gate runs deterministic Python checks on the commit (the verdict): tamper scan, public API intact, no regressions, tests fail first, claim vs proof confirmed by a hidden suite. Rejected on the first one-shot run, trusted on the same PR after feedback and best-of-3 candidates." width="860" />
</div>

```
 🧑‍💻  A GitHub issue (one real bug, handed to the agent one at a time)
        │
        ▼
 🤖  Amazon Nova Pro  (amazon.nova-pro-v1:0, Bedrock, a Kiro Crew job)   the PROPOSAL
        │   reads the issue, edits code, writes tests, pushes a branch, opens a PR
        ▼
 🛡️  Proof Gate  (deterministic Python, no LLM judge)                    the VERDICT
        │   tamper scan · public API intact · no regressions
        │   new tests must fail on old code and pass on new
        │   verified = min(hidden-suite real fixes, proven red-to-green tests)
        ▼
 📊  commit status "Proof Gate" + a comment on the PR  →  TRUSTED or REJECTED
        │   if rejected, the visible findings are fed back and the agent tries again
        ▼
 ♻️  next round: best-of-3 candidate fixes, the gate keeps the best, until trusted or out of rounds
```

- **`proof-gate/`** is the Kiro Crew app: a Python backend, a dashboard page, an agent and a skill. It runs the checks, stores every trial, and posts the GitHub status.
- **`crons/nova_fixer_job.py`** is the Kiro Crew script job. Its message is its config: `{"issue": 6, "gate_feedback": true, "rounds": 4, "candidates": 3}`.
- **`harness/`** holds the Nova Pro fixer, the feedback loop, the PR pipeline, and the hidden test suite the agent never sees.

---

## 🚫 The Rule It Never Bends

**The agent proposes. Python decides. No model grades the model.** Every verdict comes from running real tests and inspecting real code, in `harness/github_gate.py` and the gate module. An LLM is never asked whether another LLM did a good job. "Verified" means two independent things agreed: a test the agent wrote went from red to green, and a hidden suite the agent never sees confirms the bug is actually fixed. When those disagree, the fix is not counted.

---

## 📊 Honest Numbers

This is not magic, and the gate does not make the agent better. It makes the agent honest.

- One-shot on the 8 planted-bug issues: **4 passed, the rest were rejected.**
- With the gate's findings fed back, up to 4 rounds, best-of-3 candidates per round:
  - issue 6 converged in **9 of 12 runs** in my tests
  - issue 4 converged in **2 of 8**
- Best-of-3 candidates helped reliability more than extra rounds. It did not rescue issue 4.

The sample is small and the target repo is tiny. Treat these as a demonstration of the gate, not a benchmark of the model. A 2026 empirical study of agent-authored fix PRs ([arXiv 2602.00164](https://arxiv.org/abs/2602.00164)) found failing tests among the most common reasons they are never merged, which is the gap this gate closes before a human ever looks.

---

## 🧱 Tech Stack

| Component | Technology |
|---|---|
| 🤖 The agent | **Amazon Nova Pro** (`amazon.nova-pro-v1:0`), Amazon Bedrock, us-east-1 |
| ⚙️ The runner | **Kiro Crew** script job, config passed as the job message |
| 🛡️ The gate | Deterministic **Python** + **pytest 8.3.4** in a pinned venv, no LLM judge |
| 🔗 Integration | GitHub commit status + PR comment via the `gh` CLI |
| 🎯 The target | `ledgerlite`, a tiny money/date library with 8 planted bugs, each filed as an issue |

---

## 🚀 Getting Started

Requirements: Kiro Crew, Python 3.11, `gh` logged in, AWS credentials with Bedrock access to `amazon.nova-pro-v1:0` in us-east-1.

```bash
git clone https://github.com/simplynadaf/ai-fix-verifier ~/ai-fix-verifier
cd ~/ai-fix-verifier
python3.11 -m venv .venv && .venv/bin/pip install pytest==8.3.4   # the gate's interpreter
mkdir -p work && gh repo fork simplynadaf/ledgerlite --clone=false # or point at your own target repo

# install the app, then enable it in Kiro Crew > Apps > Library
kirocrew app install ./proof-gate

# the agent is a Kiro Crew script job; its message is its config
mkdir -p ~/.kiro/crew/crons && cp crons/nova_fixer_job.py ~/.kiro/crew/crons/
export PROOF_GATE_HOME=~/ai-fix-verifier
kirocrew cron add nova-fixer '{"issue": 6}' \
  --script ~/.kiro/crew/crons/nova_fixer_job.py:run --every 604800 --timeout 900 --timeout-secs 1200
```

Run the job from the Kiro Crew Schedule page. It clones the repo, asks Nova Pro for a fix, pushes a branch, opens a PR, runs the gate, and posts the check.

To put the gate in the loop (the second run in the demo):

```bash
kirocrew cron update <id> --message '{"issue": 6, "gate_feedback": true, "rounds": 4, "candidates": 3}'
```

---

## 📁 Project Structure

```
ai-fix-verifier/
├── README.md
├── LICENSE                     # MIT
├── proof-gate/                 # the Kiro Crew app (backend, dashboard UI, agent, skill)
├── crons/
│   └── nova_fixer_job.py       # the Kiro Crew script job that runs Amazon Nova Pro
├── harness/
│   ├── nova_fixer.py           # Nova Pro fixer: delimited reply, claimed fixes
│   ├── nova_loop.py            # the gate-feedback loop and visible findings
│   ├── nova_pr.py              # the PR pipeline (branch, push, PR, gate, status)
│   ├── github_gate.py          # ★ the deterministic checks + the GitHub comment
│   ├── issues.json             # the 8 planted-bug issues
│   └── hidden/                 # the hidden test suite (published here so you can reproduce)
├── research/                   # the loop sweep behind the honest numbers
└── docs/                       # cover, architecture diagram, screenshots
```

---

## 🧾 An Honest Take

**What is genuinely strong**
- The verdict is deterministic. No LLM is asked to grade another LLM.
- The gate catches the ways agents game weak checks: deleted functions, weakened tests, vacuous tests.
- "Verified" needs two independent signals to agree, and the PR comment shows exactly which tests were proven and which were vacuous.

**Honest limits**
- The convergence numbers come from small samples on a tiny repo, mixing a few configurations. They demonstrate the gate; they are not a model benchmark.
- The hidden test suite is published in this repo so you can reproduce the run. For a blind evaluation, write your own and keep it private.
- Catalog of planted bugs is deliberately small and simple.

---

## ❓ FAQ

**Does an LLM decide the verdict?**
No. The verdict is pure Python running tests and inspecting code. Amazon Nova Pro only proposes the fix.

**What does "verified" mean?**
A fix is verified only when a test the agent wrote fails on the old code and passes on the new, AND a hidden suite the agent never sees confirms the bug is fixed. Both must agree.

**Is this production-ready?**
It is a working demonstration. The checks are real and the GitHub integration is real, but the target repo and the bug set are small on purpose.

**Can I use my own repo and my own agent?**
Yes. Point the job at your repo, and swap the agent in `harness/nova_fixer.py`. The gate does not care which model proposed the change.

---

## 🔗 Links

- 🛡️ This repo: https://github.com/simplynadaf/ai-fix-verifier
- 🐞 Demo target with the issues: https://github.com/simplynadaf/ledgerlite
- ▶️ Demo video: a live walk-through of a PR going from rejected to trusted (synthetic AI voiceover; disclosed)

---

## 📝 License

MIT. See [LICENSE](LICENSE).

---

<div align="center">

## 👨‍💻 Author

**Sarvar Nadaf** · Cloud Architect · AI Infrastructure & DevOps

[Portfolio](https://sarvarnadaf.com) · [LinkedIn](https://www.linkedin.com/in/sarvar04/) · [GitHub](https://github.com/simplynadaf) · [Dev.to](https://dev.to/sarvar_04) · [YouTube](https://www.youtube.com/@sarvar-nadaf) · [AWS Builder Center](https://builder.aws.com/community/@sarvar)

*The agent proposes. Python decides. No model grades the model.*

**If this made you trust an AI pull request a little less blindly, consider a ⭐**

</div>
