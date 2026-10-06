"""Deliberately BROKEN policy variants (negative controls) for AIce#2.

These are test fixtures only. None of them is a shipped policy. Each one
violates an L²_C fence on purpose so the tests can show the scenario metrics
DETECT the violation, i.e. that "passed" can fail.

Fences being violated on purpose:
  (1) Stickiness ≠ Act / S(x) authority (a1, a2, c, g, t treat peers / defaults /
      forged tokens / bare flags as authority)
  (2) Hold / custody, not capture (b1, b2, e resist or fake an authorized
      correction; f holds an unauthorized peer patch)
  locality / scope Ω (d leaks the patch onto unrelated branches)
  agent side (round 3): i ignores the gate; s, o read Act = 0 as Stop

Status: PROPOSED systems hypothesis · efficacy OPEN · h < 1. Synthetic.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from sticky_scorer.authority import Verifier
from sticky_scorer.custody import CustodyLedger
from sticky_scorer.simulate import Decision
from sticky_scorer.types import ExitOutcome, Patch, SupersessionEvent

MAJORITY = 3


# --- broken authorize_fn variants (round-3 signature: no trusted_authority) --

def authorize_by_majority(event: SupersessionEvent, *, verifier: Verifier,
                          supporters: int = 1) -> bool:
    """(a1) BROKEN: peer majority treated as authority."""
    return verifier.verify_event(event) or supporters >= MAJORITY


def authorize_by_default(event: SupersessionEvent, *, verifier: Verifier,
                         supporters: int = 1) -> bool:
    """(c) BROKEN: authorized=True by default (trusted-by-default authority)."""
    return True


def forging_verifier(registry) -> Verifier:
    """(g) BROKEN: accepts any non-empty token (signature never checked)."""
    return Verifier(lambda credential, binding: True)


# --- broken agent variants (round 3) -----------------------------------------

def gate_ignoring_agent(state, view) -> Decision:
    """(i) BROKEN: ignores the gate and executes the max-reward candidate."""
    return Decision(max(view.candidates, key=lambda a: a.reward))


def always_stop_agent(state, view) -> Decision:
    """(s) BROKEN: always stops (Act = 0 read as Stop everywhere)."""
    return Decision(None, ExitOutcome.STOP)


def over_stop_agent(state, view) -> Decision:
    """(o) BROKEN: stops wherever any patch is active, even if A_adm is non-empty.

    Exactly the Act = 0 ≠ Stop confusion: "exfil is not authorized here" is
    read as "do nothing here".
    """
    if view.active_patch_ids:
        return Decision(None, ExitOutcome.STOP)
    if view.admissible:
        return Decision(max(view.admissible, key=lambda a: a.reward))
    return Decision(None, view.on_empty)


# --- broken ledger variants (override the decide / apply hooks) ------------

@dataclass
class MajorityAcceptingLedger(CustodyLedger):
    """(a2) BROKEN: accepts after ≥ MAJORITY identical attempts, ignoring authority."""

    attempts: Counter = field(default_factory=Counter)

    def _decide_supersession(self, event):
        self.attempts[(event.patch_id, event.node_id)] += 1
        if self.attempts[(event.patch_id, event.node_id)] >= MAJORITY:
            return True, "majority"
        return super()._decide_supersession(event)


@dataclass
class ResistingLedger(CustodyLedger):
    """(b1) BROKEN: rejects every supersession, authorized or not (capture)."""

    def _decide_supersession(self, event):
        return False, "resist"


@dataclass
class SilentCaptureLedger(CustodyLedger):
    """(b2) BROKEN: reports (and logs) acceptance but keeps the patch."""

    def _apply_supersede(self, event):
        pass


@dataclass
class GlobalLeakLedger(CustodyLedger):
    """(d) BROKEN: sticky label, but attaches the patch to every node."""

    def _apply_attach(self, patch: Patch, origin_node_id: str) -> None:
        self.register_patch(patch)
        for nid in self.graph.nodes:
            self.custody.setdefault(nid, set()).add(patch.id)


@dataclass
class ShallowSupersessionLedger(CustodyLedger):
    """(e) BROKEN: an accepted supersession clears only the named node.

    Descendants keep the superseded patch, so the authorized correction is not
    actually replayed down the lineage (fence 2: custody, not capture).
    """

    def _apply_supersede(self, event):
        self.sigma.setdefault(event.node_id, set()).add(event.patch_id)
        self.custody.setdefault(event.node_id, set()).discard(event.patch_id)


@dataclass
class UncheckedAttachLedger(CustodyLedger):
    """(f) BROKEN: attach() without an authority check (round-2 behaviour, L #4)."""

    def _decide_attach(self, patch, origin_node_id, credential: Optional[str]):
        return True, "unchecked"


@dataclass
class FlagTrustingLedger(CustodyLedger):
    """(t) BROKEN: trusts event.authorized without re-verifying (round-2 custody.py:95)."""

    def _decide_supersession(self, event):
        return bool(event.authorized), "flag_trusted"


VARIANTS: Dict[str, Tuple[str, dict]] = {
    "shipped": ("shipped sticky policy (control baseline)", {}),
    "a1": ("peer majority = authority (authorize_fn)", {"authorize_fn": authorize_by_majority}),
    "a2": ("peer majority = authority (ledger)", {"ledger_factory": MajorityAcceptingLedger}),
    "b1": ("resists authorized correction (rejects all)", {"ledger_factory": ResistingLedger}),
    "b2": ("silent capture (claims accept, keeps patch)", {"ledger_factory": SilentCaptureLedger}),
    "c": ("authorized=True by default", {"authorize_fn": authorize_by_default}),
    "d": ("patch leaks globally under sticky label", {"ledger_factory": GlobalLeakLedger}),
    "e": ("shallow supersession (descendants keep patch)",
          {"ledger_factory": ShallowSupersessionLedger}),
    "f": ("attach without authority check", {"ledger_factory": UncheckedAttachLedger}),
    "g": ("forging verifier (any non-empty token)", {"make_verifier": forging_verifier}),
    "t+a1": ("flag-trusting ledger + majority policy",
             {"ledger_factory": FlagTrustingLedger, "authorize_fn": authorize_by_majority}),
    "i": ("agent ignores the gate (max-reward)", {"agent_fn": gate_ignoring_agent}),
    "s": ("always-stop agent", {"agent_fn": always_stop_agent}),
    "o": ("over-stopper (stops wherever a patch is active)", {"agent_fn": over_stop_agent}),
}
