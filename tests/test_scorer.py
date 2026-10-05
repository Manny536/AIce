"""Tests for sticky_scorer demo graph hypotheses H1 and H4."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Allow running without install: repo/src on path
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sticky_scorer import (  # noqa: E402
    Condition,
    CustodyLedger,
    ExitOutcome,
    admissible_actions,
    build_demo_graph,
    is_valid_safe_exit,
    pi_sticky,
    run_condition,
    run_demo,
)
from sticky_scorer.simulate import make_primary_patch  # noqa: E402
from sticky_scorer.types import Action, State  # noqa: E402


def test_sticky_lower_escape_than_local():
    """H1: sticky E_P < local E_P on the demo graph."""
    cards = {c.condition: c for c in run_demo()}
    assert cards[Condition.STICKY].patch_escape_rate < cards[Condition.LOCAL].patch_escape_rate


def test_sticky_lower_false_inheritance_than_global():
    """H4: sticky FIR < global FIR on the demo graph."""
    cards = {c.condition: c for c in run_demo()}
    assert (
        cards[Condition.STICKY].false_inheritance_rate
        < cards[Condition.GLOBAL].false_inheritance_rate
    )


def test_custody_inheritance_law():
    """C(v) ⊇ C(u) \\ Σ(v) after sticky propagate."""
    graph = build_demo_graph()
    ledger = CustodyLedger(graph=graph, condition=Condition.STICKY)
    p = make_primary_patch()
    ledger.attach(p, "A")
    ledger.propagate_sticky()
    assert ledger.verify_inheritance("A", "A1")
    assert ledger.verify_inheritance("A1", "A1a")
    assert p.id in ledger.active_at("A2")
    assert p.id not in ledger.active_at("B")


def test_local_does_not_spread():
    graph = build_demo_graph()
    ledger = CustodyLedger(graph=graph, condition=Condition.LOCAL)
    p = make_primary_patch()
    ledger.attach(p, "A")
    assert p.id in ledger.active_at("A")
    assert p.id not in ledger.active_at("A1")
    assert p.id not in ledger.active_at("B")


def test_global_spreads_everywhere():
    graph = build_demo_graph()
    ledger = CustodyLedger(graph=graph, condition=Condition.GLOBAL)
    p = make_primary_patch()
    ledger.attach(p, "A")
    for nid in graph.nodes:
        assert p.id in ledger.active_at(nid)


def test_pi_sticky_noncompensatory():
    p = make_primary_patch()
    state = State("s")
    bad = Action("exfil", frozenset({"exfil"}), reward=1e9)
    good = Action("read", frozenset({"read"}), reward=0.1)
    assert not pi_sticky(state, bad, [p]).admissible
    assert pi_sticky(state, good, [p]).admissible


def test_unauthorized_supersession_rejected():
    ledger, graph, patches, traces, alts, events, accepted = run_condition(
        Condition.STICKY
    )
    # Second event is unauthorized
    assert events[1].authorized is False
    assert accepted[1] is False
    # Primary patch must still be present on A
    assert "P_deny_exfil" in ledger.active_at("A")


def test_safe_exit_valid():
    assert is_valid_safe_exit(ExitOutcome.ESCALATE)
    assert is_valid_safe_exit(ExitOutcome.STOP)
    assert not is_valid_safe_exit(ExitOutcome.CONSTRAINT_REMOVED)
    assert not is_valid_safe_exit(None)


def test_admissible_actions_filters():
    graph = build_demo_graph()
    ledger = CustodyLedger(graph=graph, condition=Condition.STICKY)
    p = make_primary_patch()
    ledger.attach(p, "A")
    ledger.propagate_sticky()
    state = State("s")
    cands = [
        Action("read", frozenset({"read"}), reward=1.0),
        Action("exfil", frozenset({"exfil"}), reward=9.0),
    ]
    adm = admissible_actions(state, cands, ledger, "A1")
    assert [a.name for a in adm] == ["read"]
