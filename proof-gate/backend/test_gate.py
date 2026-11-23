#!/usr/bin/env python3
"""Regression tests for gate.py, aimed at real-world suite shapes.

The gate's own demo habitat is flat, module-level tests with no conftest.
Real suites are not: they ship conftest.py files and put tests inside
classes. These tests pin three behaviours that habitat hid:

  A. the pristine run must still collect tests when conftest.py files exist
  B. a test inside a class must get an id that names a real file, so it can
     be re-run as a target and proven RED -> GREEN
  C. a test that already failed on the base code is not a regression

Run with: python -m pytest proof-gate/backend/test_gate.py
"""
import subprocess
import sys
from pathlib import Path

import gate

PY = sys.executable

CALC_BUG = "def add(a, b):\n    return a - b\n"
CALC_FIXED = "def add(a, b):\n    return a + b\n"
BASE_TESTS = "from calc import add\n\n\ndef test_add_zero():\n    assert add(1, 0) == 1\n"


def _tree(root: Path, files: dict) -> Path:
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return root


def _repo(tmp_path: Path, base_files: dict, head_files: dict):
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*a):
        subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)

    def rev():
        return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()

    git("init", "-q")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "t")
    _tree(repo, base_files)
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    base = rev()
    _tree(repo, head_files)
    git("add", "-A")
    git("commit", "-q", "-m", "head")
    return str(repo), base, rev()


# ---------------------------------------------------------------- Bug A
def test_pristine_run_collects_despite_conftest(tmp_path):
    # Two conftest.py files in different directories, like a real suite:
    # named as pytest targets they collide and abort collection entirely.
    files = {
        "calc.py": CALC_FIXED,
        "tests/conftest.py": "import pytest\n\n\n@pytest.fixture\ndef one():\n    return 1\n",
        "tests/test_a.py": "def test_a(one):\n    assert one == 1\n",
        "tests/sub/conftest.py": "import pytest\n\n\n@pytest.fixture\ndef two():\n    return 2\n",
        "tests/sub/test_b.py": "def test_b(two):\n    assert two == 2\n",
    }
    base = _tree(tmp_path / "base", files)
    head = _tree(tmp_path / "head", files)
    res = gate.pristine_run(PY, head, base)
    assert res["total"] == 2
    assert res["failures"] == []


# ---------------------------------------------------------------- Bug B
def test_test_key_resolves_real_files(tmp_path):
    _tree(tmp_path, {"test_bugs.py": "", "pkg/mod.py": ""})
    # module-level: unchanged from the original format
    assert gate._test_key(tmp_path, None, "test_bugs", "test_x") == "test_bugs.py::test_x"
    # class-based: the class becomes a qualifier, the file stays real
    assert (gate._test_key(tmp_path, None, "pkg.mod.TestThing", "test_x")
            == "pkg/mod.py::TestThing::test_x")
    # nested class
    assert (gate._test_key(tmp_path, None, "pkg.mod.Outer.Inner", "test_x")
            == "pkg/mod.py::Outer::Inner::test_x")


def test_class_based_test_can_be_proven(tmp_path):
    repo, base, head = _repo(
        tmp_path,
        {"calc.py": CALC_BUG, "test_calc.py": BASE_TESTS},
        {"calc.py": CALC_FIXED,
         "test_calc.py": BASE_TESTS + "\n\nclass TestAdd:\n    def test_add(self):\n        assert add(2, 3) == 5\n"},
    )
    res = gate.verify(repo, base, head, PY, claimed=1)
    assert [t["verdict"] for t in res["new_tests"]] == ["proven"]
    assert res["summary"]["verdict"] == "TRUSTED"


# ---------------------------------------------------------------- Bug C
def test_preexisting_failure_is_not_a_regression(tmp_path):
    flaky = "\n\ndef test_environment_thing():\n    assert False, 'fails on base too'\n"
    repo, base, head = _repo(
        tmp_path,
        {"calc.py": CALC_BUG, "test_calc.py": BASE_TESTS + flaky},
        {"calc.py": CALC_FIXED,
         "test_calc.py": BASE_TESTS + flaky + "\n\ndef test_add():\n    assert add(2, 3) == 5\n"},
    )
    res = gate.verify(repo, base, head, PY, claimed=1)
    assert res["pristine"]["failures"], "the pre-existing failure should still be reported"
    assert res["summary"]["regressions"] == 0
    assert res["summary"]["verdict"] == "TRUSTED"


def test_preexisting_failure_outside_testpaths_is_not_a_regression(tmp_path):
    # The pristine run names every test file as a target, but a bare pytest
    # run respects testpaths. A pre-existing failure outside testpaths was
    # never seen on base, so it read as a regression. (Real case: ezdxf's
    # integration_tests/, which its pytest.ini testpaths excludes.)
    outside = {"integration_tests/test_env.py": "def test_env_thing():\n    assert False, 'fails on base too'\n"}
    repo, base, head = _repo(
        tmp_path,
        {"calc.py": CALC_BUG, "pytest.ini": "[pytest]\ntestpaths = tests\n",
         "tests/test_calc.py": BASE_TESTS, **outside},
        {"calc.py": CALC_FIXED, "pytest.ini": "[pytest]\ntestpaths = tests\n",
         "tests/test_calc.py": BASE_TESTS + "\n\ndef test_add():\n    assert add(2, 3) == 5\n", **outside},
    )
    res = gate.verify(repo, base, head, PY, claimed=1)
    assert res["pristine"]["failures"], "the pre-existing failure should still be reported"
    assert res["summary"]["regressions"] == 0
    assert res["summary"]["verdict"] == "TRUSTED"
