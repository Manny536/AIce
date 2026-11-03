"""Adapter: replay the model's registry events through the existing sticky scorer.

Goal: find out, by running both, which parts of the AIce#9 transition system
the current sticky_scorer can represent: (a) inherited correction membership,
(b) enforcement of a decision, (c) authorization of supersession.
Why: the issue asks whether the scorer can carry concurrency, stale tokens,
retries and authority checks "without assuming the hazard away". An adapter
that only calls the public scorer API, and leaves every scorer module unchanged,
gives a direct answer instead of a description.
How checked: tests/test_concurrency_adapter.py compares outcomes and membership
event by event over every reachable registry log, pins each difference, and
runs the scorer with and without a verifier.

Nothing here changes scorer behaviour. Synthetic data only. Authority is the
external issuing table; the scorer's own HMAC tokens are minted from that table
and nowhere else. Nothing here certifies an agent or closes L²_C.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Sequence, Tuple

from . import concurrency_model as cm
from .admissibility import admissible_actions
from .authority import ATTACH, SUPERSEDE, AuthorityRegistry
from .custody import CustodyLedger
from .types import (Action, Condition, Patch, RouteGraph, RouteNode, State,
                    SupersessionEvent)

SEAT_NODE, OTHER_NODE, SEAT_CHILD, ROOT = "N_SEAT", "N_OTHER", "N_SEAT_CHILD", "N_ROOT"
GOVERNING = ("human_owner", "auditor")
REMOVE = Action("remove_seat", frozenset({"remove_seat"}))
_STATE = State("synthetic")


def build_graph() -> RouteGraph:
    """Root with two unrelated branches; the seat's branch has one child."""
    g = RouteGraph()
    g.add(RouteNode(ROOT, None, 0, ""))
    g.add(RouteNode(SEAT_NODE, ROOT, 1, "A"))
    g.add(RouteNode(OTHER_NODE, ROOT, 1, "B"))
    g.add(RouteNode(SEAT_CHILD, SEAT_NODE, 2, "A"))
    return g


def _deny_removal(state: State, action: Action) -> bool:
    return "remove_seat" not in action.tags


@dataclass
class ScorerRun:
    ledger: CustodyLedger
    registry: AuthorityRegistry
    outcomes: List[Tuple[str, str]] = field(default_factory=list)  # (event name, accepted|refused)


def _node_for(exp: dict, cid: str) -> str:
    menu = exp["fixtures"]["corrections_menu"]
    scope = next(m["scope"] for m in menu.values() if m["cid"] == cid)
    return SEAT_NODE if scope == "SEAT" else OTHER_NODE


def _token(exp: dict, reg: AuthorityRegistry, credential: Optional[str]) -> Optional[str]:
    """Mint the scorer's token for an entry of the external issuing table."""
    if credential is None:
        return None
    principal, action, cid = exp["fixtures"]["external_authority_issued"][credential]
    return reg.issue(principal, action, cid, _node_for(exp, cid))


def replay_in_scorer(exp: dict, log: Sequence[cm.RegEvent], *, verifier: bool = True,
                     guard: bool = False) -> ScorerRun:
    """Feed the model's registry events to a sticky CustodyLedger in order.

    With ``guard`` the adapter adds the three checks the scorer lacks, before the
    ledger is called: a credential is used once, a correction id is attached once,
    and only a currently held correction can be superseded. A refused event is
    recorded in ``outcomes`` and never reaches the ledger. The scorer itself is
    not changed."""
    reg = AuthorityRegistry(governing=GOVERNING)
    ledger = CustodyLedger(build_graph(), condition=Condition.STICKY,
                           verifier=reg.verifier() if verifier else None,
                           witness=reg.log_witness())
    run = ScorerRun(ledger, reg)
    menu = exp["fixtures"]["corrections_menu"]
    sup = exp["fixtures"]["supersession_menu"]
    consumed: set = set()
    ever_attached: set = set()
    for ev in log:
        if guard and _guard_refuses(exp, ev, run, consumed, ever_attached):
            run.outcomes.append((ev.name, "refused"))
            continue
        if ev.kind == "attach":
            m = menu[ev.name]
            patch = Patch(id=m["cid"], phi=_deny_removal,
                          scope_node_ids=frozenset({_node_for(exp, m["cid"])}),
                          authority=m["principal"])
            ok = ledger.attach(patch, _node_for(exp, m["cid"]), _token(exp, reg, m["credential"]))
        else:
            m = sup[ev.name]
            event = SupersessionEvent(m["target"], _node_for(exp, m["target"]),
                                      bool(m["authorized_flag"]), m["principal"],
                                      _token(exp, reg, m["credential"]))
            ok = ledger.apply_supersession(event)
        ledger.propagate_sticky()
        run.outcomes.append((ev.name, "accepted" if ok else "refused"))
        if ok:
            cred = (menu if ev.kind == "attach" else sup)[ev.name]["credential"]
            consumed.add(cred)
            if ev.kind == "attach":
                ever_attached.add(ev.cid)
    return run


def _guard_refuses(exp: dict, ev: cm.RegEvent, run: ScorerRun, consumed: set, ever: set) -> bool:
    menu = exp["fixtures"]["corrections_menu"]
    sup = exp["fixtures"]["supersession_menu"]
    m = (menu if ev.kind == "attach" else sup)[ev.name]
    if m["credential"] is not None and m["credential"] in consumed:
        return True
    if ev.kind == "attach":
        return ev.cid in ever
    return ev.cid not in run.ledger.active_at(_node_for(exp, ev.cid))


def scorer_holds(run: ScorerRun, node: str = SEAT_NODE) -> FrozenSet[str]:
    return frozenset(run.ledger.active_at(node))


def scorer_blocks_removal(run: ScorerRun, node: str = SEAT_NODE) -> bool:
    """Advisory gate: is the removal action outside A_adm at this node?"""
    return not admissible_actions(_STATE, [REMOVE], run.ledger, node)


def model_seat_holds(st: cm.State) -> FrozenSet[str]:
    return frozenset(c.cid for c in st.correction_registry.entries
                     if c.status == cm.HOLD_ACTIVE and c.scope == "SEAT")


def model_other_holds(st: cm.State) -> FrozenSet[str]:
    return frozenset(c.cid for c in st.correction_registry.entries
                     if c.status == cm.HOLD_ACTIVE and c.scope == "OTHER")


def reachable_registry_states(spec: cm.Spec) -> List[cm.State]:
    """Every registry state reachable by correction and supersession events alone."""
    s0 = cm.init_state(spec)
    seen = {s0.correction_registry: s0}
    todo = [s0]
    while todo:
        st = todo.pop()
        for lab, nxt in cm.successors(spec, st):
            if lab.split("(")[0] in ("Correct", "Supersede") and nxt.correction_registry not in seen:
                seen[nxt.correction_registry] = nxt
                todo.append(nxt)
    return list(seen.values())


def differences(exp: dict, spec: cm.Spec, *, guard: bool = False) -> List[dict]:
    """Every registry log on which the scorer and the model disagree, with the kind of
    disagreement: 'outcome' (an event accepted by one and refused by the other) or
    'membership' (the sets of held corrections differ at the end of the log)."""
    out: List[dict] = []
    for st in reachable_registry_states(spec):
        log = st.correction_registry.log
        run = replay_in_scorer(exp, log, guard=guard)
        model_out = [(e.name, e.outcome) for e in log]
        o_diff = [i for i, (a, b) in enumerate(zip(model_out, run.outcomes)) if a != b]
        m_diff = (model_seat_holds(st) != scorer_holds(run, SEAT_NODE)
                  or model_other_holds(st) != scorer_holds(run, OTHER_NODE))
        if o_diff or m_diff:
            out.append({"log": [e.name for e in log], "outcome_diff_at": o_diff,
                        "membership_differs": m_diff,
                        "model_seat": sorted(model_seat_holds(st)),
                        "scorer_seat": sorted(scorer_holds(run, SEAT_NODE))})
    return out
