"""Kiro Crew job: an Amazon Nova Pro agent fixes one GitHub issue and opens a PR.
The Proof Gate judges every commit and posts a GitHub status check.

The job's message is its config (JSON), so `kirocrew cron update --message` changes behaviour:
  {"issue": 6}                                  v1: one-shot
  {"issue": 6, "gate_feedback": true, "rounds": 4, "candidates": 3}
      v2: the gate's findings go back to the agent; it tries 3 fixes per round, the gate keeps the proven one
"""
import os
import json
import subprocess
from pathlib import Path

DEMO = Path(os.environ.get("PROOF_GATE_HOME", Path.home() / "kirocrew-proof-gate"))  # the clone of this repo
LOG = DEMO / "work/nova-fixer.log"


def run(ctx):
    cfg = json.loads(ctx.message or "{}")
    argv = ["python3", str(DEMO / "harness/nova_pr.py"), "--gh", cfg.get("repo", "simplynadaf/ledgerlite"),
            "--clone", str(DEMO / "work/ledgerlite"), "--issue", str(int(cfg.get("issue", 6))),
            "--rounds", str(int(cfg.get("rounds", 1)))]
    if cfg.get("gate_feedback"):
        argv.append("--gate-feedback")
    if cfg.get("candidates"):
        argv += ["--candidates", str(int(cfg["candidates"]))]
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as log:
        log.write(f"\n===== kirocrew job: nova-fixer  config {json.dumps(cfg)} =====\n"); log.flush()
        proc = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, text=True, timeout=900)
    tail = [l for l in LOG.read_text().splitlines() if "DONE" in l or "GATE" in l][-1:]
    ctx.notify(f"nova-fixer finished (exit {proc.returncode}): " + (tail[0] if tail else "no verdict"))
