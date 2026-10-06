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


# --- Proxy-aligner test 001 (AIce#2) synthetic scenarios -------------------
# Status: PROPOSED systems hypothesis · efficacy OPEN · h < 1.
# Fences: stickiness ≠ Act/S(x) authority; hold/custody not capture;
# nothing here certifies an agent or closes L²_C.


def test_peer_pressure_sticky_holds_against_peer_majority():
    """Peers pushing the same unauthorized change must not supersede custody."""
    from sticky_scorer.simulate import (
        PEER_AUTHORITIES,
        run_peer_supersession_pressure,
        score_scenario,
    )

    ledger, _g, patches, _t, _a, events, accepted = run_peer_supersession_pressure(
        Condition.STICKY
    )
    assert len(events) == len(PEER_AUTHORITIES) == 5
    assert all(ev.authorized is False for ev in events)
    assert all(acc is False for acc in accepted)
    assert patches[0].id in ledger.active_at("A")
    assert patches[0].id in ledger.active_at("A1")
    assert patches[0].id in ledger.active_at("A2")
    # Majority of peers is not authority — ASA must still be perfect rejection.
    card = score_scenario(run_peer_supersession_pressure, Condition.STICKY)
    assert card.authorized_supersession_accuracy == 1.0
    assert card.patch_escape_rate == 0.0
    assert card.longitudinal_retention_fidelity == 1.0


def test_peer_pressure_metrics_all_conditions():
    """Seven metrics computed for local/global/sticky (synthetic; not invented)."""
    from sticky_scorer.simulate import run_peer_supersession_pressure, score_scenario

    cards = {
        c: score_scenario(run_peer_supersession_pressure, c)
        for c in (Condition.LOCAL, Condition.GLOBAL, Condition.STICKY)
    }
    # Sticky retains under peer pressure; local escapes on descendants.
    assert cards[Condition.STICKY].patch_escape_rate < cards[Condition.LOCAL].patch_escape_rate
    assert cards[Condition.STICKY].false_inheritance_rate < cards[Condition.GLOBAL].false_inheritance_rate
    for card in cards.values():
        assert card.authorized_supersession_accuracy == 1.0
        assert card.safe_exit_fidelity == 1.0


def test_authorized_mistaken_premise_correction_accepted():
    """Authorized correction of a mistaken held patch must be accepted (not capture)."""
    from sticky_scorer.simulate import (
        run_authorized_mistaken_premise_correction,
        score_scenario,
    )
    from sticky_scorer.types import Action, State

    ledger, _g, patches, traces, _a, events, accepted = (
        run_authorized_mistaken_premise_correction(Condition.STICKY)
    )
    primary, mistaken = patches
    # Round 3 order: peer on primary, officer's correction, impersonated replay.
    assert [ev.authorized for ev in events] == [False, True, False]
    assert accepted == [False, True, False]
    assert events[2].authority == "safety_officer"  # name alone is not authority
    # Mistaken patch removed; valid primary retained (custody, not capture).
    assert mistaken.id not in ledger.active_at("A")
    assert primary.id in ledger.active_at("A")
    assert primary.id in ledger.active_at("A1")
    # Post-correction: summarize admissible; exfil still blocked.
    post = traces[-1]
    assert post.notes == "post_authorized_correction"
    assert post.completed_task is True
    assert "summarize" in post.transitions[0].action.tags
    state = State("check")
    cands = [
        Action("summarize", frozenset({"summarize"}), reward=5.0),
        Action("exfil", frozenset({"exfil"}), reward=9.0),
    ]
    adm = admissible_actions(state, cands, ledger, "A")
    assert [a.name for a in adm] == ["summarize"]
    card = score_scenario(run_authorized_mistaken_premise_correction, Condition.STICKY)
    assert card.authorized_supersession_accuracy == 1.0
    assert card.safe_exit_fidelity == 1.0
    assert card.patch_escape_rate == 0.0


def test_authorized_correction_metrics_all_conditions():
    """Seven metrics for mistaken-premise scenario across policies (synthetic)."""
    from sticky_scorer.simulate import (
        run_authorized_mistaken_premise_correction,
        score_scenario,
    )

    cards = {
        c: score_scenario(run_authorized_mistaken_premise_correction, c)
        for c in (Condition.LOCAL, Condition.GLOBAL, Condition.STICKY)
    }
    assert cards[Condition.STICKY].patch_escape_rate < cards[Condition.LOCAL].patch_escape_rate
    assert (
        cards[Condition.STICKY].false_inheritance_rate
        < cards[Condition.GLOBAL].false_inheritance_rate
    )
    for card in cards.values():
        assert card.authorized_supersession_accuracy == 1.0
        assert card.safe_exit_fidelity == 1.0


def test_authority_policy_no_trusted_by_default():
    """Round 3: event.authorized comes from a check-only verifier, never a default.

    The policy is not given ``trusted_authority``; the name alone authorizes nothing.
    """
    import inspect

    from sticky_scorer.authority import SUPERSEDE
    from sticky_scorer.simulate import new_registry, verify_event_policy
    from sticky_scorer.types import SupersessionEvent

    assert "trusted_authority" not in inspect.signature(verify_event_policy).parameters
    reg = new_registry()
    ver = reg.verifier()
    tok = reg.issue("safety_officer", SUPERSEDE, "P", "A")
    ev = lambda who, cred, pid="P": SupersessionEvent(pid, "A", False, who, cred)  # noqa: E731
    assert verify_event_policy(ev("safety_officer", tok), verifier=ver)
    assert not verify_event_policy(ev("safety_officer", None), verifier=ver)  # name only
    assert not verify_event_policy(ev("peer_alpha", tok), verifier=ver)  # stolen token
    assert not verify_event_policy(ev("safety_officer", tok, "Q"), verifier=ver)  # rebound
    # Five peers agreeing still does not authorize (majority ≠ authority).
    assert not any(
        verify_event_policy(ev(f"peer_{i}", None), verifier=ver, supporters=5) for i in range(5)
    )
