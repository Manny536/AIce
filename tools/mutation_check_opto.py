#!/usr/bin/env python3
"""Run tools/mutation_check.py against the opto-probe functions only (AIce#5).

Same generic operators and the same full test suite as mutation_check.py; only
the target list differs. Pre-registered prediction (tests/opto_expected.json):
kill rate >= 80%. This is a prediction, not a pass threshold.

Synthetic tooling only. Nothing here certifies an agent or closes L²_C.
Status: STRUCTURAL ANALOGY / PROPOSED · efficacy OPEN · h < 1.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutation_check  # noqa: E402

OPTO_TARGETS = {
    "src/sticky_scorer/opto_probe.py": (
        "_deny", "make_patches", "lineage", "candidates", "build_graph", "add_successors",
        "enforcing", "wrapped", "gate_ignoring_agent", "hooked_inherit", "handoff_live",
        "handoff_replay", "admit", "_checkpoint", "_digest", "_diff", "run_probe",
        "do_handoff", "_tags", "evaluate", "detected", "run_key", "run_matrix",
    ),
}

if __name__ == "__main__":
    mutation_check.DEFAULT_TARGETS = OPTO_TARGETS
    raise SystemExit(mutation_check.main())
