#!/usr/bin/env python3
"""Proof Gate on a GitHub pull request.

Fetches the PR head into a local clone, runs the gate (base = PR base), then posts:
  - a commit status `Proof Gate` (success / failure) on the PR head SHA, and
  - a PR comment with the verdict and every failed check.
Uses the authenticated `gh` CLI. Never merges, never approves.

  python3 github_gate.py --repo OWNER/NAME --pr N --clone DIR [--claimed N] [--hidden DIR] [--post]
"""
import argparse, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "proof-gate" / "backend"))
import gate  # noqa: E402

PY = str(ROOT / ".venv" / "bin" / "python")


def gh(*args, input_text=None):
    r = subprocess.run(["gh", *args], capture_output=True, text=True, input=input_text, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:3])} failed: {r.stderr[:300]}")
    return r.stdout


def comment_body(res: dict, pr: int) -> str:
    s, t = res["summary"], res["tamper"]
    ok = s["verdict"] == "TRUSTED"
    head = "### ✅ Proof Gate: TRUSTED" if ok else "### ❌ Proof Gate: REJECTED"
    rows = [
        ("Tamper scan", "pass" if not t["flagged"] else f"FAIL: edited {t['edited']} deleted {t['deleted']}"),
        ("Public API intact", "pass" if res.get("api", {}).get("intact", True) else "FAIL: removed " + ", ".join(n.split(":")[-1] for n in res["api"]["removed"])),
        ("Original tests on new code", f"{res['pristine']['passed']}/{res['pristine']['total']} pass"
         + ("" if not res["pristine"]["failures"] else f": FAIL {', '.join(f.split('::')[-1] for f in res['pristine']['failures'])}")),
        ("New tests RED then GREEN", f"{s['proven_tests']} proven of {len(res['new_tests'])} added"),
        ("Claim vs evidence", f"claimed {s['claimed']}, verified {s.get('verified', s['proven_tests'])}"),
    ]
    if s["false_positives"] is not None:
        rows.append(("Intentional behaviour", "intact" if not s["false_positives"] else f"FAIL: {s['false_positives']} broken"))
    table = "| Check | Result |\n|---|---|\n" + "\n".join(f"| {a} | {b} |" for a, b in rows)
    tests = "\n".join(f"- `{n['id'].split('::')[-1]}`: **{n['verdict']}** ({n['why']})" for n in res["new_tests"]) or "- none added"
    reasons = "" if ok else "\n**Why it was rejected**\n" + "\n".join(f"- {r}" for r in s["reasons"]) + "\n"
    return (f"{head}\n\nThe agent proposes. Python decides. No model graded this PR.\n\n{table}\n{reasons}"
            f"\n**Tests the agent added**\n{tests}\n\n<sub>Proof Gate for Kiro Crew · commit `{res['head'][:8]}`</sub>")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--pr", type=int, required=True)
    ap.add_argument("--clone", required=True, help="local clone of the repo")
    ap.add_argument("--claimed", type=int)
    ap.add_argument("--hidden", default=str(ROOT / "harness" / "hidden"))
    ap.add_argument("--post", action="store_true", help="post the status + comment to GitHub")
    a = ap.parse_args()
    pr = json.loads(gh("pr", "view", str(a.pr), "--repo", a.repo, "--json", "headRefName,headRefOid,baseRefName,title"))
    clone = Path(a.clone)
    subprocess.run(["git", "-C", str(clone), "fetch", "-q", "origin",
                    f"+refs/heads/{pr['baseRefName']}:refs/remotes/origin/{pr['baseRefName']}",
                    f"+refs/pull/{a.pr}/head:refs/remotes/origin/pr-{a.pr}"], check=True)
    base, head = f"origin/{pr['baseRefName']}", f"origin/pr-{a.pr}"
    res = gate.verify(str(clone), base, head, PY, a.hidden, a.claimed, pr["title"])
    res["head"] = pr["headRefOid"]
    s = res["summary"]
    print(json.dumps({"pr": a.pr, "sha": pr["headRefOid"][:8], **s}))
    if a.post:
        state = "success" if s["verdict"] == "TRUSTED" else "failure"
        desc = (f"{s['verdict']}: claimed {s['claimed']}, verified {s['real_fixes'] if s['real_fixes'] is not None else s['proven_tests']}")[:140]
        gh("api", f"repos/{a.repo}/statuses/{pr['headRefOid']}", "-f", f"state={state}",
           "-f", "context=Proof Gate", "-f", f"description={desc}")
        gh("pr", "comment", str(a.pr), "--repo", a.repo, "--body-file", "-", input_text=comment_body(res, a.pr))
        print("posted status + comment")


if __name__ == "__main__":
    main()
