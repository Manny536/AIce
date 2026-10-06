#!/usr/bin/env python3
"""Small AST mutation-testing pass for sticky_scorer (AIce#2 legitimacy check).

Purpose: show the test suite can FAIL. Each mutant is one generic syntactic
change inside a targeted function; the suite runs against it; a non-zero exit
(or timeout) = killed, exit 0 = survived.

Operators are generic (not hand-picked to be killable):
  cmp      flip a comparison (== <-> !=, < <-> >=, > <-> <=, in <-> not in, is <-> is not)
  boolop   and <-> or
  not      drop a unary `not`
  if       negate an if / while / ternary test
  const    True <-> False
  stmt     delete a call statement or augmented assignment (replace with `pass`)

Usage (from repo root):
    python3 tools/mutation_check.py                 # mutate this repo
    python3 tools/mutation_check.py --repo /path    # mutate another checkout
    python3 tools/mutation_check.py --json out.json --jobs 8

Synthetic tooling only. Kill rate is a property of this test suite on this
synthetic simulator. Nothing here certifies an agent or closes L²_C (fence 3). Status: PROPOSED
systems hypothesis · efficacy OPEN · h < 1.
"""

from __future__ import annotations

import argparse
import ast
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

# file (relative to repo) -> functions to mutate (missing names are skipped)
DEFAULT_TARGETS: Dict[str, Sequence[str]] = {
    "src/sticky_scorer/simulate.py": (
        "verify_event_policy",
        "make_peer_lockin_patch",
        "make_mistaken_premise_patch",
        "compliant_agent",
        "_step",
        "_completed",
        "_walk",
        "_walk_lineage_A",
        "_walk_branch_B",
        "_exit_probe",
        "run_peer_supersession_pressure",
        "run_authorized_mistaken_premise_correction",
        "score_scenario",
        "run_proxy_aligner_scenarios",
    ),
    "src/sticky_scorer/authority.py": (
        "verify",
        "verify_event",
        "issue",
        "was_issued",
        "issued_any",
        "check",
    ),
    "src/sticky_scorer/custody.py": (
        "_append",
        "verify_log_chain",
        "_decide_attach",
        "_attach_targets",
        "_apply_attach",
        "_decide_supersession",
        "_apply_supersede",
        "apply_supersession",
        "replay_ledger",
        "custody_state",
        "attach",
        "inherit_child",
        "propagate_sticky",
        "verify_inheritance",
        "should_apply",
    ),
    "src/sticky_scorer/scorer.py": (
        "patch_escape_rate",
        "longitudinal_retention_fidelity",
        "route_invariance_score",
        "false_inheritance_rate",
        "authorized_supersession_accuracy",
        "safe_exit_fidelity",
        "over_stop_rate",
        "supersession_audit",
        "custody_audit",
    ),
    "src/sticky_scorer/admissibility.py": (
        "pi_sticky",
        "admissible_actions",
        "choose_or_exit",
    ),
}

CMP_SWAP = {
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
    ast.Lt: ast.GtE, ast.GtE: ast.Lt,
    ast.Gt: ast.LtE, ast.LtE: ast.Gt,
    ast.In: ast.NotIn, ast.NotIn: ast.In,
    ast.Is: ast.IsNot, ast.IsNot: ast.Is,
}


@dataclass
class Site:
    file: str
    function: str
    node_index: int  # index in ast.walk order of the whole module
    op: str
    sub: int  # comparator position for cmp
    line: int
    desc: str


@dataclass
class Result:
    site: Site
    killed: bool
    reason: str


def _functions(tree: ast.AST, wanted: Sequence[str]):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted:
            yield node


def _index_map(tree: ast.AST) -> Dict[int, int]:
    return {id(n): i for i, n in enumerate(ast.walk(tree))}


def _is_docstring(node: ast.AST) -> bool:
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)


def enumerate_sites(repo: Path, targets: Dict[str, Sequence[str]]) -> Tuple[List[Site], Dict[str, List[str]]]:
    sites: List[Site] = []
    found: Dict[str, List[str]] = {}
    for rel, funcs in targets.items():
        src = (repo / rel).read_text()
        tree = ast.parse(src)
        idx = _index_map(tree)
        lines = src.splitlines()
        seen_nodes = set()
        found[rel] = []
        for fn in _functions(tree, funcs):
            found[rel].append(fn.name)
            for node in ast.walk(fn):
                if id(node) in seen_nodes:
                    continue
                seen_nodes.add(id(node))
                i = idx[id(node)]
                ln = getattr(node, "lineno", fn.lineno)
                snippet = lines[ln - 1].strip() if 0 < ln <= len(lines) else ""
                def add(op: str, desc: str, sub: int = 0) -> None:
                    sites.append(Site(rel, fn.name, i, op, sub, ln, f"{desc} :: {snippet}"))
                if isinstance(node, ast.Compare):
                    for k, o in enumerate(node.ops):
                        if type(o) in CMP_SWAP:
                            add("cmp", f"{type(o).__name__}->{CMP_SWAP[type(o)].__name__}", k)
                elif isinstance(node, ast.BoolOp):
                    add("boolop", "and<->or")
                elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
                    add("not", "drop not")
                elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
                    add("const", f"{node.value}->{not node.value}")
                if isinstance(node, (ast.If, ast.While, ast.IfExp)):
                    add("if", "negate test")
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and not _is_docstring(node):
                    add("stmt", "delete call stmt")
                elif isinstance(node, ast.AugAssign):
                    add("stmt", "delete aug-assign")
    return sites, found


class _Mutator(ast.NodeTransformer):
    def __init__(self, target_index: int, op: str, sub: int, idx: Dict[int, int]):
        self.t = target_index
        self.op = op
        self.sub = sub
        self.idx = idx
        self.applied = False

    def _hit(self, node: ast.AST) -> bool:
        return self.idx.get(id(node)) == self.t

    def generic_visit(self, node):
        # mutate children first, then self (so indices refer to original nodes)
        super().generic_visit(node)
        return node

    def visit(self, node):
        node = self.generic_visit(node) if not self._hit(node) else node
        if not self._hit(node):
            return node
        # visit children of hit node too (unchanged), then apply op
        self.applied = True
        if self.op == "cmp":
            node.ops[self.sub] = CMP_SWAP[type(node.ops[self.sub])]()
            return node
        if self.op == "boolop":
            node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
            return node
        if self.op == "not":
            return node.operand
        if self.op == "const":
            return ast.Constant(value=not node.value)
        if self.op == "if":
            node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
            return node
        if self.op == "stmt":
            return ast.Pass()
        raise ValueError(self.op)


def mutate_source(src: str, site: Site) -> str:
    tree = ast.parse(src)
    idx = _index_map(tree)
    m = _Mutator(site.node_index, site.op, site.sub, idx)
    tree = m.visit(tree)
    if not m.applied:
        raise RuntimeError(f"mutation not applied: {site}")
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


def _copy_repo(repo: Path, dest: Path) -> None:
    ignore = shutil.ignore_patterns(
        ".git", ".venv", "__pycache__", ".pytest_cache", "*.pyc", "mutants", "tools"
    )
    for name in ("src", "tests"):
        shutil.copytree(repo / name, dest / name, ignore=ignore)
    for f in ("pyproject.toml",):
        if (repo / f).exists():
            shutil.copy2(repo / f, dest / f)


def _run_tests(workdir: Path, python: str, timeout: int) -> Tuple[bool, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(workdir / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            [python, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "tests"],
            cwd=workdir, env=env, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, "timeout"
    tail = (proc.stdout.strip().splitlines() or [""])[-1]
    return proc.returncode == 0, tail


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2)))
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--json", default=None, help="write full results here")
    args = ap.parse_args(argv)

    repo = Path(args.repo).resolve()
    sites, found = enumerate_sites(repo, DEFAULT_TARGETS)
    originals = {rel: (repo / rel).read_text() for rel in DEFAULT_TARGETS}

    root = Path(tempfile.mkdtemp(prefix="aice-mut-"))
    try:
        # Baseline: unmutated (round-tripped through ast.unparse) must pass.
        base = root / "baseline"
        _copy_repo(repo, base)
        for rel, src in originals.items():
            (base / rel).write_text(ast.unparse(ast.parse(src)))
        ok, tail = _run_tests(base, args.python, args.timeout)
        if not ok:
            print(f"BASELINE FAILED ({tail}); aborting", file=sys.stderr)
            return 2

        workers = [root / f"w{i}" for i in range(args.jobs)]
        for w in workers:
            _copy_repo(repo, w)

        def run(i_site: Tuple[int, Site]) -> Result:
            i, site = i_site
            w = workers[i % len(workers)]
            # restore all target files, then mutate one
            for rel, src in originals.items():
                (w / rel).write_text(src)
            try:
                mutated = mutate_source(originals[site.file], site)
            except Exception as exc:  # unparseable -> count as killed by compiler
                return Result(site, True, f"mutation-error {exc}")
            (w / site.file).write_text(mutated)
            ok, tail = _run_tests(w, args.python, args.timeout)
            return Result(site, not ok, tail)

        # one worker dir per job: chunk sites so a worker dir is never shared concurrently
        buckets: List[List[Tuple[int, Site]]] = [[] for _ in workers]
        for i, s in enumerate(sites):
            buckets[i % len(workers)].append((i, s))

        def run_bucket(bucket):
            return [run(x) for x in bucket]

        results: List[Result] = []
        with ThreadPoolExecutor(max_workers=len(workers)) as ex:
            for chunk in ex.map(run_bucket, buckets):
                results.extend(chunk)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    results.sort(key=lambda r: (r.site.file, r.site.line, r.site.op, r.site.sub))
    killed = sum(r.killed for r in results)
    total = len(results)
    rate = killed / total if total else 0.0
    print(f"repo: {repo}")
    for rel, names in found.items():
        missing = [n for n in DEFAULT_TARGETS[rel] if n not in names]
        print(f"  {rel}: {len(names)} functions" + (f" (absent: {', '.join(missing)})" if missing else ""))
    print(f"mutants: {total}  killed: {killed}  survived: {total - killed}  kill rate: {rate:.1%}")
    by_fn: Dict[str, List[int]] = {}
    for r in results:
        k = f"{Path(r.site.file).name}:{r.site.function}"
        by_fn.setdefault(k, [0, 0])
        by_fn[k][0] += 1
        by_fn[k][1] += int(r.killed)
    print("per function (killed/total):")
    for k in sorted(by_fn):
        t, kk = by_fn[k]
        print(f"  {k}: {kk}/{t}")
    print("SURVIVORS:")
    for r in results:
        if not r.killed:
            s = r.site
            print(f"  {Path(s.file).name}:{s.line} [{s.function}] {s.op}: {s.desc}")
    if args.json:
        Path(args.json).write_text(json.dumps(
            {"total": total, "killed": killed, "kill_rate": rate,
             "results": [dict(asdict(r.site), killed=r.killed, reason=r.reason) for r in results]},
            indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
