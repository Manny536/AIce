"""Tests for src/sticky_scorer/concurrency_adapter.py (AIce#9, mapping to the scorer).

Goal: pin, by running both, what the current sticky_scorer represents of the
transition system and where it differs.
Why: the issue asks for an honest mapping. A pinned difference cannot drift
into a claim the code does not support.
How checked: every reachable registry log of three event menus is replayed in
the model and in a verifier-equipped CustodyLedger; differences are classified.
The scorer modules are not modified.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sticky_scorer import concurrency_adapter as ad
from sticky_scorer import concurrency_model as cm

EXP = cm.load_expected()
CONFIGS = ["authority", "authority_dup", "authority_scope"]
SRC = Path(__file__).resolve().parents[1] / "src" / "sticky_scorer"


def _logs():
    for c in CONFIGS:
        spec = cm.config_spec(EXP, c)
        for st in ad.reachable_registry_states(spec):
            yield c, spec, st


def _run(names, **kw):
    spec = cm.make_spec(EXP, "SN_OLD", names)
    st = cm.replay(spec, names)[-1]
    return spec, st, ad.replay_in_scorer(EXP, st.correction_registry.log, **kw)


def test_outcome_differences_have_exactly_two_causes_and_one_direction():
    causes = set()
    for _c, _spec, st in _logs():
        log = st.correction_registry.log
        run = ad.replay_in_scorer(EXP, log)
        for ev, (_n, got) in zip(log, run.outcomes):
            if ev.outcome != got:
                causes.add((ev.kind, ev.reason, ev.outcome, got))
    assert causes == {("supersede", "not_active", "refused", "accepted"),
                      ("attach", "duplicate", "refused", "accepted")}


def test_scorer_never_refuses_what_the_model_accepts():
    for _c, _spec, st in _logs():
        log = st.correction_registry.log
        run = ad.replay_in_scorer(EXP, log)
        assert not [1 for ev, (_n, got) in zip(log, run.outcomes) if ev.outcome == "accepted" and got == "refused"]


def test_membership_differs_only_where_a_replayed_attach_follows_a_supersession():
    differing, explained = 0, 0
    for _c, _spec, st in _logs():
        log = st.correction_registry.log
        run = ad.replay_in_scorer(EXP, log)
        same = (ad.model_seat_holds(st) == ad.scorer_holds(run, ad.SEAT_NODE)
                and ad.model_other_holds(st) == ad.scorer_holds(run, ad.OTHER_NODE))
        accepted_sup = set()
        resurrect = False
        for ev, (_n, got) in zip(log, run.outcomes):
            if ev.kind == "supersede" and ev.outcome == "accepted":
                accepted_sup.add(ev.cid)
            if ev.kind == "attach" and ev.outcome == "refused" and ev.cid in accepted_sup and got == "accepted":
                resurrect = True
        if not same:
            differing += 1
            explained += resurrect
    assert differing > 0 and differing == explained


def test_a_replayed_attach_token_resurrects_a_superseded_correction_in_the_scorer():
    names = ["Correct(K1)", "Supersede(S_good)", "Correct(K1_dup)"]
    spec = cm.make_spec(EXP, "SN_OLD", names)
    st = cm.replay(spec, names)[-1]
    run = ad.replay_in_scorer(EXP, st.correction_registry.log)
    assert cm.observe(spec, st)["registry"] == {"K1": "SUPERSEDED"}
    assert ad.model_seat_holds(st) == frozenset()
    assert ad.scorer_holds(run) == frozenset({"K1"})
    assert [o for _n, o in run.outcomes] == ["accepted", "accepted", "accepted"]
    assert ad.scorer_blocks_removal(run) and not ad.model_seat_holds(st)


def test_guarded_adapter_agrees_with_the_model_on_every_log():
    for c in CONFIGS:
        assert ad.differences(EXP, cm.config_spec(EXP, c), guard=True) == []


def test_without_the_guard_the_scorer_differs_from_the_model():
    assert any(ad.differences(EXP, cm.config_spec(EXP, c)) for c in CONFIGS)


def test_replayed_supersession_token_is_accepted_by_the_scorer_and_refused_by_the_model():
    names = ["Correct(K1)", "Supersede(S_good)"]
    spec, st, run = _run(names)
    again = list(st.correction_registry.log) + [st.correction_registry.log[-1]]
    run2 = ad.replay_in_scorer(EXP, again)
    assert [o for _n, o in run2.outcomes] == ["accepted", "accepted", "accepted"]
    log2 = cm.replay(cm.make_spec(EXP, "SN_OLD", names + ["Supersede(S_good)"]), names)[-1]
    assert not [lab for lab, _ in cm.successors(spec, log2) if lab == "Supersede(S_good)"]
    guarded = ad.replay_in_scorer(EXP, again, guard=True)
    assert [o for _n, o in guarded.outcomes] == ["accepted", "accepted", "refused"]


def test_flag_alone_is_refused_with_a_verifier_and_trusted_without_one():
    names = ["Correct(K1)", "Supersede(S_flag)"]
    spec = cm.make_spec(EXP, "SN_OLD", names)
    log = cm.replay(spec, names)[-1].correction_registry.log
    with_v = ad.replay_in_scorer(EXP, log, verifier=True)
    without = ad.replay_in_scorer(EXP, log, verifier=False)
    assert with_v.outcomes[-1] == ("S_flag", "refused") and ad.scorer_holds(with_v) == {"K1"}
    assert without.outcomes[-1] == ("S_flag", "accepted") and ad.scorer_holds(without) == frozenset()


def test_peer_agreement_and_a_worker_attach_are_refused_by_the_scorer():
    names = ["Correct(K1)", "Correct(K3)", "Supersede(S_peer)"]
    spec = cm.make_spec(EXP, "SN_OLD", names)
    log = cm.replay(spec, names)[-1].correction_registry.log
    run = ad.replay_in_scorer(EXP, log)
    assert [o for _n, o in run.outcomes] == ["accepted", "refused", "refused"]


def test_token_for_attach_is_not_a_token_for_supersede_in_the_scorer():
    names = ["Correct(K1)", "Supersede(S_stale)"]
    spec = cm.make_spec(EXP, "SN_OLD", names)
    run = ad.replay_in_scorer(EXP, cm.replay(spec, names)[-1].correction_registry.log)
    assert run.outcomes[-1] == ("S_stale", "refused") and ad.scorer_holds(run) == {"K1"}


def test_correction_for_another_branch_does_not_enter_this_branch_in_the_scorer():
    names = ["Correct(K2)"]
    _spec, st, run = _run(names)
    assert ad.scorer_holds(run, ad.SEAT_NODE) == frozenset()
    assert ad.scorer_holds(run, ad.OTHER_NODE) == {"K2"}
    assert not ad.scorer_blocks_removal(run, ad.SEAT_NODE)
    assert ad.scorer_blocks_removal(run, ad.OTHER_NODE)


def test_sticky_custody_reaches_the_child_of_the_corrected_node():
    names = ["Correct(K1)"]
    _spec, _st, run = _run(names)
    assert ad.scorer_holds(run, ad.SEAT_CHILD) == {"K1"}
    assert ad.scorer_blocks_removal(run, ad.SEAT_CHILD)


def test_decision_gate_agrees_with_model_wherever_membership_agrees():
    checked = 0
    for _c, _spec, st in _logs():
        run = ad.replay_in_scorer(EXP, st.correction_registry.log)
        if ad.model_seat_holds(st) == ad.scorer_holds(run):
            assert ad.scorer_blocks_removal(run) == bool(ad.model_seat_holds(st))
            assert ad.scorer_blocks_removal(run, ad.SEAT_CHILD) == bool(ad.model_seat_holds(st))
            checked += 1
    assert checked > 100


def test_scorer_blocking_is_advisory_the_model_gate_is_what_withholds_a_release():
    """admissible_actions only filters a candidate list; nothing in the scorer stops a caller
    from executing an action it did not return, nor recalls a decision already made."""
    names = ["Correct(K1)"]
    _spec, _st, run = _run(names)
    assert ad.scorer_blocks_removal(run)  # advisory answer
    text = (SRC / "admissibility.py").read_text(encoding="utf-8")
    assert "commit" not in text and "recall" not in text.lower()


@pytest.mark.parametrize("word", ["snapshot", "policy_version", "commit_version", "idempot",
                                  "crash", "retry", "interleav", "freshness", "inactive", "unknown_class"])
def test_scorer_modules_have_no_representation_of(word):
    for mod in ("types.py", "custody.py", "admissibility.py", "authority.py"):
        assert word.lower() not in (SRC / mod).read_text(encoding="utf-8").lower(), (word, mod)


def test_adapter_does_not_import_a_change_into_the_scorer():
    """The adapter builds its own ledger, registry and graph per replay."""
    a = ad.replay_in_scorer(EXP, [])
    b = ad.replay_in_scorer(EXP, [])
    assert a.ledger is not b.ledger and a.registry is not b.registry


def test_review_n6_supersession_before_its_hold_in_both_orders():
    """grok-terminal#13 N6, replayed. The model refuses the premature supersession; the
    scorer accepts it and records it, yet the hold that arrives next is held, also at the child."""
    early = ["Supersede(S_good)", "Correct(K1)"]
    spec, st, run = _run(early)
    assert [(e.name, e.outcome) for e in st.correction_registry.log] == [("S_good", "refused"), ("K1", "accepted")]
    assert [o for _n, o in run.outcomes] == ["accepted", "accepted"]
    assert ad.scorer_holds(run) == {"K1"} == ad.scorer_holds(run, ad.SEAT_CHILD)
    assert ad.scorer_blocks_removal(run)
    guarded = ad.replay_in_scorer(EXP, st.correction_registry.log, guard=True)
    assert [o for _n, o in guarded.outcomes] == ["refused", "accepted"]
    late = ["Correct(K1)", "Supersede(S_good)"]
    _spec2, _st2, run2 = _run(late)
    assert ad.scorer_holds(run2) == frozenset() == ad.scorer_holds(run2, ad.SEAT_CHILD)
    assert not ad.scorer_blocks_removal(run2)
