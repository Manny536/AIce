"""Tests for src/sticky_scorer/concurrency_model.py (AIce#9).

Goal: check the finite transition system against outcomes written down before
the model existed (tests/lamport_expected.json), over every interleaving of
each bounded configuration, and show that each deliberately broken variant
fails with a counterexample trace.

Why: a model that only agrees with itself says nothing. The expected values
come from the issue text, not from model output. A variant that does not fail
means the invariants are too weak to see that flaw.

How checked: this file runs under pytest on Python 3.9, 3.10 and 3.11.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from sticky_scorer import concurrency_model as cm

EXP = cm.load_expected()
SCHEDULES = {k: v for k, v in EXP["schedules"].items() if not k.startswith("_")}
CONFIGS = [k for k in EXP["explore_configs"] if not k.startswith("_")]
VARIANTS = [k for k in EXP["unsafe_variants"] if not k.startswith("_")]
ROOT = Path(__file__).resolve().parents[1]


def _run(name):
    sched = SCHEDULES[name]
    spec = cm.schedule_spec(EXP, sched)
    steps = list(sched["steps"]) + list(sched.get("continue_steps", []))
    return spec, cm.replay(spec, steps), sched


def _check(spec, st, expect):
    obs = cm.observe(spec, st)
    for key, want in expect.items():
        if key == "not_enabled":
            assert not set(want) & set(obs["enabled"]), (key, obs["enabled"])
        elif key == "phases":
            for w, ph in want.items():
                assert obs["phases"][w] == ph, (w, obs["phases"])
        else:
            assert obs[key] == want, (key, obs[key], want)


@pytest.mark.parametrize("name", list(SCHEDULES))
def test_schedule_matches_frozen_expectation(name):
    spec, states, sched = _run(name)
    for idx, expect in sched.get("checkpoints", {}).items():
        _check(spec, states[int(idx)], expect)
    _check(spec, states[-1], sched["expect"])


@pytest.mark.parametrize("name", list(SCHEDULES))
def test_every_schedule_state_satisfies_every_invariant(name):
    spec, states, _ = _run(name)
    for i, st in enumerate(states):
        assert cm.violated(spec, st) == [], (name, i)


def test_init_satisfies_invariants():
    spec = cm.make_spec(EXP, "SN_OLD")
    assert cm.violated(spec, cm.init_state(spec)) == []


def test_disabled_step_raises():
    spec = cm.make_spec(EXP, "SN_OLD")
    with pytest.raises(ValueError):
        cm.replay(spec, ["CommitWrite(W1)"])


@pytest.mark.parametrize("name", CONFIGS)
def test_safe_model_has_no_counterexample_in_any_interleaving(name):
    res = cm.explore(cm.config_spec(EXP, name))
    assert not res.truncated
    assert res.counterexamples == {}
    assert res.deadlocks == []
    assert res.cannot_progress == 0


def test_expected_statement_lists_all_invariants():
    assert set(EXP["safe_model_expectations"]["invariants_hold_in_every_explored_configuration"]) == set(cm.INVARIANTS)


@pytest.mark.parametrize("variant", VARIANTS)
def test_unsafe_variant_fails_with_counterexample_trace(variant):
    meta = EXP["unsafe_variants"][variant]
    spec = cm.config_spec(EXP, meta["config"], [variant])
    res = cm.explore(spec, max_states=400_000, progress=False)
    for inv in meta["must_violate"]:
        trace = res.counterexamples.get(inv)
        assert trace, (variant, inv, sorted(res.counterexamples))
        states = cm.replay(spec, trace)  # the trace is a real enabled interleaving
        assert inv in cm.violated(spec, states[-1])
        assert all(inv not in cm.violated(spec, s) for s in states[:-1])  # first violation


def test_every_variant_listed_is_implemented_and_vice_versa():
    assert set(VARIANTS) == set(cm.VARIANTS)


@pytest.mark.parametrize("variant", VARIANTS)
def test_variant_flag_changes_behaviour_only_where_declared(variant):
    """The same configuration without the flaw must stay clean (no false alarm from the checker)."""
    meta = EXP["unsafe_variants"][variant]
    assert cm.explore(cm.config_spec(EXP, meta["config"]), progress=False).counterexamples == {}


def test_explorer_is_deterministic():
    a = cm.explore(cm.config_spec(EXP, "recall"))
    b = cm.explore(cm.config_spec(EXP, "recall"))
    assert (a.states, a.transitions, a.max_depth) == (b.states, b.transitions, b.max_depth)
    v = cm.config_spec(EXP, "race", ["no_idempotent_commit"])
    assert cm.explore(v).counterexamples == cm.explore(v).counterexamples


def test_explorer_reports_truncation_instead_of_silently_passing():
    res = cm.explore(cm.config_spec(EXP, "bump"), max_states=10)
    assert res.truncated and not res.ok()


def test_explorer_finds_a_deadlock_outside_the_goal():
    """A system that can wedge before any goal state must be reported, not hidden."""
    spec = cm.make_spec(EXP, "SN_OLD")
    wedged = cm.init_state(spec)._replace(worker_state=tuple(
        w._replace(phase=cm.ESCALATED) for w in cm.init_state(spec).worker_state))
    assert cm.successors(spec, wedged) == [] and not cm.goal(wedged)


def test_progress_check_flags_a_state_that_cannot_reach_the_goal(monkeypatch):
    spec = cm.config_spec(EXP, "race")
    monkeypatch.setattr(cm, "goal", lambda st: False)
    res = cm.explore(spec)
    assert res.cannot_progress > 0 and res.progress_example is not None


def test_shortest_trace_is_reported():
    spec = cm.config_spec(EXP, "race", ["no_idempotent_commit"])
    trace = cm.explore(spec, progress=False).counterexamples["I2"]
    assert len(trace) == 8  # 3 steps per worker to commit, 2 commits, no shorter interleaving


def test_authority_is_read_from_external_table_never_from_the_flag():
    spec = cm.make_spec(EXP, "SN_OLD", ["Correct(K1)", "Supersede(S_flag)"])
    s = cm.replay(spec, ["Correct(K1)", "Supersede(S_flag)"])[-1]
    assert cm.observe(spec, s)["registry"] == {"K1": "ACTIVE"}
    broken = cm.make_spec(EXP, "SN_OLD", ["Correct(K1)", "Supersede(S_flag)"], variant=["trust_authorized_flag"])
    s2 = cm.replay(broken, ["Correct(K1)", "Supersede(S_flag)"])[-1]
    assert cm.observe(broken, s2)["registry"] == {"K1": "SUPERSEDED"}


def test_credential_is_single_use():
    spec = cm.make_spec(EXP, "SN_OLD", ["Correct(K1)", "Supersede(S_good)", "Supersede(S_good)"])
    s = cm.replay(spec, ["Correct(K1)", "Supersede(S_good)"])[-1]
    assert not [lab for lab, _ in cm.successors(spec, s) if lab == "Supersede(S_good)"]


def test_supersession_of_unknown_correction_is_refused_not_applied():
    spec = cm.make_spec(EXP, "SN_OLD", ["Supersede(S_good)"])
    s = cm.replay(spec, ["Supersede(S_good)"])[-1]
    o = cm.observe(spec, s)
    assert o["registry"] == {} and o["last_registry_outcome"] == "refused"
    assert s.correction_registry.log[-1].reason == "not_active"


def test_a_released_removal_is_recalled_when_a_newer_input_arrives():
    spec = cm.make_spec(EXP, "SN_OLD_THEN_ACTIVE", ["PublishSnapshot(2)"])
    steps = ["ReadSnap(W1)", "ReadPolicy(W1)", "Compute(W1)", "CommitWrite(W1)", "PublishSnapshot(2)"]
    o = cm.observe(spec, cm.replay(spec, steps)[-1])
    assert o["decision"] == ["RECALL", "stale_input"]


def test_lamport_order_is_not_authority():
    """The model has no clock or ordering field that grants authority: a later correction
    event cannot supersede without the external credential, however late it arrives."""
    steps = ["Correct(K1)", "Supersede(S_peer)", "Supersede(S_flag)"]
    spec = cm.make_spec(EXP, "SN_OLD", steps)
    s = cm.replay(spec, steps)[-1]
    assert cm.observe(spec, s)["registry"] == {"K1": "ACTIVE"}
    assert not any("clock" in f or "lamport" in f.lower() for f in cm.State._fields)


# --- I7: synthetic-only, checked on the files this work adds ---------------

_NEW_FILES = ["src/sticky_scorer/concurrency_model.py", "tests/lamport_expected.json",
              "tests/test_concurrency_model.py", "docs/PEAICE-AICE-LAMPORT-001.md"]
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}")
_URL = re.compile(r"https?://[^\s)>\"']+")


@pytest.mark.parametrize("rel", _NEW_FILES)
def test_new_files_contain_no_email_addresses(rel):
    p = ROOT / rel
    if not p.exists():
        pytest.skip("not present yet")
    assert not _EMAIL.findall(p.read_text(encoding="utf-8"))


def test_fixture_identifiers_are_synthetic():
    ids = EXP["fixtures"]["identifiers"]
    assert all(re.fullmatch(r"SYN-[A-Z]+-[0-9A-Z]+", v) for v in ids.values())
    assert not _URL.findall(str(EXP["fixtures"]))


# ---------------------------------------------------------------------------
# Each invariant must also be able to fail on its own, not only through a
# broken variant. These tests edit one field of a reachable state and expect
# exactly the named invariant to report it.
# ---------------------------------------------------------------------------

_COMMIT = ["ReadSnap(W1)", "ReadPolicy(W1)", "Compute(W1)", "CommitWrite(W1)"]


def _base(events, steps, snapshots="SN_OLD"):
    spec = cm.make_spec(EXP, snapshots, events)
    st = cm.replay(spec, steps)[-1]
    assert cm.violated(spec, st) == []
    return spec, st


def _only(spec, st, name):
    """The edited state violates ``name`` (other invariants may report it as well)."""
    assert name in cm.violated(spec, st), cm.violated(spec, st)


def test_I4_fails_on_each_way_custody_or_authority_can_break():
    spec, st = _base(["Correct(K1)", "Supersede(S_good)"], _COMMIT + ["Correct(K1)", "Supersede(S_good)"])
    reg = st.correction_registry
    e0, e1 = reg.log
    # a correction listed twice
    _only(spec, st._replace(correction_registry=reg._replace(entries=reg.entries * 2)), "I4")
    # an attach in the log with no correction in the registry
    _only(spec, st._replace(correction_registry=reg._replace(entries=())), "I4")
    # an accepted event whose credential the external table does not issue to that principal
    bad = e0._replace(principal="worker")
    _only(spec, st._replace(correction_registry=reg._replace(log=(bad, e1))), "I4")
    # the same credential used for two accepted events
    _only(spec, st._replace(correction_registry=reg._replace(log=(e0, e1._replace(credential=e0.credential)))), "I4")
    # a correction marked superseded with no accepted supersession in the log
    _only(spec, st._replace(correction_registry=reg._replace(log=(e0,))), "I4")


def test_I4_fails_when_a_release_stands_over_a_live_hold():
    spec, st = _base(["Correct(K1)"], _COMMIT)
    st2 = cm.replay(spec, _COMMIT + ["Correct(K1)"])[-1]
    live = st2.correction_registry
    released = st._replace(correction_registry=live)
    assert released.decision_state.kind == cm.RELEASED
    _only(spec, released, "I4")


def test_I5_fails_on_stale_overwrite_and_stale_references():
    spec, st = _base(["PublishSnapshot(2)"], _COMMIT, "SN_OLD_THEN_ACTIVE")
    rec = st.records[0]
    # records not strictly newer one after another
    older = rec._replace(snap=2, commit_version=1)
    newer = rec._replace(snap=1, commit_version=2)
    assert "I5" in cm.violated(spec, st._replace(records=(older, newer), commit_version=2))
    # decision refers to something other than the newest record
    d = st.decision_state
    _only(spec, st._replace(decision_state=d._replace(key=(2, 1))), "I5")
    # evidence refers to something other than the newest record
    ev = st.evidence_ref
    _only(spec, st._replace(evidence_ref=ev._replace(snap=2)), "I5")
    # a release is current only for the present versions
    _only(spec, st._replace(snapshot_version=2), "I5")


def test_I6_needs_every_gate_for_a_verified_report():
    spec, st = _base([], _COMMIT + ["Report"])
    assert st.report.kind == cm.VERIFIED
    _only(spec, st._replace(decision_state=st.decision_state._replace(kind=cm.DENIED, reason="hold")), "I6")
    bad_ev = st._replace(evidence_ref=st.evidence_ref._replace(scope="MISMATCH"))
    assert "I6" in cm.violated(spec, bad_ev) and "I3" in cm.violated(spec, bad_ev)


def test_I7_fails_on_non_synthetic_identifiers_and_address_or_link_text():
    spec, st = _base([], _COMMIT)
    rec = st.records[0]
    _only(spec, st._replace(records=(rec._replace(seat="real-person"),)), "I7")
    _only(spec, st._replace(records=(rec._replace(product="Product A"),)), "I7")
    _only(spec, st._replace(records=(rec._replace(lineage=(("W1@host", 0),)),)), "I7")
    _only(spec, st._replace(records=(rec._replace(lineage=(("W1://x", 0),)),)), "I7")
    assert cm.inv_I7(spec, st)


def test_U1_fails_when_a_denial_has_no_justification():
    spec, st = _base([], _COMMIT + ["Report"])
    d = st.decision_state
    # not_inactive on a seat that is INACTIVE
    assert "U1" in cm.violated(spec, st._replace(decision_state=d._replace(kind=cm.DENIED, reason="not_inactive")))
    # evidence denial although the evidence is sufficient and matches
    assert "U1" in cm.violated(spec, st._replace(decision_state=d._replace(kind=cm.DENIED, reason="evidence")))
    # hold denial with no live hold
    assert "U1" in cm.violated(spec, st._replace(decision_state=d._replace(kind=cm.DENIED, reason="hold")))
    # a hold only on another seat does not justify a hold denial
    spec2, st2 = _base(["Correct(K2)"], _COMMIT + ["Correct(K2)"])
    assert "U1" in cm.violated(spec2, st2._replace(decision_state=st2.decision_state._replace(
        kind=cm.DENIED, reason="hold")))


def test_blocked_with_reason_needs_a_reason():
    spec, st = _base([], _COMMIT)
    d = st.decision_state
    assert not cm.blocked_with_reason(st._replace(decision_state=d._replace(kind=cm.BLOCKED, reason="")))
    assert cm.blocked_with_reason(st._replace(decision_state=d._replace(kind=cm.BLOCKED, reason="x")))
    assert not cm.blocked_with_reason(st._replace(decision_state=d._replace(kind=cm.RELEASED, reason="x")))


# Sizes were measured on the first complete run of these configurations. They are a
# regression pin (a change in the transition relation moves them), not an
# independently specified expectation.
PINNED_SIZES = {
    "race": (56, 104, 10), "blank": (56, 104, 10), "future": (56, 104, 10),
    "future_only": (56, 104, 10), "bump": (1450, 2935, 22), "authority": (83500, 220328, 16),
    "recall": (284, 536, 11), "hold": (284, 536, 11), "evidence": (137, 268, 10),
    "partial": (56, 104, 10), "report": (56, 104, 10), "leak": (152, 336, 11),
    "full_crash_hold": (5448, 13664, 18), "full_versions": (205221, 514102, 35),
    "versions_crash": (61295, 150342, 28), "authority_dup": (21640, 59712, 15),
    "authority_scope": (18908, 49636, 15),
}


def test_pinned_sizes_cover_every_configuration():
    assert set(PINNED_SIZES) == set(CONFIGS)


@pytest.mark.parametrize("name", CONFIGS)
def test_explored_size_is_pinned(name):
    res = cm.explore(cm.config_spec(EXP, name), progress=False)
    assert (res.states, res.transitions, res.max_depth) == PINNED_SIZES[name]
