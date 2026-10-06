"""sticky_scorer — first scorer for sticky patch custody (AIce / L²).

Implements study §§15–19 metrics:
  E_P, L_N, I(P), false inheritance, supersession accuracy, safe-exit fidelity,
  plus optional performance-cost hooks.
"""

from .admissibility import (
    VALID_SAFE_EXITS,
    admissible_actions,
    choose_or_exit,
    is_valid_safe_exit,
    pi_sticky,
)
from .custody import CustodyLedger
from .scorer import (
    TARGETS,
    authorized_supersession_accuracy,
    false_inheritance_rate,
    format_scorecard_table,
    longitudinal_retention_fidelity,
    patch_escape_rate,
    performance_cost,
    route_invariance_score,
    safe_exit_fidelity,
    score_condition,
    supersession_audit,
)
from .simulate import (
    build_demo_graph,
    demo_report,
    make_mistaken_premise_patch,
    proxy_aligner_report,
    run_authorized_mistaken_premise_correction,
    run_condition,
    run_demo,
    run_peer_supersession_pressure,
    run_proxy_aligner_scenarios,
)
from .types import (
    Action,
    Condition,
    ExecutionTrace,
    ExitOutcome,
    Patch,
    PerformanceCost,
    RouteGraph,
    RouteNode,
    Scorecard,
    State,
    SupersessionEvent,
    Transition,
)

__version__ = "0.1.0"
__all__ = [
    "VALID_SAFE_EXITS",
    "TARGETS",
    "Action",
    "Condition",
    "CustodyLedger",
    "ExecutionTrace",
    "ExitOutcome",
    "Patch",
    "PerformanceCost",
    "RouteGraph",
    "RouteNode",
    "Scorecard",
    "State",
    "SupersessionEvent",
    "Transition",
    "admissible_actions",
    "authorized_supersession_accuracy",
    "build_demo_graph",
    "choose_or_exit",
    "demo_report",
    "false_inheritance_rate",
    "format_scorecard_table",
    "is_valid_safe_exit",
    "longitudinal_retention_fidelity",
    "patch_escape_rate",
    "performance_cost",
    "pi_sticky",
    "route_invariance_score",
    "run_condition",
    "run_demo",
    "run_proxy_aligner_scenarios",
    "run_peer_supersession_pressure",
    "run_authorized_mistaken_premise_correction",
    "proxy_aligner_report",
    "make_mistaken_premise_patch",
    "safe_exit_fidelity",
    "score_condition",
    "supersession_audit",
]
