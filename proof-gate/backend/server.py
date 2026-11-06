#!/usr/bin/env python3
"""Proof Gate backend. Stdlib only. Runs as its own process; the gateway reverse-proxies to it.

  GET  /health            unsigned (the gateway probe has no credential)
  GET  /config            demo defaults (repo, python, hidden suite, arms)
  PUT  /config            update defaults
  GET  /trials            summaries, newest first
  GET  /trials/<id>       full verdict + live stage
  POST /trials            start one verification  {label, repo, base, head, python, hidden?, claimed?}
  POST /batch             start every arm listed in config.arms
  POST /reset             delete all stored trials
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import gate

PORT = int(os.environ.get("PORT", 9170))
APP = os.environ.get("KIROCREW_APP_NAME", "proof-gate")
HOME = Path(os.environ.get("KIROCREW_HOME", Path.home() / ".kiro" / "crew"))
DATA = Path(os.environ.get("PROOF_GATE_DATA", HOME / "apps" / APP / "data"))
TRIALS = DATA / "trials"
TRIALS.mkdir(parents=True, exist_ok=True)
SECRET = os.environ.get("KIROCREW_PROXY_SECRET", "")
USER_HOME = Path.home().resolve()
LOCK = threading.Lock()


def verify_proxy(header: str, method: str, target: str, body: bytes) -> bool:
    """Same HMAC the gateway signs every forwarded request with. Fails closed."""
    if not SECRET or not header or ":" not in header:
        return False
    ts, _, sig = header.partition(":")
    if not ts.isdigit() or not sig or abs(time.time() - int(ts)) > 60:
        return False
    msg = f"{ts}:{method}:{target}:{hashlib.sha256(body or b'').hexdigest()}"
    return hmac.compare_digest(hmac.new(SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest(), sig)


def under_home(p: str, follow_links: bool = True) -> Path:
    """Only paths inside the user's home may be verified. No reading /etc through this app.
    Interpreters are checked WITHOUT following links: a venv's python is a symlink to the system one."""
    q = Path(p).expanduser()
    rp = q.resolve() if follow_links else Path(os.path.abspath(q))
    if USER_HOME != rp and USER_HOME not in rp.parents:
        raise ValueError(f"path outside home is not allowed: {p}")
    return rp


def load_config() -> dict:
    f = DATA / "config.json"
    return json.loads(f.read_text()) if f.exists() else {"arms": []}


def save_trial(t: dict) -> None:
    with LOCK:
        (TRIALS / f"{t['id']}.json").write_text(json.dumps(t, indent=2))


def read_trial(tid: str) -> dict | None:
    f = TRIALS / f"{Path(tid).name}.json"
    return json.loads(f.read_text()) if f.exists() else None


def summary_row(t: dict) -> dict:
    s = t.get("summary") or {}
    return {"id": t["id"], "label": t.get("label", ""), "arm": t.get("arm", ""), "status": t["status"],
            "stage": t.get("stage"), "created": t["created"], "duration_s": t.get("duration_s"),
            "claimed": s.get("claimed"), "real_fixes": s.get("real_fixes"), "proven_tests": s.get("proven_tests"),
            "false_positives": s.get("false_positives"), "regressions": s.get("regressions"),
            "tampered": s.get("tampered"), "precision": s.get("precision"), "verdict": s.get("verdict"),
            "verified": s.get("verified"), "api_intact": s.get("api_intact"), "pr_url": t.get("pr_url")}


def start_trial(spec: dict) -> dict:
    repo = under_home(spec["repo"])
    python = under_home(spec["python"], follow_links=False)
    hidden = under_home(spec["hidden"]) if spec.get("hidden") else None
    t = {"id": uuid.uuid4().hex[:10], "label": spec.get("label", ""), "arm": spec.get("arm", ""),
         "status": "running", "stage": "queued", "created": time.time(), "stages": []}
    save_trial(t)

    def on_stage(name: str, detail: str) -> None:
        t["stage"] = name
        t["stages"].append({"stage": name, "detail": detail, "t": round(time.time() - t["created"], 2)})
        save_trial(t)

    def work() -> None:
        try:
            res = gate.verify(str(repo), spec["base"], spec["head"], str(python),
                              str(hidden) if hidden else None, spec.get("claimed"), t["label"], on_stage)
            t.update(res)
            t["status"] = "done"
        except Exception as exc:  # report, never crash the server
            t["status"], t["error"] = "error", str(exc)[:500]
        save_trial(t)

    threading.Thread(target=work, daemon=True).start()
    return t


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # keep stdout quiet
        pass

    def _send(self, code: int, obj) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth(self, body: bytes) -> bool:
        return verify_proxy(self.headers.get("X-KiroCrew-Proxy", ""), self.command, self.path, body)

    def _dispatch(self) -> None:
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else b""
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path == "/api" or path.startswith("/api/"):  # the gateway proxy forwards /api/<route>
            path = path[4:] or "/"
        if path == "/health":
            return self._send(200, {"status": "ok", "app": APP})
        if not self._auth(body):
            return self._send(401, {"error": "unauthorized"})
        try:
            data = json.loads(body) if body else {}
            if self.command == "GET" and path == "/config":
                return self._send(200, load_config())
            if self.command == "PUT" and path == "/config":
                (DATA / "config.json").write_text(json.dumps(data, indent=2))
                return self._send(200, data)
            if self.command == "GET" and path == "/trials":
                rows = [summary_row(json.loads(f.read_text())) for f in TRIALS.glob("*.json")]
                return self._send(200, sorted(rows, key=lambda r: -r["created"]))
            if self.command == "GET" and path.startswith("/trials/"):
                t = read_trial(path.split("/")[-1])
                return self._send(200, t) if t else self._send(404, {"error": "not found"})
            if self.command == "POST" and path == "/trials":
                return self._send(202, {"id": start_trial(data)["id"]})
            if self.command == "POST" and path == "/batch":
                cfg = load_config()
                ids = [start_trial({**arm, "repo": cfg["repo"], "python": cfg["python"],
                                    "hidden": cfg.get("hidden")})["id"] for arm in cfg.get("arms", [])]
                return self._send(202, {"ids": ids})
            if self.command == "POST" and path == "/reset":
                for f in TRIALS.glob("*.json"):
                    f.unlink()
                return self._send(200, {"ok": True})
            return self._send(404, {"error": "no such route"})
        except (KeyError, ValueError) as exc:
            return self._send(400, {"error": str(exc)})

    do_GET = do_POST = do_PUT = _dispatch


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"proof-gate backend on 127.0.0.1:{PORT}  data={DATA}", flush=True)
    srv.serve_forever()
