"""Smallest synthetic finite transition system for AIce#9 (Lamport method).

Goal: say, as an executable state machine, what must stay true when several
workers classify one seat while snapshots, policies and corrections change,
and check it by exhaustive bounded exploration.

Why: AIce#9 asks whether the sticky scorer can represent concurrent branches,
stale results, retries and authority checks. Lamport's method answers that
with Init(S0) => I(S0) and I(S) and Next(S,S') => I(S'). This module is the
Init, the Next and the I. docs/PEAICE-AICE-LAMPORT-001.md has the state table.

How checked: tests/test_concurrency_model.py replays the schedules frozen in
tests/lamport_expected.json, explores every interleaving of each bounded
configuration, and runs twelve deliberately broken variants that must each
produce a counterexample trace. tools/mutation_check_concurrency.py mutates
this file and the tests must fail.

Scope. Synthetic data only. A counterexample-free bounded exploration says the
invariants hold for these fixtures, these event menus and these bounds. It is
not a statement about a live deployment. Authority comes from the named
external table in the fixtures (a human or an issuing service), never from a
field the worker supplies. Lamport timestamps and happens-before order events;
they do not decide who may supersede a correction. Replica agreement is not
correctness. Status: PROPOSED systems hypothesis, efficacy OPEN, h < 1.
Fences: (1) Stickiness is not Act / S(x) authority (2) hold / custody, not
capture; Act(x)=0 is not Stop (3) Nothing here certifies an agent or closes L²_C.
"""

from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, FrozenSet, Iterator, List, NamedTuple, Optional, Sequence, Tuple

EXPECTED_PATH = Path(__file__).resolve().parents[2] / "tests" / "lamport_expected.json"

VALID_KINDS = frozenset({"AGE_A", "AGE_B"})  # observed past activity buckets
ACTIVE, INACTIVE, UNKNOWN = "ACTIVE", "INACTIVE", "UNKNOWN"
IDLE, READ_SNAP, READ_POL, COMPUTED, CHECKED = "IDLE", "READ_SNAP", "READ_POL", "COMPUTED", "CHECKED"
WROTE, DONE, DUP, STALE, CRASHED, ESCALATED = "WROTE", "DONE", "DUP", "STALE", "CRASHED", "ESCALATED"
NONE_, RELEASED, DENIED, RECALL, BLOCKED = "NONE", "RELEASED", "DENIED", "RECALL", "BLOCKED"
VERIFIED, WITHDRAWN = "VERIFIED", "WITHDRAWN"
HOLD_ACTIVE, HOLD_SUPERSEDED = "ACTIVE", "SUPERSEDED"
WORKERS = ("W1", "W2")

VARIANTS = (
    "no_idempotent_commit", "non_atomic_commit", "blank_as_inactive", "future_as_active",
    "stale_overwrites", "trust_authorized_flag", "no_recall", "gate_uses_worker_view",
    "no_scope_check", "partial_as_complete", "compensating_report", "scope_blind_holds",
)

# ---------------------------------------------------------------------------
# Fixtures and the specification of one bounded system
# ---------------------------------------------------------------------------


class Snapshot(NamedTuple):
    obs: Tuple[Tuple[str, str], ...]  # (event id, bucket)
    complete: bool


@dataclass(frozen=True)
class Spec:
    """Constants of one bounded system: fixtures, event menu, bounds, variant."""

    snapshots: Dict[int, Snapshot]
    policies: Dict[int, FrozenSet[str]]
    issued: Dict[str, Tuple[str, str, str]]  # credential -> (principal, action, correction id)
    corrections: Dict[str, dict]
    supersessions: Dict[str, dict]
    seat: str
    product: str
    events: Tuple[str, ...] = ()
    crash: bool = False
    mismatch: bool = False
    variant: FrozenSet[str] = frozenset()
    gain_claimed: bool = True  # symbolic: an optimizer claims a speed or cost gain

    def has(self, flaw: str) -> bool:
        return flaw in self.variant


def load_expected(path: Path = EXPECTED_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def make_spec(exp: dict, snapshots: str, events: Sequence[str] = (), crash: bool = False,
              mismatch: bool = False, variant: Sequence[str] = ()) -> Spec:
    fx = exp["fixtures"]
    snaps = {int(v): Snapshot(tuple((e, k) for e, k in s["obs"]), bool(s["complete"]))
             for v, s in fx["snapshots"][snapshots].items()}
    pols = {int(v): frozenset(k) for v, k in fx["policies"].items()}
    issued = {c: tuple(t) for c, t in fx["external_authority_issued"].items()}
    ids = fx["identifiers"]
    return Spec(snaps, pols, issued, fx["corrections_menu"], fx["supersession_menu"],
                ids["seat"], ids["product"], tuple(events), crash, mismatch, frozenset(variant))


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class Worker(NamedTuple):
    name: str
    phase: str
    snap: int
    pol: int
    view: FrozenSet[str]  # the worker's own copy of the applicable holds
    cls: str
    anomaly: bool
    scope: str
    attempt: int
    saw_exists: bool


class Corr(NamedTuple):
    cid: str
    scope: str  # SEAT or OTHER
    status: str
    arrived_rev: int
    superseded_rev: int  # -1 while active


class RegEvent(NamedTuple):
    kind: str  # attach or supersede
    name: str
    cid: str
    principal: str
    credential: Optional[str]
    outcome: str  # accepted or refused
    reason: str


class Registry(NamedTuple):
    entries: Tuple[Corr, ...]
    consumed: FrozenSet[str]
    log: Tuple[RegEvent, ...]
    rev: int


class Record(NamedTuple):
    seat: str
    product: str
    snap: int
    pol: int
    cls: str
    anomaly: bool
    commit_version: int
    lineage: Tuple[Tuple[str, int], ...]


class Evidence(NamedTuple):
    snap: int
    pol: int
    scope: str  # MATCH or MISMATCH
    sufficient: bool


class Decision(NamedTuple):
    kind: str
    reason: str
    key: Optional[Tuple[int, int]]
    reg_rev: int


class Report(NamedTuple):
    kind: str
    reason: str
    basis: Optional[Tuple[str, str, Optional[Tuple[int, int]]]]


class State(NamedTuple):
    snapshot_version: int
    policy_version: int
    worker_state: Tuple[Worker, ...]
    correction_registry: Registry
    evidence_ref: Optional[Evidence]
    decision_state: Decision
    commit_version: int
    records: Tuple[Record, ...]
    report: Report
    used: FrozenSet[str]


def init_state(spec: Spec) -> State:
    ws = tuple(Worker(w, IDLE, 0, 0, frozenset(), "", False, "", 0, False) for w in WORKERS)
    return State(1, 1, ws, Registry((), frozenset(), (), 0), None,
                 Decision(NONE_, "", None, 0), 0, (), Report(NONE_, "", None), frozenset())


# ---------------------------------------------------------------------------
# Pure helpers: classification, evidence, authority, gate
# ---------------------------------------------------------------------------


def classify(spec: Spec, snap: int, pol: int) -> Tuple[str, bool]:
    """(class, anomaly) of the seat for one snapshot and one policy."""
    s = spec.snapshots[snap]
    kinds = {k for _e, k in set(s.obs)}  # a repeated row counts once
    anomaly = "FUTURE" in kinds
    valid = kinds & VALID_KINDS
    recent = valid & spec.policies[pol]
    complete = s.complete or spec.has("partial_as_complete")
    if spec.has("future_as_active") and anomaly:
        return ACTIVE, anomaly
    if recent:
        return ACTIVE, anomaly
    if valid:
        return (INACTIVE if complete else UNKNOWN), anomaly
    if spec.has("blank_as_inactive") and "BLANK" in kinds:
        return INACTIVE, anomaly
    return UNKNOWN, anomaly


def evidence_sufficient(spec: Spec, snap: int) -> bool:
    s = spec.snapshots[snap]
    complete = s.complete or spec.has("partial_as_complete")
    has_valid = bool({k for _e, k in s.obs} & VALID_KINDS)
    if spec.has("blank_as_inactive") and any(k == "BLANK" for _e, k in s.obs):
        has_valid = True  # missing evidence read as zero activity
    return complete and has_valid


def authority_ok(spec: Spec, action: str, principal: str, credential: Optional[str],
                 cid: str, consumed: FrozenSet[str], flag: bool) -> bool:
    """Authority is decided by the external issued table. ``flag`` is the
    worker-supplied authorized field; only a broken variant reads it."""
    if spec.has("trust_authorized_flag"):
        return flag
    if credential is None or credential in consumed:
        return False
    return spec.issued.get(credential) == (principal, action, cid)


def applicable_holds(spec: Spec, reg: Registry) -> FrozenSet[str]:
    return frozenset(c.cid for c in reg.entries
                     if c.status == HOLD_ACTIVE and (c.scope == "SEAT" or spec.has("scope_blind_holds")))


def gate(spec: Spec, rec: Record, ev: Evidence, holds: FrozenSet[str], reg_rev: int) -> Decision:
    """Release gate for the optimizer's removal proposal. Order: class, evidence, holds."""
    key = (rec.snap, rec.pol)
    if rec.cls != INACTIVE:
        return Decision(DENIED, "not_inactive", key, reg_rev)
    scope_bad = ev.scope != "MATCH" and not spec.has("no_scope_check")
    if not ev.sufficient or scope_bad:
        return Decision(DENIED, "evidence", key, reg_rev)
    if holds:
        return Decision(DENIED, "hold", key, reg_rev)
    return Decision(RELEASED, "", key, reg_rev)


def _withdraw(report: Report, reason: str) -> Report:
    return Report(WITHDRAWN, reason, report.basis) if report.kind == VERIFIED else report


def _recall(st: State, reason: str) -> Tuple[Decision, Report]:
    d = st.decision_state
    if d.kind == RELEASED:
        return Decision(RECALL, reason, d.key, st.correction_registry.rev), _withdraw(st.report, reason)
    return d, st.report


def _set_worker(st: State, w: Worker) -> Tuple[Worker, ...]:
    return tuple(w if x.name == w.name else x for x in st.worker_state)


def _record_for(st: State, key: Tuple[int, int]) -> Optional[Record]:
    for r in st.records:
        if (r.snap, r.pol) == key:
            return r
    return None


def _fresh(spec: Spec, st: State, w: Worker) -> bool:
    return spec.has("stale_overwrites") or (w.snap, w.pol) == (st.snapshot_version, st.policy_version)


def _blank(w: Worker, phase: str, attempt: int) -> Worker:
    return Worker(w.name, phase, 0, 0, frozenset(), "", False, "", attempt, False)


# ---------------------------------------------------------------------------
# Next: every enabled action and its successor
# ---------------------------------------------------------------------------


def _write(spec: Spec, st: State, w: Worker) -> State:
    cv = st.commit_version + 1
    rec = Record(spec.seat, spec.product, w.snap, w.pol, w.cls, w.anomaly, cv, ((w.name, w.attempt),))
    ev = Evidence(w.snap, w.pol, w.scope, evidence_sufficient(spec, w.snap))
    holds = w.view if spec.has("gate_uses_worker_view") else applicable_holds(spec, st.correction_registry)
    dec = gate(spec, rec, ev, holds, st.correction_registry.rev)
    return st._replace(worker_state=_set_worker(st, w._replace(phase=WROTE, saw_exists=False)),
                       evidence_ref=ev, decision_state=dec, commit_version=cv,
                       records=st.records + (rec,))


def _duplicate(st: State, w: Worker, existing: Record) -> State:
    merged = existing._replace(lineage=existing.lineage + ((w.name, w.attempt),))
    recs = tuple(merged if r is existing else r for r in st.records)
    return st._replace(worker_state=_set_worker(st, w._replace(phase=DUP, saw_exists=False)), records=recs)


def _commit_write(spec: Spec, st: State, w: Worker) -> State:
    if not _fresh(spec, st, w):
        return st._replace(worker_state=_set_worker(st, w._replace(phase=STALE)))
    existing = _record_for(st, (w.snap, w.pol))
    if existing is not None and not spec.has("no_idempotent_commit"):
        return _duplicate(st, w, existing)
    return _write(spec, st, w)


def _commit_check(spec: Spec, st: State, w: Worker) -> State:
    if not _fresh(spec, st, w):
        return st._replace(worker_state=_set_worker(st, w._replace(phase=STALE)))
    seen = _record_for(st, (w.snap, w.pol)) is not None
    return st._replace(worker_state=_set_worker(st, w._replace(phase=CHECKED, saw_exists=seen)))


def _commit_put(spec: Spec, st: State, w: Worker) -> State:
    existing = _record_for(st, (w.snap, w.pol))
    if w.saw_exists and existing is not None:
        return _duplicate(st, w, existing)
    return _write(spec, st, w)


def _compute(spec: Spec, st: State, w: Worker, scope: str) -> State:
    cls, anomaly = classify(spec, w.snap, w.pol)
    return st._replace(worker_state=_set_worker(st, w._replace(phase=COMPUTED, cls=cls, anomaly=anomaly, scope=scope)))


def _attach_event(spec: Spec, st: State, name: str) -> State:
    m = spec.corrections[name]
    reg = st.correction_registry
    known = any(c.cid == m["cid"] for c in reg.entries)
    ok = authority_ok(spec, "attach", m["principal"], m["credential"], m["cid"], reg.consumed,
                      bool(m["authorized_flag"])) and not known
    reason = "ok" if ok else ("duplicate" if known else "no_authority")
    ev = RegEvent("attach", name, m["cid"], m["principal"], m["credential"],
                  "accepted" if ok else "refused", reason)
    used = st.used | {f"Correct({name})"}
    if not ok:
        return st._replace(correction_registry=reg._replace(log=reg.log + (ev,)), used=used)
    rev = reg.rev + 1
    cons = reg.consumed | ({m["credential"]} if m["credential"] else set())
    reg2 = Registry(reg.entries + (Corr(m["cid"], m["scope"], HOLD_ACTIVE, rev, -1),), cons, reg.log + (ev,), rev)
    st2 = st._replace(correction_registry=reg2, used=used)
    if m["scope"] == "SEAT" and not spec.has("no_recall"):
        dec, rep = _recall(st2, "hold")
        st2 = st2._replace(decision_state=dec, report=rep)
    return st2


def _supersede_event(spec: Spec, st: State, name: str) -> State:
    m = spec.supersessions[name]
    reg = st.correction_registry
    target = next((c for c in reg.entries if c.cid == m["target"]), None)
    active = target is not None and target.status == HOLD_ACTIVE
    auth = authority_ok(spec, "supersede", m["principal"], m["credential"], m["target"], reg.consumed,
                        bool(m["authorized_flag"]))
    ok = active and auth
    reason = "ok" if ok else ("no_authority" if not auth else "not_active")
    ev = RegEvent("supersede", name, m["target"], m["principal"], m["credential"],
                  "accepted" if ok else "refused", reason)
    used = st.used | {f"Supersede({name})"}
    if not ok:
        return st._replace(correction_registry=reg._replace(log=reg.log + (ev,)), used=used)
    rev = reg.rev + 1
    entries = tuple(c._replace(status=HOLD_SUPERSEDED, superseded_rev=rev) if c is target else c
                    for c in reg.entries)
    cons = reg.consumed | ({m["credential"]} if m["credential"] else set())
    return st._replace(correction_registry=Registry(entries, cons, reg.log + (ev,), rev), used=used)


def _bump(st: State, snap: Optional[int], pol: Optional[int], label: str) -> State:
    dec, rep = _recall(st, "stale_input")
    return st._replace(snapshot_version=snap if snap is not None else st.snapshot_version,
                       policy_version=pol if pol is not None else st.policy_version,
                       decision_state=dec, report=rep, used=st.used | {label})


def _regate(spec: Spec, st: State) -> State:
    d = st.decision_state
    rec = _record_for(st, d.key)
    reg = st.correction_registry
    dec = gate(spec, rec, st.evidence_ref, applicable_holds(spec, reg), reg.rev)
    return st._replace(decision_state=dec)


def _verdict(spec: Spec, d: Decision) -> Report:
    basis = (d.kind, d.reason, d.key)
    if d.kind == RELEASED or (spec.has("compensating_report") and spec.gain_claimed):
        return Report(VERIFIED, "", basis)
    return Report("BLOCKED", d.reason, basis)


def _worker_successors(spec: Spec, st: State, w: Worker) -> Iterator[Tuple[str, State]]:
    n, ph = w.name, w.phase
    cur = (st.snapshot_version, st.policy_version)
    if ph == IDLE:
        yield f"ReadSnap({n})", st._replace(worker_state=_set_worker(
            st, w._replace(phase=READ_SNAP, snap=st.snapshot_version)))
    if ph == READ_SNAP:
        view = applicable_holds(spec, st.correction_registry)
        yield f"ReadPolicy({n})", st._replace(worker_state=_set_worker(
            st, w._replace(phase=READ_POL, pol=st.policy_version, view=view)))
    if ph == READ_POL:
        yield f"Compute({n})", _compute(spec, st, w, "MATCH")
        if spec.mismatch:
            yield f"Compute({n},MISMATCH)", _compute(spec, st, w, "MISMATCH")
    if ph == COMPUTED and not spec.has("non_atomic_commit"):
        yield f"CommitWrite({n})", _commit_write(spec, st, w)
    if ph == COMPUTED and spec.has("non_atomic_commit"):
        yield f"CommitCheck({n})", _commit_check(spec, st, w)
    if ph == CHECKED:
        yield f"CommitPut({n})", _commit_put(spec, st, w)
    if ph == WROTE:
        yield f"Ack({n})", st._replace(worker_state=_set_worker(st, w._replace(phase=DONE)))
    if spec.crash and "crash" not in st.used and ph in (READ_SNAP, READ_POL, COMPUTED, CHECKED, WROTE):
        yield f"Crash({n})", st._replace(worker_state=_set_worker(st, _blank(w, CRASHED, w.attempt)),
                                         used=st.used | {"crash"})
    if ph in (CRASHED, STALE):
        yield f"Retry({n})", st._replace(worker_state=_set_worker(st, _blank(w, IDLE, w.attempt + 1)))
    if ph in (DONE, DUP) and (w.snap, w.pol) != cur:
        yield f"Dispatch({n})", st._replace(worker_state=_set_worker(st, _blank(w, IDLE, w.attempt + 1)))
    if ph == STALE:
        d = st.decision_state
        blocked = Decision(BLOCKED, "stale_quarantined", None, st.correction_registry.rev)
        dec = blocked if d.key != cur else d
        yield f"Escalate({n})", st._replace(worker_state=_set_worker(st, w._replace(phase=ESCALATED)),
                                            decision_state=dec)


def successors(spec: Spec, st: State) -> List[Tuple[str, State]]:
    """Next: all (label, successor) pairs enabled in ``st``."""
    out: List[Tuple[str, State]] = []
    for w in st.worker_state:
        out.extend(_worker_successors(spec, st, w))
    for label in spec.events:
        if label in st.used:
            continue
        kind, arg = label[:-1].split("(", 1)
        if kind == "PublishSnapshot" and int(arg) == st.snapshot_version + 1 and int(arg) in spec.snapshots:
            out.append((label, _bump(st, int(arg), None, label)))
        elif kind == "UpdatePolicy" and int(arg) == st.policy_version + 1 and int(arg) in spec.policies:
            out.append((label, _bump(st, None, int(arg), label)))
        elif kind == "Correct":
            out.append((label, _attach_event(spec, st, arg)))
        elif kind == "Supersede":
            out.append((label, _supersede_event(spec, st, arg)))
    d = st.decision_state
    cur = (st.snapshot_version, st.policy_version)
    if d.kind == DENIED and d.reason == "hold" and d.key == cur and st.correction_registry.rev != d.reg_rev:
        out.append(("Regate", _regate(spec, st)))
    if d.kind in (RELEASED, DENIED, BLOCKED) and st.report.basis != (d.kind, d.reason, d.key):
        out.append(("Report", st._replace(report=_verdict(spec, d))))
    return out


def step(spec: Spec, st: State, label: str) -> State:
    for lab, nxt in successors(spec, st):
        if lab == label:
            return nxt
    raise ValueError(f"action not enabled: {label}")


def replay(spec: Spec, labels: Sequence[str]) -> List[State]:
    """States along a schedule, starting with Init. Raises if a step is not enabled."""
    states = [init_state(spec)]
    for lab in labels:
        states.append(step(spec, states[-1], lab))
    return states


# ---------------------------------------------------------------------------
# Invariants. Each returns True when it holds in the state.
# ---------------------------------------------------------------------------


def _expected_class(spec: Spec, rec: Record) -> Tuple[str, bool]:
    """I1 restated declaratively from the fixture rows (not via classify)."""
    s = spec.snapshots[rec.snap]
    kinds = {k for _e, k in s.obs}
    valid = kinds & VALID_KINDS
    recent = valid & spec.policies[rec.pol]
    if recent:
        cls = ACTIVE
    elif valid and s.complete:
        cls = INACTIVE
    else:
        cls = UNKNOWN
    return cls, "FUTURE" in kinds


def inv_I1(spec: Spec, st: State) -> bool:
    """Blank or unknown activity is UNKNOWN; future-dated rows are flagged, never active."""
    return all(_expected_class(spec, r) == (r.cls, r.anomaly) for r in st.records)


def inv_I2(spec: Spec, st: State) -> bool:
    """One logical commit per (seat, product, snapshot, policy); the counter agrees with the log."""
    keys = [(r.seat, r.product, r.snap, r.pol) for r in st.records]
    return (len(keys) == len(set(keys)) and st.commit_version == len(st.records)
            and all(r.lineage for r in st.records))


def _release_backed(spec: Spec, st: State) -> bool:
    d = st.decision_state
    rec = _record_for(st, d.key) if d.key else None
    ev = st.evidence_ref
    if rec is None or ev is None:
        return False
    snap = spec.snapshots[rec.snap]
    truly_backed = snap.complete and bool({k for _e, k in snap.obs} & VALID_KINDS)
    return (rec.cls == INACTIVE and ev.sufficient and ev.scope == "MATCH"
            and (ev.snap, ev.pol) == (rec.snap, rec.pol) and truly_backed)


def inv_I3(spec: Spec, st: State) -> bool:
    """A released removal is backed by complete, scope-matched evidence for its own snapshot."""
    return st.decision_state.kind != RELEASED or _release_backed(spec, st)


def _no_live_hold(spec: Spec, st: State) -> bool:
    return not any(c.status == HOLD_ACTIVE and c.scope == "SEAT" for c in st.correction_registry.entries)


def inv_I4(spec: Spec, st: State) -> bool:
    """Corrections and their lineage survive; every attach and supersession was authorized
    by the external table (not by a field); credentials are single-use; no release stands
    over a live applicable hold."""
    reg = st.correction_registry
    acc = [e for e in reg.log if e.outcome == "accepted"]
    cids = [c.cid for c in reg.entries]
    if len(cids) != len(set(cids)):
        return False
    attached = {e.cid for e in acc if e.kind == "attach"}
    if attached != set(cids):
        return False
    for e in acc:
        if spec.issued.get(e.credential) != (e.principal, e.kind, e.cid):
            return False
    creds = [e.credential for e in acc]
    if len(creds) != len(set(creds)):
        return False
    superseded = {c.cid for c in reg.entries if c.status == HOLD_SUPERSEDED}
    if superseded != {e.cid for e in acc if e.kind == "supersede"}:
        return False
    return st.decision_state.kind != RELEASED or _no_live_hold(spec, st)


def inv_I5(spec: Spec, st: State) -> bool:
    """A newer committed result is never overwritten by an older one; a release refers
    to the current snapshot and policy and to the newest record."""
    keys = [(r.snap, r.pol) for r in st.records]
    if any(a >= b for a, b in zip(keys, keys[1:])):
        return False
    d = st.decision_state
    if d.key is not None and keys and d.key != keys[-1]:
        return False
    if st.evidence_ref is not None and keys and (st.evidence_ref.snap, st.evidence_ref.pol) != keys[-1]:
        return False
    return d.kind != RELEASED or d.key == (st.snapshot_version, st.policy_version)


def inv_I6(spec: Spec, st: State) -> bool:
    """A verified report needs every gate to pass. A claimed gain never substitutes."""
    if st.report.kind != VERIFIED:
        return True
    return (st.decision_state.kind == RELEASED and _release_backed(spec, st)
            and _no_live_hold(spec, st) and inv_I5(spec, st))


_SYN = re.compile(r"^SYN-(SEAT|PRODUCT)-[0-9A-Z]+(-[0-9A-Z]+)?$")


def _strings(x) -> Iterator[str]:
    if isinstance(x, str):
        yield x
    elif isinstance(x, (tuple, list, frozenset, set)):
        for y in x:
            yield from _strings(y)


def inv_I7(spec: Spec, st: State) -> bool:
    """Only synthetic identifiers appear; no address-like or link-like text."""
    for r in st.records:
        if not (_SYN.match(r.seat) and _SYN.match(r.product)):
            return False
    return not any("@" in s or "://" in s for s in _strings(st))


def inv_U1(spec: Spec, st: State) -> bool:
    """Control: a denial is justified. Nothing safe is blocked, and a correction for
    another seat does not block this one."""
    d = st.decision_state
    if d.kind != DENIED:
        return True
    rec = _record_for(st, d.key)
    if d.reason == "not_inactive":
        return rec.cls != INACTIVE
    if d.reason == "evidence":
        ev = st.evidence_ref
        return rec.cls == INACTIVE and (ev is None or not ev.sufficient or ev.scope != "MATCH")
    live = [c for c in st.correction_registry.entries
            if c.scope == "SEAT" and c.arrived_rev <= d.reg_rev
            and (c.superseded_rev == -1 or c.superseded_rev > d.reg_rev)]
    return d.reason == "hold" and rec.cls == INACTIVE and bool(live)


INVARIANTS = {"I1": inv_I1, "I2": inv_I2, "I3": inv_I3, "I4": inv_I4, "I5": inv_I5,
              "I6": inv_I6, "I7": inv_I7, "U1": inv_U1}


def violated(spec: Spec, st: State) -> List[str]:
    return [name for name, fn in INVARIANTS.items() if not fn(spec, st)]


# ---------------------------------------------------------------------------
# Progress: Committed or BlockedWithReason
# ---------------------------------------------------------------------------


def committed(st: State) -> bool:
    return _record_for(st, (st.snapshot_version, st.policy_version)) is not None


def blocked_with_reason(st: State) -> bool:
    return st.decision_state.kind in (BLOCKED, RECALL) and bool(st.decision_state.reason)


def goal(st: State) -> bool:
    return committed(st) or blocked_with_reason(st)


# ---------------------------------------------------------------------------
# Bounded exhaustive explorer
# ---------------------------------------------------------------------------


@dataclass
class Exploration:
    states: int = 0
    transitions: int = 0
    max_depth: int = 0
    truncated: bool = False
    counterexamples: Dict[str, List[str]] = field(default_factory=dict)
    deadlocks: List[List[str]] = field(default_factory=list)
    cannot_progress: int = 0
    progress_example: Optional[List[str]] = None

    def ok(self) -> bool:
        return (not self.counterexamples and not self.deadlocks and self.cannot_progress == 0
                and not self.truncated)


def _trace(parents: List[Tuple[int, str]], i: int) -> List[str]:
    out: List[str] = []
    while i > 0:
        p, lab = parents[i]
        out.append(lab)
        i = p
    return out[::-1]


def explore(spec: Spec, max_states: int = 1_500_000, progress: bool = True) -> Exploration:
    """Breadth-first search over every interleaving. Checks every invariant at every
    reachable state and keeps the shortest counterexample trace per invariant. With
    ``progress`` it also reports deadlocks outside the goal and states from which no
    goal state is reachable."""
    res = Exploration()
    s0 = init_state(spec)
    index = {s0: 0}
    parents: List[Tuple[int, str]] = [(-1, "")]
    depth = [0]
    succ: List[List[int]] = []
    states = [s0]
    queue = deque([0])
    for name in violated(spec, s0):
        res.counterexamples.setdefault(name, [])
    while queue:
        i = queue.popleft()
        st = states[i]
        nxt = successors(spec, st)
        row: List[int] = []
        if not nxt and not goal(st):
            res.deadlocks.append(_trace(parents, i))
        for lab, st2 in nxt:
            res.transitions += 1
            j = index.get(st2)
            if j is None:
                if len(states) >= max_states:
                    res.truncated = True
                    continue
                j = len(states)
                index[st2] = j
                states.append(st2)
                parents.append((i, lab))
                depth.append(depth[i] + 1)
                queue.append(j)
                for name in violated(spec, st2):
                    res.counterexamples.setdefault(name, _trace(parents, j))
            row.append(j)
        succ.append(row)
    res.states = len(states)
    res.max_depth = max(depth)
    if progress and not res.truncated:
        pred: List[List[int]] = [[] for _ in states]
        for i, row in enumerate(succ):
            for j in row:
                pred[j].append(i)
        reach = [goal(st) for st in states]
        stack = [i for i, ok in enumerate(reach) if ok]
        while stack:
            j = stack.pop()
            for i in pred[j]:
                if not reach[i]:
                    reach[i] = True
                    stack.append(i)
        bad = [i for i, ok in enumerate(reach) if not ok]
        res.cannot_progress = len(bad)
        if bad:
            res.progress_example = _trace(parents, bad[0])
    return res


# ---------------------------------------------------------------------------
# Observation of a state, for comparison with the frozen expectations
# ---------------------------------------------------------------------------


def observe(spec: Spec, st: State) -> dict:
    reg = st.correction_registry
    d = st.decision_state
    return {
        "records": [[r.snap, r.pol, r.cls, r.anomaly] for r in st.records],
        "commit_version": st.commit_version,
        "decision": [d.kind, d.reason],
        "report": [st.report.kind, st.report.reason],
        "lineage": [[w, a] for w, a in st.records[0].lineage] if st.records else [],
        "phases": {w.name: w.phase for w in st.worker_state},
        "registry": {c.cid: c.status for c in reg.entries},
        "registry_entries": len(reg.entries),
        "accepted_supersessions": sum(1 for e in reg.log if e.kind == "supersede" and e.outcome == "accepted"),
        "last_registry_outcome": reg.log[-1].outcome if reg.log else None,
        "enabled": sorted(lab.split("(")[0] for lab, _ in successors(spec, st)),
    }


def schedule_spec(exp: dict, sched: dict, variant: Sequence[str] = ()) -> Spec:
    steps = list(sched["steps"]) + list(sched.get("continue_steps", []))
    env = [s for s in steps if s.split("(")[0] in ("PublishSnapshot", "UpdatePolicy", "Correct", "Supersede")]
    return make_spec(exp, sched["snapshots"], env, crash=any(s.startswith("Crash") for s in steps),
                     mismatch=any("MISMATCH" in s for s in steps), variant=variant)


def config_spec(exp: dict, name: str, variant: Sequence[str] = ()) -> Spec:
    c = exp["explore_configs"][name]
    return make_spec(exp, c["snapshots"], c["events"], c["crash"], c["mismatch"], variant)
