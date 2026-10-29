#!/usr/bin/env python3
"""Run tools/mutation_check.py against the AIce#9 concurrency model and adapter.

Goal: show that the tests for the transition system can fail. Each mutant is one
generic syntactic change inside a function of concurrency_model.py or
concurrency_adapter.py; the model and adapter tests run against it.
Why: a checker that cannot fail says nothing about a protocol. Survivors are
listed, not hidden, and are discussed in docs/PEAICE-AICE-LAMPORT-001.md.
How checked: baseline (unmutated, round-tripped through ast.unparse) must pass;
a non-zero exit or a timeout kills the mutant.

Same generic operators as mutation_check.py. The kill rate is a property of
these tests on this synthetic model; it is not a prediction about any deployment.
Synthetic tooling only. Nothing here certifies an agent or closes L²_C.
Status: PROPOSED systems hypothesis · efficacy OPEN · h < 1.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path
from typing import Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutation_check  # noqa: E402

TEST_FILES = ("tests/test_concurrency_model.py", "tests/test_concurrency_adapter.py")


def _function_names(rel: str) -> Tuple[str, ...]:
    root = Path(__file__).resolve().parents[1]
    tree = ast.parse((root / rel).read_text(encoding="utf-8"))
    skip = {"load_expected", "ok", "has"}  # file loading and a trivial accessor
    return tuple(sorted({n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)} - skip))


CONCURRENCY_TARGETS = {
    "src/sticky_scorer/concurrency_model.py": _function_names("src/sticky_scorer/concurrency_model.py"),
    "src/sticky_scorer/concurrency_adapter.py": _function_names("src/sticky_scorer/concurrency_adapter.py"),
}


def _run_tests(workdir: Path, python: str, timeout: int):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(workdir / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            [python, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *TEST_FILES],
            cwd=workdir, env=env, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, "timeout"
    tail = (proc.stdout.strip().splitlines() or [""])[-1]
    return proc.returncode == 0, tail


if __name__ == "__main__":
    mutation_check.DEFAULT_TARGETS = CONCURRENCY_TARGETS
    mutation_check._run_tests = _run_tests
    raise SystemExit(mutation_check.main(sys.argv[1:] or ["--timeout", "240"]))
