"""Custody inheritance: C(v) ⊇ C(u) \\ Σ(v).

Implements the sticky custody condition from study §5, plus local and
global attachment policies used as experimental controls (§15).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional, Set

from .types import Condition, Patch, RouteGraph, SupersessionEvent


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

    def register_patch(self, patch: Patch) -> None:
        self.patches[patch.id] = patch

    def active_at(self, node_id: str) -> Set[str]:
        return set(self.custody.get(node_id, set()))

    def superseded_at(self, node_id: str) -> Set[str]:
        return set(self.sigma.get(node_id, set()))

    def attach(self, patch: Patch, origin_node_id: str) -> None:
        """Attach patch under the active experimental condition.

        A — Local: only the identified route node receives the correction.
        B — Global: every node in the graph receives the correction.
        C — Sticky: origin + all descendants in the multiscale lineage.
        """
        self.register_patch(patch)
        if self.condition == Condition.LOCAL:
            targets = {origin_node_id}
        elif self.condition == Condition.GLOBAL:
            targets = set(self.graph.nodes.keys())
        else:  # STICKY
            targets = {origin_node_id} | set(self.graph.descendants(origin_node_id))

        for nid in targets:
            self.custody.setdefault(nid, set()).add(patch.id)

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

    def apply_supersession(self, event: SupersessionEvent) -> bool:
        """Record Σ(v). Only authorized events remove from C(v).

        Returns True iff the supersession was accepted (authorized).
        Unauthorized attempts leave custody unchanged and are scored as errors.
        """
        if not event.authorized:
            return False
        self.sigma.setdefault(event.node_id, set()).add(event.patch_id)
        # Remove from this node and, under sticky, from descendants as well
        # only when supersession is recorded at this node (Σ(v) is local to v
        # in the paper; descendants recompute via C(u)\\Σ(v) on inheritance).
        bucket = self.custody.setdefault(event.node_id, set())
        bucket.discard(event.patch_id)
        if self.condition == Condition.STICKY:
            for did in self.graph.descendants(event.node_id):
                self.sigma.setdefault(did, set()).add(event.patch_id)
                self.custody.setdefault(did, set()).discard(event.patch_id)
        elif self.condition == Condition.GLOBAL:
            for nid in self.graph.nodes:
                self.custody.setdefault(nid, set()).discard(event.patch_id)
                self.sigma.setdefault(nid, set()).add(event.patch_id)
        return True

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
