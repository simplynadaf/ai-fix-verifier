#!/usr/bin/env python3
"""Nova Pro fixes one GitHub issue, opens/updates a PR, and the Proof Gate judges every commit.

This is the command the Kiro Crew job runs (`kirocrew cron add ... --command`).

  v1 (one-shot):        nova_pr.py --gh OWNER/REPO --clone DIR --issue 6
  v2 (gate in the loop): nova_pr.py --gh OWNER/REPO --clone DIR --issue 6 --gate-feedback --rounds 4

v2 continues on the SAME branch/PR: it starts from the gate's verdict on the current head, and
only the gate's VISIBLE findings are fed back. The hidden suite is never shown to the model.
Every round: commit -> push -> gate -> GitHub status + PR comment -> Proof Gate dashboard trial.
"""
import argparse, json, os, subprocess, sys, time, uuid, warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import boto3  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nova_fixer as nf  # noqa: E402
import nova_loop as nl  # noqa: E402
import github_gate as gg  # noqa: E402
gate = nl.gate

APP_DATA = Path(os.environ.get("PROOF_GATE_DATA", Path.home() / ".kiro/crew/apps/proof-gate/data"))


def say(kind, msg):
    """One structured, human-readable line per step (the video shows these)."""
    print(f"[{time.strftime('%H:%M:%S')}] {kind:<8} {msg}", flush=True)


def record_trial(res, label, arm, round_no, pr_url):
    """Write the verdict where the Proof Gate dashboard reads trials."""
    d = APP_DATA / "trials"; d.mkdir(parents=True, exist_ok=True)
    tid = uuid.uuid4().hex[:10]
    t = {"id": tid, "label": label, "arm": arm, "status": "done", "stage": "done", "created": time.time(),
         "stages": [{"stage": s, "detail": "", "t": 0} for s in ("export", "tamper", "pristine", "new_tests", "ground_truth", "done")],
         "pr_url": pr_url, "round": round_no, **res}
    (d / f"{tid}.json").write_text(json.dumps(t, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gh", required=True, help="OWNER/REPO on GitHub")
    ap.add_argument("--clone", required=True)
    ap.add_argument("--issue", type=int, required=True)
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--gate-feedback", action="store_true")
    ap.add_argument("--base", default="main")
    ap.add_argument("--candidates", type=int, default=1, help="candidate fixes per round; the gate keeps the best")
    a = ap.parse_args()
    repo = Path(a.clone).resolve()
    git = lambda *x: subprocess.run(["git", "-C", str(repo), *x], capture_output=True, text=True, check=True).stdout
    iss = json.loads(gg.gh("issue", "view", str(a.issue), "--repo", a.gh, "--json", "number,title,body"))
    branch = f"nova/issue-{a.issue}"
    version = ("v2 gate in the loop" + (f", {a.candidates} candidates" if a.candidates > 1 else "")) if a.gate_feedback else "v1 one-shot"
    say("ISSUE", f"#{iss['number']} {iss['title']}")
    say("AGENT", f"Amazon Nova Pro, {version}, up to {a.rounds} round(s)")

    git("fetch", "-q", "origin")
    git("checkout", "-q", a.base); git("reset", "-q", "--hard", f"origin/{a.base}")
    remote_has = subprocess.run(["git", "-C", str(repo), "ls-remote", "--exit-code", "--heads", "origin", branch],
                                capture_output=True).returncode == 0
    if remote_has and a.gate_feedback:
        git("checkout", "-q", "-B", branch, f"origin/{branch}")
        say("BRANCH", f"continuing {branch} (same PR)")
    else:
        git("checkout", "-q", "-B", branch)
        say("BRANCH", f"new branch {branch} from {a.base}")

    system = ("You are a senior Python engineer fixing ONE GitHub issue. Fix only this issue; do not touch anything else.\n"
              + (nl.LOOP_RULES if a.gate_feedback else "Make sure the tests pass.") + "\n" + nf.FORMAT)
    task = f"GitHub issue #{iss['number']}: {iss['title']}\n\n{iss['body']}\n\nHere is the repository:\n\n" + nf.repo_snapshot(repo)
    if remote_has and a.gate_feedback:
        head = git("rev-parse", "HEAD").strip()
        prev = gate.verify(str(repo), f"origin/{a.base}", head, nl.PY, nl.HIDDEN, 1, "previous attempt")
        task_feedback = nl.visible_feedback(prev, repo, head)
        # Start the new attempt from the base code (same branch, same PR): the rejected code is not reused,
        # only the gate's findings about it are.
        git("read-tree", "-u", "--reset", f"origin/{a.base}")
        task = (f"GitHub issue #{iss['number']}: {iss['title']}\n\n{iss['body']}\n\nHere is the repository:\n\n"
                + nf.repo_snapshot(repo)
                + "\n\nA previous attempt at this issue was REJECTED by the Proof Gate. Its findings:\n" + task_feedback)
        say("FEEDBACK", "rejected attempt reset; gate findings handed to Nova Pro")
    convo = [{"role": "user", "content": [{"text": task}]}]
    client = boto3.client("bedrock-runtime", region_name="us-east-1")
    pr_url = None
    from concurrent.futures import ThreadPoolExecutor

    def ask_one(temp):
        r = client.converse(modelId=nl.MODEL, system=[{"text": system}], messages=convo,
                            inferenceConfig={"maxTokens": 8000, "temperature": temp})
        return r["output"]["message"]["content"][0]["text"]

    def score(res):
        s = res["summary"]
        return (s["verdict"] == "TRUSTED", -len(s["reasons"]), s["verified"] or 0, -s["regressions"])

    start_tree = git("write-tree").strip()
    for rnd in range(1, a.rounds + 1):
        k = max(1, a.candidates)
        say("NOVA", f"round {rnd}: thinking ({k} candidate fix{'es' if k > 1 else ''})...")
        temps = [0.2] + [0.8] * (k - 1)
        with ThreadPoolExecutor(max_workers=k) as ex:
            raws = list(ex.map(ask_one, temps))
        trials = []
        for ci, raw in enumerate(raws, 1):
            try:
                out = nf.parse_reply(raw)
            except Exception:
                continue
            git("read-tree", "-u", "--reset", start_tree)
            for rel, content in out["files"].items():
                pth = nf.safe_target(repo, rel); pth.parent.mkdir(parents=True, exist_ok=True)
                pth.write_text(content if content.endswith("\n") else content + "\n")
            git("add", "-A")
            tree = git("write-tree").strip()
            sha = git("commit-tree", tree, "-p", "HEAD", "-m", f"candidate {ci}").strip()
            res = gate.verify(str(repo), f"origin/{a.base}", sha, nl.PY, nl.HIDDEN, out["claimed_fixes"], f"candidate {ci}")
            trials.append((score(res), ci, raw, out, tree, res))
            if k > 1:
                cs = res["summary"]
                say("CANDIDATE", f"round {rnd} #{ci}: {cs['verdict']}  regressions {cs['regressions']}  verified {cs['verified']}")
        if not trials:
            say("NOVA", f"round {rnd}: no parsable answer"); continue
        trials.sort(key=lambda t: t[0], reverse=True)
        _, ci, raw, out, tree, _ = trials[0]
        git("read-tree", "-u", "--reset", tree)
        say("NOVA", f"round {rnd}: keeping candidate #{ci}: changed {', '.join(out['files']) or 'nothing'}; claims {out['claimed_fixes']} fix(es)")
        subprocess.run(["git", "-C", str(repo), "commit", "-q", "--allow-empty", "-m",
                        f"Fix #{a.issue}: {iss['title']} (Nova Pro, {version}, round {rnd})"], capture_output=True)
        start_tree = git("write-tree").strip()
        git("push", "-q", "-f", "origin", branch)
        if pr_url is None:
            existing = json.loads(gg.gh("pr", "list", "--repo", a.gh, "--head", branch, "--json", "url,number"))
            if existing:
                pr_url, pr_no = existing[0]["url"], existing[0]["number"]
            else:
                pr_url = gg.gh("pr", "create", "--repo", a.gh, "--head", branch, "--base", a.base,
                               "--title", f"Fix #{a.issue}: {iss['title']}",
                               "--body", f"Fixes #{a.issue}\n\nOpened by an Amazon Nova Pro agent running as a Kiro Crew job. "
                                         f"Claim: {', '.join(out['fixes']) or 'see diff'}").strip()
                pr_no = int(pr_url.rstrip("/").split("/")[-1])
            say("PR", pr_url)
        head = git("rev-parse", "HEAD").strip()
        res = gate.verify(str(repo), f"origin/{a.base}", head, nl.PY, nl.HIDDEN, out["claimed_fixes"], f"PR #{pr_no}")
        res["head"] = head
        s = res["summary"]
        state = "success" if s["verdict"] == "TRUSTED" else "failure"
        gg.gh("api", f"repos/{a.gh}/statuses/{head}", "-f", f"state={state}", "-f", "context=Proof Gate",
              "-f", f"description={s['verdict']}: claimed {s['claimed']}, verified {s['verified']}"[:140])
        final_round = (not a.gate_feedback) or s["verdict"] == "TRUSTED" or rnd >= a.rounds
        if final_round:  # one visible comment per run: v1 rejected, v2 trusted (1 reject + 1 pass)
            gg.gh("pr", "comment", str(pr_no), "--repo", a.gh, "--body-file", "-", input_text=gg.comment_body(res, pr_no))
        record_trial(res, f"PR #{pr_no} issue #{a.issue}, {version}, round {rnd}", "V2" if a.gate_feedback else "V1", rnd, pr_url)
        say("GATE", f"round {rnd}: {s['verdict']}  claimed {s['claimed']}  verified {s['verified']}  "
                    f"regressions {s['regressions']}  " + ("; ".join(s["reasons"]) if s["reasons"] else "all checks passed"))
        if s["verdict"] == "TRUSTED" or not a.gate_feedback:
            break
        convo += [{"role": "assistant", "content": [{"text": raw}]},
                  {"role": "user", "content": [{"text": "The Proof Gate reviewed your change.\n\n" + nl.visible_feedback(res, repo, head)
                                                + "\n\nFix it and reply in the same format."}]}]
        say("FEEDBACK", "gate findings handed back to Nova Pro")
    say("DONE", f"{pr_url}  final verdict: {s['verdict']}")


if __name__ == "__main__":
    main()
