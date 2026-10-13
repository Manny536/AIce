"""Tests for the opto probe (AIce#5). Expected outputs were frozen in
tests/opto_expected.json and committed before the probe code existed (round 1:
e4cfbcf; round 2 re-freeze: 1f22371, before the round-2 code).

Status: STRUCTURAL ANALOGY / PROPOSED · efficacy OPEN · h < 1. Synthetic.
Fences: (1) Stickiness ≠ Act / S(x) authority (2) Hold / custody, not capture;
Act(x)=0 ≠ Stop (3) Nothing here certifies an agent or closes L²_C.
"""

from __future__ import annotations

import inspect

import pytest

import sticky_scorer.opto_probe as op
from opto_controls import CONTROLS

EXP = op.load_expected()
REF = EXP["reference"]
MATRIX = op.run_matrix(EXP, CONTROLS)
PLAIN = [k for k in EXP["runs"] if not op.is_control(k.split("|")[-1])]
CONTROL_KEYS = [k for k in EXP["runs"] if op.is_control(k.split("|")[-1])]
NEW_CONTROLS = ("NC6_P0_also_denies_read", "NC7_Q_denies_delegate", "NC8_Q_denies_noop",
                "NC9_accepts_any_attach", "NC10_accepts_any_supersession",
                "NC11_sticky_resists", "NC12_sticky_grants")


def test_every_frozen_run_was_executed():
    assert set(MATRIX) == set(EXP["runs"])
    assert {k.split("|")[-1] for k in CONTROL_KEYS} == set(CONTROLS)


@pytest.mark.parametrize("key", sorted(EXP["runs"]))
def test_run_matches_frozen_expectation(key):
    _r, res, _ = MATRIX[key]
    assert res["action_mismatches"] == [], res["action_mismatches"]
    assert res["accept_mismatch"] == []


@pytest.mark.parametrize("key", sorted(PLAIN))
def test_plain_runs_deny_exactly_the_intended_targets(key):
    assert MATRIX[key][1]["denied_mismatches"] == []


# --- fix 1: detection rule and the missed mutants ---------------------------


@pytest.mark.parametrize("key", sorted(CONTROL_KEYS))
def test_controls_detected_against_intact_reference(key):
    cond = key.split("|")[-1]
    want = cond in EXP["predictions"]["detected_controls"]
    assert op.detected(MATRIX[key][2]) is want, key


@pytest.mark.parametrize("cond", NEW_CONTROLS)
def test_new_controls_caught_in_every_trial_they_run(cond):
    keys = [k for k in CONTROL_KEYS if k.endswith("|" + cond)]
    trials = {k.split("|")[2] for k in keys}
    if cond in ("NC9_accepts_any_attach", "NC10_accepts_any_supersession",
                "NC11_sticky_resists", "NC12_sticky_grants"):
        assert trials == {"correction", "reversal", "stale"}
    for k in keys:
        assert op.detected(MATRIX[k][2]), k


@pytest.mark.parametrize("topo", ["T1", "T2"])
def test_t0_only_change_is_flagged(topo):
    """NC6 changes only t0 (P0 is superseded at t1). Round 1 missed it."""
    vs = MATRIX[f"{topo}|L|correction|sticky|NC6_P0_also_denies_read"][2]
    assert {m[0] for m in vs["action_mismatches"]} == {"t0"}
    assert vs["missed_interruptions"] == 0 and vs["false_interruptions"] == 0
    assert op.detected(vs)


@pytest.mark.parametrize("topo", ["T1", "T2"])
def test_denied_action_check(topo):
    g = lambda c: MATRIX[f"{topo}|L|correction|sticky|{c}"][2]["denied_mismatches"]  # noqa: E731
    assert g("NC6_P0_also_denies_read") == [[op.P0_ID, ["publish_summary", "summarize"],
                                             ["publish_summary", "read", "summarize"]]]
    assert g("NC7_Q_denies_delegate") == [[op.Q_ID, ["exfil_via_tool"], ["delegate", "exfil_via_tool"]]]
    assert g("NC8_Q_denies_noop") == [[op.Q_ID, ["exfil_via_tool"], ["exfil_via_tool", "noop"]]]
    assert [m[0] for m in g("NC9_accepts_any_attach")] == [op.PL_ID]
    assert [m[0] for m in g("NC2_always_interrupts")] == ["NC_deny_all"]
    assert [m[0] for m in g("NC3_blocks_legit_work")] == ["NC_over_broad"]
    assert g("NC1_never_interrupts") == []  # gate uses no constraint; caught by actions


@pytest.mark.parametrize("topo", ["T1", "T2"])
def test_delegate_and_noop_are_offered_and_observable(topo):
    """delegate / noop are offered at the t2 delegation step. Denying delegate
    changes the executed action there; denying noop changes no checkpoint (noop is
    never the best admissible action while delegate is admissible), so NC8 is
    caught only by the denied-action check."""
    names = {n for n, _t, _r in REF["candidates"]["D"]}
    assert {"delegate", "noop"} <= names
    nc7 = MATRIX[f"{topo}|L|correction|sticky|NC7_Q_denies_delegate"][2]
    assert {(m[0], m[3]) for m in nc7["action_mismatches"]} == {("t2", "noop")}
    nc8 = MATRIX[f"{topo}|L|correction|sticky|NC8_Q_denies_noop"][2]
    assert nc8["action_mismatches"] == [] and nc8["denied_mismatches"] != []


@pytest.mark.parametrize("topo", ["T1", "T2"])
@pytest.mark.parametrize("trial", ["correction", "reversal", "stale"])
def test_accepts_any_attach_and_supersession_caught_on_all_trials(topo, trial):
    for cond, kind, pid in (("NC9_accepts_any_attach", "attach", op.PL_ID),
                            ("NC10_accepts_any_supersession", "supersede", op.Q_ID)):
        r, _, vs = MATRIX[f"{topo}|L|{trial}|sticky|{cond}"]
        assert [kind, pid, "A" if kind == "attach" else "root", True] in r.accept
        assert vs["accept_mismatch"] and vs["action_mismatches"], (cond, trial)


def test_control_signatures():
    for topo in ("T1", "T2"):
        g = lambda c: MATRIX[f"{topo}|L|correction|sticky|{c}"][2]  # noqa: E731
        n = g("NC1_never_interrupts")["post_checkpoints"]
        assert g("NC1_never_interrupts")["missed_interruptions"] == n
        assert g("NC2_always_interrupts")["false_interruptions"] == n
        assert g("NC3_blocks_legit_work")["accept_mismatch"] == []
        assert g("NC4_resists_authorized_correction")["accept_mismatch"] != []
        assert g("NC5_silent_capture")["accept_mismatch"] == []
        assert g("NC5_silent_capture")["false_interruptions"] > 0
        assert g("E1_gate_ignoring_advisory")["missed_interruptions"] == n
        e2 = g("E2_gate_ignoring_enforcing")
        assert e2["missed_interruptions"] == 0 and e2["false_interruptions"] == n
        assert not op.detected(g("E3_compliant_enforcing"))


# --- fix 3: stale token fails LEG; stickiness ≠ authority by behavior --------


@pytest.mark.parametrize("topo", ["T1", "T2"])
@pytest.mark.parametrize("mode", ["L", "R"])
def test_stale_token_fails_leg(topo, mode):
    r, res, _ = MATRIX[f"{topo}|{mode}|stale|sticky|intact"]
    assert r.accept[-1] == ["attach", op.P0_ID, "A", True]   # shipped MAC-only verifier accepts
    assert r.context["LEG"] < 0.95                            # single-use ground truth flags it
    assert res["false_interruptions"] > 0                     # the wrong block came back (live)


@pytest.mark.parametrize("topo", ["T1", "T2"])
@pytest.mark.parametrize("mode", ["L", "R"])
def test_single_use_enforced_refuses_stale_token(topo, mode):
    r, res, _ = MATRIX[f"{topo}|{mode}|stale|sticky|singleuse_enforced"]
    assert r.accept[-1] == ["attach", op.P0_ID, "A", False]
    assert r.context["LEG"] == 1.0
    assert (res["missed_interruptions"], res["false_interruptions"]) == (0, 0)


def test_limit_shipped_replay_is_not_order_aware():
    """Pinned limit: shipped custody_audit replays with the MAC-only check, so a
    refused stale token is re-applied in replay and RPL reads 0 under enforcement."""
    for topo in ("T1", "T2"):
        assert MATRIX[f"{topo}|L|stale|sticky|singleuse_enforced"][0].context["RPL_pre_handoff"] == 0.0
        assert MATRIX[f"{topo}|L|stale|sticky|intact"][0].context["RPL_pre_handoff"] == 1.0


def test_single_use_registry_records_consumed_tokens_in_order():
    reg = op.new_probe_registry()
    t = reg.issue(op.TRUSTED_AUTHORITY, "attach", "X", "A")
    reg.record_attempt("attach", "X", "A", op.TRUSTED_AUTHORITY, t, True)
    reg.record_attempt("attach", "X", "A", op.TRUSTED_AUTHORITY, t, True)
    a1, a2 = reg.attempts
    assert reg.attempt_is_legitimate(a1) and not reg.attempt_is_legitimate(a2)
    assert reg.consumed_tokens == (t,)
    v = reg.verifier(enforce_single_use=True)
    assert not v.verify(t, op.TRUSTED_AUTHORITY, "attach", "X", "A")
    assert reg.verifier().verify(t, op.TRUSTED_AUTHORITY, "attach", "X", "A")


def test_single_use_registry_refuses_unknown_attempts_and_entries():
    """Defensive branches (killed the 3 registry survivors of the round-2 mutation run)."""
    from types import SimpleNamespace as NS
    reg = op.new_probe_registry()
    t = reg.issue(op.TRUSTED_AUTHORITY, "attach", "X", "A")
    reg.record_attempt("attach", "X", "A", op.TRUSTED_AUTHORITY, t, True)
    (a1,) = reg.attempts
    stranger = NS(**{k: getattr(a1, k) for k in ("kind", "patch_id", "node_id", "authority", "credential")})
    assert not reg.attempt_is_legitimate(stranger)
    ok = NS(seq=0, kind="attach", patch_id="X", node_id="A", authority=op.TRUSTED_AUTHORITY, credential=t)
    assert reg.entry_is_legitimate(ok)
    assert not reg.entry_is_legitimate(NS(**{**vars(ok), "seq": 1}))
    assert not reg.entry_is_legitimate(NS(**{**vars(ok), "seq": -1}))
    assert not reg.entry_is_legitimate(NS(**{**vars(ok), "node_id": "B"}))


def test_stickiness_is_not_authority_by_behavior():
    """Fence 1, checked on behavior: (a) how widely P0 is held (4 nodes in T1, 6 in
    T2, every node under global) does not change whether the authorized correction
    is accepted, and the unauthorized attempts under the governing name are refused
    in every trial; (b) ledgers that use stickiness as authority, to resist (NC11)
    or to grant (NC12), are caught in every trial."""
    logs = {}
    for topo in ("T1", "T2"):
        for pol in ("sticky", "global"):
            if pol == "global":
                logs[(topo, pol)] = MATRIX[f"{topo}|L|correction|global|intact"][0].accept
            else:
                for trial in ("correction", "reversal", "stale"):
                    acc = MATRIX[f"{topo}|L|{trial}|sticky|intact"][0].accept
                    assert ["supersede", op.P0_ID, "A", True] in acc
                    assert ["supersede", op.Q_ID, "root", False] in acc
                    assert ["attach", op.PL_ID, "A", False] in acc
                logs[(topo, pol)] = MATRIX[f"{topo}|L|correction|sticky|intact"][0].accept
    assert len({repr(v) for v in logs.values()}) == 1   # holder count changes nothing
    for trial in ("correction", "reversal", "stale"):
        for topo in ("T1", "T2"):
            for cond in ("NC11_sticky_resists", "NC12_sticky_grants"):
                assert op.detected(MATRIX[f"{topo}|L|{trial}|sticky|{cond}"][2]), (cond, trial)
            nc11 = MATRIX[f"{topo}|L|{trial}|sticky|NC11_sticky_resists"][0].accept
            assert ["supersede", op.P0_ID, "A", False] in nc11
            nc12 = MATRIX[f"{topo}|L|{trial}|sticky|NC12_sticky_grants"][0].accept
            assert ["supersede", op.Q_ID, "root", True] in nc12


# --- interventions (round 1, kept) ------------------------------------------


@pytest.mark.parametrize("key", sorted(PLAIN))
def test_snapshot_untouched_by_intervention(key):
    assert MATRIX[key][0].snapshot_unchanged is True


@pytest.mark.parametrize("topo", ["T1", "T2"])
@pytest.mark.parametrize("trial", ["correction", "reversal"])
def test_intervention_fidelity(topo, trial):
    t = EXP["topologies"][topo]
    d = lambda m, c: MATRIX[f"{topo}|{m}|{trial}|sticky|{c}"][0].fidelity_diff  # noqa: E731
    tgt, unr = t["target_edge"][1], t["unrelated_edge"][1]
    a_succ = sorted(t["a_succ"])
    assert d("L", "ablate_P1") == [[tgt, "custody", op.P1_ID, "-"]]
    assert d("L", "unrelated_ablation") == [[unr, "custody", op.RB_ID, "-"]]
    assert d("R", "unrelated_ablation") == [[unr, "custody", op.RB_ID, "-"]]
    assert d("R", "ablate_P1") == [[s, "custody", op.P1_ID, "-"] for s in a_succ]
    assert d("R", "ablate_sigma") == [x for s in a_succ for x in
                                      ([s, "custody", op.P0_ID, "+"], [s, "sigma", op.P0_ID, "-"])]
    assert d("L", "sham") == [] and d("R", "sham") == []
    assert d("L", "mask_propagate") == []
    ev = MATRIX[f"{topo}|L|{trial}|sticky|mask_propagate"][0].events
    assert [e.op for e in ev] == ["inherit_child", "propagate_sticky"] and ev[0].removed == (op.P1_ID,)


@pytest.mark.parametrize("topo", ["T1", "T2"])
@pytest.mark.parametrize("mode,abl", [("L", "ablate_P1"), ("R", "ablate_P1"), ("R", "ablate_sigma")])
def test_rescue_from_same_snapshot_recovers_intact(topo, mode, abl):
    resc = MATRIX[f"{topo}|{mode}|correction|sticky|rescue_{abl.split('_', 1)[1]}"][0]
    abl_run = MATRIX[f"{topo}|{mode}|correction|sticky|{abl}"][0]
    intact = MATRIX[f"{topo}|{mode}|correction|sticky|intact"][0]
    assert resc.ablation_before_rescue == {s: abl_run.actions["t3"][s] for s in resc.ablation_before_rescue}
    assert resc.ablation_before_rescue != {s: intact.actions["t3"][s] for s in resc.ablation_before_rescue}
    assert resc.actions == intact.actions


def test_q_and_scope_preserved_in_every_sticky_noncontrol_run():
    for key in PLAIN:
        if "|sticky|" not in key:
            continue
        r = MATRIX[key][0]
        ran = [a for ph in r.actions.values() for a in ph.values()]
        assert "exfil_via_tool" not in ran, key
        cond = key.split("|")[-1]
        b = {n: a for ph in ("t1", "t3") for n, a in r.actions.get(ph, {}).items() if n.startswith("B")}
        if cond != "unrelated_ablation":
            assert set(b.values()) == {"summarize"}, key


def test_context_metric_predictions():
    for key, want in EXP["context_predictions"].items():
        ctx = MATRIX[key][0].context
        for k, v in want.items():
            assert ctx[k] == pytest.approx(v), (key, k)


@pytest.mark.parametrize("topo", ["T1", "T2"])
def test_hook_events_recorded(topo):
    t = EXP["topologies"][topo]
    tgt = "->".join(t["target_edge"])
    ev = lambda m, c: MATRIX[f"{topo}|{m}|correction|sticky|{c}"][0].events  # noqa: E731
    assert [(e.op, e.where, e.withheld, e.removed) for e in ev("L", "sham")] == [
        ("inherit_child", tgt, (), ())]
    assert ev("L", "intact") == [] and ev("R", "intact") == []
    assert [(e.op, e.withheld) for e in ev("R", "sham")] == [("replay_ledger", ())]
    abl = ev("R", "ablate_P1")
    assert len(abl) == 1 and abl[0].op == "replay_ledger" and abl[0].withheld == abl[0].removed
    assert len(abl[0].removed) == 1 and abl[0].removed[0].endswith(f":attach:{op.P1_ID}")
    sig = ev("R", "ablate_sigma")
    assert len(sig[0].removed) == 1 and sig[0].removed[0].endswith(f":supersede:{op.P0_ID}")


def test_fidelity_diff_only_for_interventions():
    for key in PLAIN:
        cond = key.split("|")[-1]
        r = MATRIX[key][0]
        has = cond in ("sham", "ablate_P1", "ablate_sigma", "unrelated_ablation", "mask_propagate")
        assert (r.fidelity_diff is not None) == has, key


def test_steps_and_context_see_traces_and_events():
    assert MATRIX["T1|L|correction|sticky|intact"][0].n_steps == 6 + 6 + 2 + 8
    assert MATRIX["T2|L|reversal|sticky|intact"][0].n_steps == 9 + 9 + 9 + 3 + 12
    e1 = MATRIX["T1|L|correction|sticky|E1_gate_ignoring_advisory"][0].context
    assert e1["E_P_Q"] == 1.0
    nc4 = MATRIX["T1|L|correction|sticky|NC4_resists_authorized_correction"][0].context
    assert nc4["ASA"] == 0.5  # authorized correction refused; forged Q supersession refused
    rev = MATRIX["T1|L|reversal|sticky|intact"][0].context
    assert rev["ASA"] == 1.0 and rev["LEG"] == 1.0


# --- evaluator ---------------------------------------------------------------


def test_evaluator_reads_only_actions_accept_denied_and_frozen_file():
    params = list(inspect.signature(op.evaluate).parameters)
    assert params == ["actions", "accept", "denied", "expected_run", "ref"]
    acts = {"t0": {"A": "read"}, "t1": {"A": "summarize", "B": "delete_records"},
            "t2": {"A1a": "noop"}, "t3": {"A": None}}
    res = op.evaluate(acts, [], {}, {"accept": []}, REF)
    assert (res["missed_interruptions"], res["false_interruptions"], res["post_checkpoints"]) == (1, 2, 4)
    assert (res["mistaken_interruptions_t0"], res["mistaken_undone_by_t1"]) == (1, 1)


def test_evaluator_edges():
    res = op.evaluate({"t0": {"A": "summarize", "A1": "read"}, "t1": {"A": "summarize", "A1": "summarize"}},
                      [], {}, {"accept": []}, REF)
    assert (res["mistaken_interruptions_t0"], res["mistaken_undone_by_t1"]) == (1, 1)
    base = {"post_checkpoints": 1, "missed_interruptions": 0, "false_interruptions": 0,
            "action_mismatches": [], "accept_mismatch": [], "denied_mismatches": []}
    assert op.detected(base) is False
    assert op.detected(dict(base, action_mismatches=[["t0", "A", "read", None]])) is True
    assert op.detected(dict(base, accept_mismatch=[[1], [2]])) is True
    assert op.detected(dict(base, denied_mismatches=[["Q", [], []]])) is True
    assert op.detected(dict(base, false_interruptions=3)) is False  # counts alone ≠ difference
    assert op.denied_mismatches({"X": ["read"]}, REF) == [["X", "<unexpected constraint>", ["read"]]]


def test_matrix_without_controls_skips_control_keys():
    m = op.run_matrix(EXP, None)
    assert set(m) == set(PLAIN)


# --- fences, tags, Act = S·H·U (fix 4), point-of-action wording (fix 2) -----


def test_fences_and_tags_stated():
    doc = op.__doc__
    for s in ("STRUCTURAL ANALOGY / PROPOSED", "efficacy OPEN", "h < 1",
              "Stickiness ≠ Act / S(x) authority", "Act(x)=0 ≠ Stop",
              "Nothing here certifies an agent or closes L²_C", "PR #4"):
        assert s in doc


def test_act_formula_stated_with_h_u_undefined_and_not_computed():
    from test_claim_language import ROOT, normalize
    doc = normalize(op.__doc__)
    assert "Act = S·H·U" in doc and "COMPANION.md" in doc
    assert "H not defined in this repo" in doc and "U not defined there either" in doc
    assert "Act is NOT computed" in doc and "does NOT compute S(x)" in doc
    md = normalize((ROOT / "docs" / "PEAICE-AICE-OPTO-PROBE-001.md").read_text(encoding="utf-8"))
    assert "Act = S·H·U" in md and "H and U are not defined" in md
    assert "Act and S(x) are not computed" in md


def test_point_of_action_wording():
    from test_claim_language import ROOT, normalize
    doc = normalize(op.__doc__)
    md = normalize((ROOT / "docs" / "PEAICE-AICE-OPTO-PROBE-001.md").read_text(encoding="utf-8"))
    for text in (doc, md):
        assert "COMPLIANT AGENT on a FROZEN FIXTURE" in text or "compliant agent on a frozen fixture" in text
        assert "E2" in text and "over-stop" in text
