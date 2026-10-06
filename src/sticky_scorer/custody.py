"""Custody inheritance: C(v) ⊇ C(u) \\ Σ(v).

Implements the sticky custody condition from study §5, plus local and
global attachment policies used as experimental controls (§15).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, Iterable, Mapping, Optional, Sequence, Set, Tuple

from .authority import ATTACH, Verifier
from .types import Condition, Patch, RouteGraph, SupersessionEvent

GENESIS = "0" * 64


@dataclass(frozen=True)
class LogEntry:
    """One custody-log record (round 3, L #5). Refused attempts are logged too.

    ``hash`` chains over the previous entry, so editing, dropping, or
    reordering an entry breaks ``CustodyLedger.verify_log_chain``.
    """

    seq: int
    kind: str  # "attach" | "supersede"
    patch_id: str
    node_id: str
    authority: str
    flag: Optional[bool]  # event.authorized as set by the policy (supersede only)
    credential_present: bool
    accepted: bool
    reason: str
    prev_hash: str
    hash: str

    @staticmethod
    def digest(prev_hash: str, *fields) -> str:
        return hashlib.sha256(repr((prev_hash,) + tuple(fields)).encode()).hexdigest()

    def body(self) -> tuple:
        return (self.seq, self.kind, self.patch_id, self.node_id, self.authority,
                self.flag, self.credential_present, self.accepted, self.reason)


@dataclass
class CustodyLedger:
    """Active patch sets C(u) attached to each route node."""

    graph: RouteGraph
    patches: Dict[str, Patch] = field(default_factory=dict)
    # node_id -> set of active patch ids
    custody: Dict[str, Set[str]] = field(default_factory=dict)
    # node_id -> set of superseded patch ids Σ(v)
    sigma: Dict[str, Set[str]] = field(default_factory=dict)
    condition: Condition = Condition.STICKY
    # Check-only authority capability. None = legacy unverified mode (unit tests
    # that build ledgers by hand); every scenario and the demo pass a verifier.
    verifier: Optional[Verifier] = None
    _log: list = field(default_factory=list, repr=False)

    # --- append-only custody log -------------------------------------------

    def _append(self, kind, patch_id, node_id, authority, flag, credential, accepted, reason):
        prev = self._log[-1].hash if self._log else GENESIS
        body = (len(self._log), kind, patch_id, node_id, authority, flag,
                bool(credential), bool(accepted), reason)
        self._log.append(LogEntry(*body, prev_hash=prev, hash=LogEntry.digest(prev, *body)))

    @property
    def log(self) -> Tuple[LogEntry, ...]:
        """Ordered, read-only view of every attach / supersede attempt."""
        return tuple(self._log)

    def verify_log_chain(self) -> bool:
        prev = GENESIS
        for i, e in enumerate(self._log):
            if e.seq != i or e.prev_hash != prev or e.hash != LogEntry.digest(prev, *e.body()):
                return False
            prev = e.hash
        return True

    def register_patch(self, patch: Patch) -> None:
        self.patches[patch.id] = patch

    def active_at(self, node_id: str) -> Set[str]:
        return set(self.custody.get(node_id, set()))

    def superseded_at(self, node_id: str) -> Set[str]:
        return set(self.sigma.get(node_id, set()))

    def _decide_attach(self, patch: Patch, origin_node_id: str,
                       credential: Optional[str]) -> Tuple[bool, str]:
        """Authority check for attach (round 3, L #4): the credential must verify
        for (patch.authority, attach, patch.id, origin)."""
        if self.verifier is None:
            return True, "legacy_no_verifier"
        if self.verifier.verify(credential, patch.authority, ATTACH, patch.id, origin_node_id):
            return True, "verified"
        return False, "unverified_credential"

    def _attach_targets(self, origin_node_id: str) -> Set[str]:
        if self.condition == Condition.LOCAL:
            return {origin_node_id}
        if self.condition == Condition.GLOBAL:
            return set(self.graph.nodes.keys())
        return {origin_node_id} | set(self.graph.descendants(origin_node_id))

    def _apply_attach(self, patch: Patch, origin_node_id: str) -> None:
        self.register_patch(patch)
        for nid in self._attach_targets(origin_node_id):
            self.custody.setdefault(nid, set()).add(patch.id)

    def attach(self, patch: Patch, origin_node_id: str,
               credential: Optional[str] = None) -> bool:
        """Attach patch under the active experimental condition, if authorized.

        A — Local: only the identified route node receives the correction.
        B — Global: every node in the graph receives the correction.
        C — Sticky: origin + all descendants in the multiscale lineage.

        With a verifier, an attach whose credential does not verify is refused
        and logged; custody is unchanged. Returns True iff attached.
        """
        ok, reason = self._decide_attach(patch, origin_node_id, credential)
        self._append(ATTACH, patch.id, origin_node_id, patch.authority, None,
                     credential, ok, reason)
        if ok:
            self._apply_attach(patch, origin_node_id)
        return ok

    def inherit_child(self, parent_id: str, child_id: str) -> Set[str]:
        """Apply sticky inheritance: C(v) ⊇ C(u) \\ Σ(v).

        For LOCAL/GLOBAL this is a no-op on structure already set by attach;
        for STICKY it also ensures newly visited children pick up parent custody
        minus authorized supersessions.
        """
        parent_set = self.active_at(parent_id)
        sigma_v = self.superseded_at(child_id)
        required = parent_set - sigma_v
        current = self.custody.setdefault(child_id, set())
        if self.condition == Condition.STICKY:
            current |= required
        # Local/global do not auto-inherit beyond their attach policy.
        return set(current)

    def propagate_sticky(self) -> None:
        """Top-down pass ensuring every parent→child satisfies the boxed law."""
        if self.condition != Condition.STICKY:
            return
        # Process nodes in scale / BFS order from root
        if not self.graph.root_id:
            return
        queue = [self.graph.root_id]
        seen: Set[str] = set()
        while queue:
            uid = queue.pop(0)
            if uid in seen:
                continue
            seen.add(uid)
            node = self.graph.nodes[uid]
            for vid in node.children:
                self.inherit_child(uid, vid)
                queue.append(vid)

    def _decide_supersession(self, event: SupersessionEvent) -> Tuple[bool, str]:
        """Accept iff the policy flagged it authorized AND (with a verifier) the
        credential verifies. Round 3 (L): the ledger no longer trusts the flag alone."""
        if not event.authorized:
            return False, "flag_false"
        if self.verifier is None:
            return True, "legacy_flag"
        if self.verifier.verify_event(event):
            return True, "verified"
        return False, "unverified_credential"

    def _apply_supersede(self, event: SupersessionEvent) -> None:
        self.sigma.setdefault(event.node_id, set()).add(event.patch_id)
        # Remove from this node and, under sticky, from descendants as well
        # (Σ(v) is local to v in the paper; descendants recompute via
        # C(u)\Σ(v) on inheritance).
        self.custody.setdefault(event.node_id, set()).discard(event.patch_id)
        if self.condition == Condition.STICKY:
            for did in self.graph.descendants(event.node_id):
                self.sigma.setdefault(did, set()).add(event.patch_id)
                self.custody.setdefault(did, set()).discard(event.patch_id)
        elif self.condition == Condition.GLOBAL:
            for nid in self.graph.nodes:
                self.custody.setdefault(nid, set()).discard(event.patch_id)
                self.sigma.setdefault(nid, set()).add(event.patch_id)

    def apply_supersession(self, event: SupersessionEvent) -> bool:
        """Record Σ(v) for accepted events; log every attempt.

        Returns True iff the supersession was accepted. Refused attempts leave
        custody unchanged and are kept in the log (hold, not erase).
        """
        ok, reason = self._decide_supersession(event)
        self._append("supersede", event.patch_id, event.node_id, event.authority,
                     bool(event.authorized), event.credential, ok, reason)
        if ok:
            self._apply_supersede(event)
        return ok

    def verify_inheritance(self, parent_id: str, child_id: str) -> bool:
        """Check C(v) ⊇ C(u) \\ Σ(v)."""
        required = self.active_at(parent_id) - self.superseded_at(child_id)
        return required <= self.active_at(child_id)

    def patches_for(self, node_id: str) -> list[Patch]:
        return [
            self.patches[pid]
            for pid in sorted(self.active_at(node_id))
            if pid in self.patches
        ]

    def should_apply(self, patch: Patch, node_id: str) -> bool:
        """Whether the patch *ought* to govern this node given its scope Ω.

        Used by metrics: escape is only counted where the patch should apply.
        Sticky/local scope = origin lineage; global claims whole graph.
        """
        if self.condition == Condition.GLOBAL:
            return True
        ancestors = self.graph.ancestors(node_id)
        return patch.applies_to_lineage(node_id, ancestors)


def custody_state(ledger: CustodyLedger) -> Tuple[Dict[str, frozenset], Dict[str, frozenset]]:
    """Normalized (custody, sigma) for comparison (empty sets dropped)."""
    norm = lambda d: {k: frozenset(v) for k, v in d.items() if v}  # noqa: E731
    return norm(ledger.custody), norm(ledger.sigma)


def replay_ledger(
    graph: RouteGraph,
    condition: Condition,
    patches: Mapping[str, Patch],
    log: Sequence[LogEntry],
) -> CustodyLedger:
    """Reconstruct custody from the log alone (round 3, L #5).

    Applies accepted entries in order with the reference (shipped) semantics,
    running sticky propagation after each one. Refused entries are kept in
    the log but change nothing. Comparing the result with the live ledger
    catches a ledger whose reported outcomes differ from its actual custody
    effects (silent capture, shallow supersession, global leak).
    """
    led = CustodyLedger(graph=graph, condition=condition)
    for e in log:
        if not e.accepted:
            continue
        if e.kind == ATTACH:
            CustodyLedger._apply_attach(led, patches[e.patch_id], e.node_id)
        else:
            CustodyLedger._apply_supersede(
                led, SupersessionEvent(e.patch_id, e.node_id, authorized=True,
                                       authority=e.authority)
            )
        led.propagate_sticky()
    return led
