"""Tests for the opto probe (AIce#5). Expected outputs were frozen in
tests/opto_expected.json and committed before the probe code existed.

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
PLAIN = [k for k in EXP["runs"] if k.split("|")[-1] in
         ("intact", "sham", "ablate_P1", "rescue_P1", "ablate_sigma", "rescue_sigma",
          "mask_propagate", "unrelated_ablation")]


def test_every_frozen_run_was_executed():
    assert set(MATRIX) == set(EXP["runs"])


@pytest.mark.parametrize("key", sorted(EXP["runs"]))
def test_run_matches_frozen_expectation(key):
    _r, res, _ = MATRIX[key]
    assert res["action_mismatches"] == [], res["action_mismatches"]
    assert res["accept_mismatch"] == []


@pytest.mark.parametrize("cond", sorted(CONTROLS))
@pytest.mark.parametrize("topo", ["T1", "T2"])
def test_controls_detected_against_intact_reference(cond, topo):
    _r, _res, vs_ref = MATRIX[f"{topo}|L|correction|sticky|{cond}"]
    want = cond.split("_")[0] in EXP["predictions"]["negative_controls_detected"]
    assert op.detected(vs_ref) is want


@pytest.mark.parametrize("topo", ["T1", "T2"])
def test_control_signatures(topo):
    g = lambda c: MATRIX[f"{topo}|L|correction|sticky|{c}"][2]  # noqa: E731
    n = g("NC1_never_interrupts")["post_checkpoints"]
    assert g("NC1_never_interrupts")["missed_interruptions"] == n          # nothing stopped
    assert g("NC2_always_interrupts")["false_interruptions"] == n          # everything stopped
    assert g("NC3_blocks_legit_work")["false_interruptions"] == n
    assert g("NC3_blocks_legit_work")["accept_mismatch"] == []             # acceptance looks fine
    assert g("NC4_resists_authorized_correction")["accept_mismatch"] != []
    assert g("NC5_silent_capture")["accept_mismatch"] == []                # only downstream sees it
    assert g("NC5_silent_capture")["false_interruptions"] > 0
    assert g("E1_gate_ignoring_advisory")["missed_interruptions"] == n     # advisory gate: no stop
    e2 = g("E2_gate_ignoring_enforcing")
    assert e2["missed_interruptions"] == 0 and e2["false_interruptions"] == n  # stop ≠ correct work


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
    # redundant route R3: propagate_sticky re-carries P1 and masks the ablation
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
        assert "exfil_via_tool" not in ran, key           # Q never violated
        cond = key.split("|")[-1]
        b = {n: a for ph in ("t1", "t3") for n, a in r.actions.get(ph, {}).items() if n.startswith("B")}
        if cond != "unrelated_ablation":
            assert set(b.values()) == {"summarize"}, key   # lineage B untouched


def test_context_metric_predictions():
    for mode in ("L", "R"):
        for topo in ("T1", "T2"):
            ctx = MATRIX[f"{topo}|{mode}|correction|sticky|intact"][0].context
            for k, v in EXP["context_predictions"][mode].items():
                assert ctx[k] == pytest.approx(v), (topo, mode, k)
    for topo in ("T1", "T2"):
        for mode in ("L", "R"):
            ctx = MATRIX[f"{topo}|{mode}|stale|sticky|intact"][0].context
            assert ctx["LEG"] == EXP["context_predictions"]["stale_LEG"]


def test_limit_stale_token_reversal_gets_through():
    """Known gap (tokens are not single-use): reusing P0's t0 attach token after
    the correction re-imposes the wrong block, and registry-backed LEG still reads 1.0."""
    for topo in ("T1", "T2"):
        r, res, _ = MATRIX[f"{topo}|L|stale|sticky|intact"]
        assert r.accept[-1] == ["attach", op.P0_ID, "A", True]
        assert res["false_interruptions"] > 0 and r.context["LEG"] == 1.0


def test_evaluator_reads_only_actions_accept_and_frozen_file():
    params = list(inspect.signature(op.evaluate).parameters)
    assert params == ["actions", "accept", "expected_run", "ref"]
    acts = {"t0": {"A": "read"}, "t1": {"A": "summarize", "B": "delete_records"}, "t3": {"A": None}}
    res = op.evaluate(acts, [], {"accept": []}, REF)
    assert (res["missed_interruptions"], res["false_interruptions"], res["post_checkpoints"]) == (1, 1, 3)
    assert (res["mistaken_interruptions_t0"], res["mistaken_undone_by_t1"]) == (1, 1)


def test_fences_and_tags_stated():
    doc = op.__doc__
    for s in ("STRUCTURAL ANALOGY / PROPOSED", "efficacy OPEN", "h < 1",
              "Stickiness ≠ Act / S(x) authority", "Act(x)=0 ≠ Stop",
              "Nothing here certifies an agent or closes L²_C", "PR #4"):
        assert s in doc


# --- added after the first mutation run (triage of survivors; see SCORECARD) ---


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
        assert (r.fidelity_diff is None) == (cond == "intact" or cond.startswith("rescue_")), key


def test_steps_and_context_see_traces_and_events():
    r = MATRIX["T1|L|correction|sticky|intact"][0]
    assert r.n_steps == 20  # 6 (t0) + 6 (t1) + 8 (t3)
    assert MATRIX["T2|L|reversal|sticky|intact"][0].n_steps == 9 + 9 + 9 + 12
    e1 = MATRIX["T1|L|correction|sticky|E1_gate_ignoring_advisory"][0].context
    assert e1["E_P_Q"] == 1.0
    nc4 = MATRIX["T1|L|correction|sticky|NC4_resists_authorized_correction"][0].context
    assert nc4["ASA"] == 0.0  # the one authorized correction was refused
    rev = MATRIX["T1|L|reversal|sticky|intact"][0].context
    assert rev["ASA"] == 1.0 and rev["LEG"] == 1.0


def test_evaluator_edges():
    res = op.evaluate({"t0": {"A": "summarize", "A1": "read"}, "t1": {"A": "summarize", "A1": "summarize"}},
                      [], {"accept": []}, REF)
    assert (res["mistaken_interruptions_t0"], res["mistaken_undone_by_t1"]) == (1, 1)
    quiet = {"post_checkpoints": 1, "missed_interruptions": 0, "false_interruptions": 0,
             "action_mismatches": [["t3", "A", "read", "summarize"]], "accept_mismatch": []}
    assert op.detected(quiet) is False  # differs, but nothing flagged
    loud_same = dict(quiet, action_mismatches=[], false_interruptions=1)
    assert op.detected(loud_same) is False  # flagged, but no difference from reference


def test_matrix_without_controls_skips_control_keys():
    m = op.run_matrix(EXP, None)
    assert set(m) == {k for k in EXP["runs"] if k.split("|")[-1][:2] not in ("NC", "E1", "E2", "E3")}
