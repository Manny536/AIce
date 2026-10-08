#!/usr/bin/env python3
"""Run the full opto-probe matrix (AIce#5) and print / save raw results.

    PYTHONPATH=src:tests python3 tools/opto_probe_run.py [--json out.json]

Deterministic: no seeds are used. Registry keys are random per run, but no
outcome depends on key values. Synthetic only. Nothing here certifies an agent
or closes L²_C. Status: STRUCTURAL ANALOGY / PROPOSED · efficacy OPEN · h < 1.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

from opto_controls import CONTROLS  # noqa: E402
from sticky_scorer.opto_probe import detected, load_expected, run_matrix  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    exp = load_expected()
    t = time.perf_counter()
    out = run_matrix(exp, CONTROLS)
    elapsed = time.perf_counter() - t
    rows, mis = [], 0
    for key in sorted(out):
        r, res, vs_ref = out[key]
        mis += bool(res["action_mismatches"] or res["accept_mismatch"])
        row = {"key": key, "actions": r.actions, "accept": r.accept, "denied": r.denied,
               "consumed_tokens": r.consumed_tokens,
               "events": [asdict(e) for e in r.events], "fidelity_diff": r.fidelity_diff,
               "snapshot_unchanged": r.snapshot_unchanged,
               "ablation_before_rescue": r.ablation_before_rescue, "context": r.context,
               "n_steps": r.n_steps, "eval_vs_frozen": res}
        if vs_ref is not None:
            row["eval_vs_intact_reference"] = vs_ref
            row["detected"] = detected(vs_ref)
        rows.append(row)
        line = (f"{key:56s} post={res['post_checkpoints']:2d} missed={res['missed_interruptions']:2d} "
                f"false={res['false_interruptions']:2d} t0_wrong_block={res['mistaken_interruptions_t0']} "
                f"undone={res['mistaken_undone_by_t1']}")
        if vs_ref is not None:
            line += f" detected={detected(vs_ref)}"
        print(line)
    print(f"runs={len(out)} mispredicted={mis} elapsed_s={elapsed:.3f} "
          f"steps={sum(o[0].n_steps for o in out.values())}")
    if args.json:
        Path(args.json).write_text(json.dumps({"runs": rows, "elapsed_s": elapsed}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
