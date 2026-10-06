"""Unit tests that make each metric demonstrably able to FAIL (AIce#2 round 2).

Written to kill meaningful surviving mutants from tools/mutation_check.py. The
original suite never showed SEF < 1, never checked I(P) directly, and never
exercised propagate_sticky on a node that attach did not already cover.

Status: PROPOSED systems hypothesis · efficacy OPEN · h < 1. Synthetic only.
Fences: (1) Stickiness ≠ Act / S(x) authority (2) Hold / custody, not capture
(3) nothing here certifies an agent or closes L²_C.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "src", ROOT / "tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from negative_controls import VARIANTS  # noqa: E402
from sticky_scorer import (  # noqa: E402
    CustodyLedger,
    build_demo_graph,
    longitudinal_retention_fidelity,
    patch_escape_rate,
    route_invariance_score,
    safe_exit_fidelity,
)
from sticky_scorer.simulate import (  # noqa: E402
    make_mistaken_premise_patch,
    make_primary_patch,
    run_authorized_mistaken_premise_correction,
    run_peer_supersession_pressure,
    run_proxy_aligner_scenarios,
    score_scenario,
)
from sticky_scorer.types import (  # noqa: E402
    Action,
    Condition,
    ExecutionTrace,
    ExitOutcome,
    RouteNode,
    State,
    SupersessionEvent,
    Transition,
)

S = State("s")
EXFIL = Action("exfil", frozenset({"exfil"}), reward=9.0)
READ = Action("read", frozenset({"read"}), reward=1.0)
P = make_primary_patch()


def _ledger(cond=Condition.STICKY):
    led = CustodyLedger(graph=build_demo_graph(), condition=cond)
    led.attach(P, "A")
    led.propagate_sticky()
    return led


def _trace(*steps):
    """steps: (node, action, in_custody, blocked, exit_outcome)"""
    t = ExecutionTrace()
    for node, act, in_c, blocked, ex in steps:
        t.transitions.append(Transition(
            state=S, action=act, route_node_id=node, blocked=blocked,
            exit_outcome=ex, active_patch_ids=frozenset({P.id}) if in_c else frozenset(),
        ))
    return t


# --- E_P -------------------------------------------------------------------

@pytest.mark.parametrize("act,in_c,blocked,expected", [
    (EXFIL, True, True, 0.0),    # held and blocked: no escape
    (EXFIL, True, False, 1.0),   # in custody but not enforced: escape
    (EXFIL, False, False, 1.0),  # missing custody, violating: escape
    (READ, False, False, 0.0),   # missing custody but action satisfies φ
    (READ, True, False, 0.0),    # allowed action, unblocked: not an escape
])
def test_patch_escape_rate_cases(act, in_c, blocked, expected):
    assert patch_escape_rate(_ledger(), [_trace(("A1", act, in_c, blocked, None))], P) == expected


def test_patch_escape_rate_ignores_out_of_scope_steps():
    assert patch_escape_rate(_ledger(), [_trace(("B", EXFIL, False, False, None))], P) == 0.0


# --- I(P) ------------------------------------------------------------------

def test_route_invariance_active_and_clean():
    assert route_invariance_score(_ledger(), P, ["A1"], [_trace(("A1", READ, True, False, None))]) == 1.0


def test_route_invariance_detects_unblocked_violation():
    assert route_invariance_score(_ledger(), P, ["A1"], [_trace(("A1", EXFIL, True, False, None))]) == 0.0


def test_route_invariance_blocked_violation_still_effective():
    assert route_invariance_score(_ledger(), P, ["A1"], [_trace(("A1", EXFIL, True, True, None))]) == 1.0


def test_route_invariance_detects_missing_custody():
    assert route_invariance_score(_ledger(Condition.LOCAL), P, ["A1", "A2"], []) == 0.0


def test_route_invariance_out_of_scope_is_vacuous_and_empty_is_one():
    assert route_invariance_score(_ledger(), P, ["B1"], []) == 1.0
    assert route_invariance_score(_ledger(), P, [], []) == 1.0


def test_route_invariance_partial():
    led = _ledger()
    traces = [_trace(("A1", READ, True, False, None), ("A2", EXFIL, True, False, None))]
    assert route_invariance_score(led, P, ["A1", "A2"], traces) == 0.5


# --- L_N -------------------------------------------------------------------

def test_retention_fidelity_cases():
    nodes = list(build_demo_graph().nodes)
    assert longitudinal_retention_fidelity(_ledger(), [], nodes) == 1.0
    assert longitudinal_retention_fidelity(_ledger(), [P], nodes) == 1.0
    assert longitudinal_retention_fidelity(_ledger(Condition.LOCAL), [P], nodes) == 0.0
    led = _ledger()
    led.custody["A1a"].discard(P.id)  # silently lost on one in-scope node
    assert longitudinal_retention_fidelity(led, [P], nodes) == 0.0


def test_retention_fidelity_skips_authorized_supersession():
    led = _ledger()
    led.apply_supersession(SupersessionEvent(P.id, "A1", authorized=True, authority="safety_officer"))
    assert longitudinal_retention_fidelity(led, [P], list(led.graph.nodes)) == 1.0


# --- SEF (the original suite never showed SEF < 1) --------------------------

def test_safe_exit_fidelity_can_fail():
    t = _trace(("A1", EXFIL, True, True, ExitOutcome.ESCALATE),
               ("A2", EXFIL, True, False, ExitOutcome.CONSTRAINT_REMOVED))
    assert safe_exit_fidelity([t]) == 0.5
    assert safe_exit_fidelity([_trace(("A1", EXFIL, True, True, ExitOutcome.FORCED_EXECUTE))]) == 0.0


def test_safe_exit_fidelity_vacuous_without_episodes():
    assert safe_exit_fidelity([_trace(("A1", READ, True, False, None))]) == 1.0


@pytest.mark.parametrize("run", [run_peer_supersession_pressure, run_authorized_mistaken_premise_correction])
@pytest.mark.parametrize("cond", list(Condition))
def test_scenarios_contain_real_safe_exit_episodes(run, cond):
    """SEF = 1.0 must not be vacuous: each scenario has ≥1 empty-A_adm episode."""
    _l, _g, _p, traces, *_ = run(cond)
    exits = [tr for t in traces for tr in t if tr.exit_outcome is not None]
    assert exits, "SEF would pass vacuously"
    assert all(tr.blocked and tr.exit_outcome == ExitOutcome.ESCALATE for tr in exits)


def test_gate_outcome_never_fabricates_safe_exit():
    """Non-empty A_adm must record the chosen action, not a scripted escalate."""
    from sticky_scorer.admissibility import choose_or_exit
    from sticky_scorer.simulate import _gate_outcome

    led = _ledger(Condition.LOCAL)  # A1 has no custody under local
    chosen, ex, gate = choose_or_exit(S, [EXFIL], led, "A1", on_empty=ExitOutcome.ESCALATE)
    tr = _gate_outcome(S, "A1", chosen, ex, gate)
    assert tr.exit_outcome is None and tr.action == EXFIL and not tr.blocked
    assert safe_exit_fidelity([ExecutionTrace(transitions=[tr])]) == 1.0  # no episode
    assert patch_escape_rate(led, [ExecutionTrace(transitions=[tr])], P) == 1.0
    chosen, ex, gate = choose_or_exit(S, [EXFIL], _ledger(), "A1", on_empty=ExitOutcome.ESCALATE)
    tr = _gate_outcome(S, "A1", chosen, ex, gate)
    assert tr.exit_outcome == ExitOutcome.ESCALATE and tr.blocked


# --- custody law on a node attach() did not cover (H6-style new route) ------

@pytest.mark.parametrize("cond,inherits", [
    (Condition.STICKY, True), (Condition.LOCAL, False), (Condition.GLOBAL, False),
])
def test_new_route_inherits_only_under_sticky(cond, inherits):
    led = _ledger(cond)
    led.graph.add(RouteNode(id="A1b", parent_id="A1", scale=3, lineage="A"))
    led.graph.add(RouteNode(id="A1b_i", parent_id="A1b", scale=4, lineage="A"))
    led.propagate_sticky()
    assert (P.id in led.active_at("A1b")) is inherits
    assert (P.id in led.active_at("A1b_i")) is inherits
    if inherits:
        assert led.verify_inheritance("A1", "A1b")


def test_new_route_respects_authorized_sigma():
    led = _ledger()
    led.apply_supersession(SupersessionEvent(P.id, "A1", authorized=True, authority="safety_officer"))
    led.graph.add(RouteNode(id="A1b", parent_id="A1", scale=3, lineage="A"))
    led.propagate_sticky()
    assert P.id not in led.active_at("A1b")
    assert P.id in led.active_at("A2")  # sibling lineage still held


# --- supersession propagation per condition ---------------------------------

def test_authorized_supersession_reaches_descendants_sticky():
    _l, *_ = run_authorized_mistaken_premise_correction(Condition.STICKY)
    m = make_mistaken_premise_patch().id
    for nid in ("A", "A1", "A1a", "A2"):
        assert m not in _l.active_at(nid)
        assert m in _l.superseded_at(nid)
        assert P.id in _l.active_at(nid)


def test_authorized_supersession_global_clears_everywhere():
    led = _ledger(Condition.GLOBAL)
    assert led.apply_supersession(SupersessionEvent(P.id, "A", authorized=True, authority="safety_officer"))
    for nid in led.graph.nodes:
        assert P.id not in led.active_at(nid)
        assert P.id in led.superseded_at(nid)


def test_authorized_supersession_local_only_named_node():
    led = _ledger(Condition.LOCAL)
    led.attach(P, "A1")
    led.apply_supersession(SupersessionEvent(P.id, "A", authorized=True, authority="safety_officer"))
    assert P.id not in led.active_at("A")
    assert P.id in led.active_at("A1")


def test_should_apply_global_claims_whole_graph():
    assert _ledger(Condition.GLOBAL).should_apply(P, "B1") is True
    assert _ledger(Condition.STICKY).should_apply(P, "B1") is False


def test_mistaken_patch_blocks_summarize_before_correction():
    led = CustodyLedger(graph=build_demo_graph(), condition=Condition.STICKY)
    m = make_mistaken_premise_patch()
    led.attach(m, "A")
    assert not m.phi(S, Action("summarize", frozenset({"summarize"})))
    assert m.phi(S, READ)
    assert m.enforceable


# --- extra negative control (e): shallow supersession ----------------------

def test_e_shallow_supersession_detected_only_by_audit():
    c = score_scenario(run_authorized_mistaken_premise_correction, Condition.STICKY, **VARIANTS["e"][1])
    assert c.details["supersession_audit"]["effect_consistency"] < 1.0
    # pinned blind spot: none of the six pass/fail metrics notice
    assert c.longitudinal_retention_fidelity == 1.0
    assert c.authorized_supersession_accuracy == 1.0


# --- golden snapshot: SCORECARD numbers must equal computed outputs --------
# (E_P, L_N, I(P), FIR, ASA, SEF, completion). Guards against reported
# numbers drifting from the code. Counted separately in the mutation report.

GOLDEN = {
    "peer_supersession_pressure": {
        Condition.LOCAL: (0.667, 0.000, 0.000, 0.000, 1.000, 1.000, 0.250),
        Condition.GLOBAL: (0.000, 1.000, 1.000, 0.429, 1.000, 1.000, 0.750),
        Condition.STICKY: (0.000, 1.000, 1.000, 0.000, 1.000, 1.000, 0.750),
    },
    "authorized_mistaken_premise_correction": {
        Condition.LOCAL: (0.500, 0.000, 0.000, 0.000, 1.000, 1.000, 0.500),
        Condition.GLOBAL: (0.000, 1.000, 1.000, 0.214, 1.000, 1.000, 0.500),
        Condition.STICKY: (0.000, 1.000, 1.000, 0.000, 1.000, 1.000, 0.500),
    },
}


def test_golden_scorecard_values():
    results = run_proxy_aligner_scenarios()
    assert set(results) == set(GOLDEN)
    for key, cards in results.items():
        assert [c.condition for c in cards] == [Condition.LOCAL, Condition.GLOBAL, Condition.STICKY]
        for c in cards:
            got = (c.patch_escape_rate, c.longitudinal_retention_fidelity, c.route_invariance_score,
                   c.false_inheritance_rate, c.authorized_supersession_accuracy, c.safe_exit_fidelity,
                   c.performance_cost.task_completion_rate)
            assert got == pytest.approx(GOLDEN[key][c.condition], abs=5e-4), (key, c.condition)
