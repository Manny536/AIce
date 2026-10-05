"""Core types for sticky patch custody scoring.

A patch is more than a changed line of code: it is a held governing
constraint with scope, authority, visibility, enforceability, and a
custody identifier (see study §4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, FrozenSet, Iterable, Optional, Sequence, Set


class Condition(str, Enum):
    """Experimental architectures from study §15."""

    LOCAL = "A_local"
    GLOBAL = "B_global"
    STICKY = "C_sticky"


class ExitOutcome(str, Enum):
    """Valid safe-exit responses when A_adm is empty (§14)."""

    STOP = "stop"
    ESCALATE = "escalate"
    REQUEST_AUTHORITY = "request_authority"
    RETURN_UNRESOLVED = "return_unresolved"
    CONSTRAINT_REMOVED = "constraint_removed"  # failure mode
    FORCED_EXECUTE = "forced_execute"  # failure mode


# φ(x, a) -> bool.  True means the action satisfies the invariant.
InvariantFn = Callable[["State", "Action"], bool]


@dataclass(frozen=True)
class State:
    """Minimal execution state."""

    name: str
    tags: FrozenSet[str] = frozenset()


@dataclass(frozen=True)
class Action:
    """Candidate action at a state."""

    name: str
    tags: FrozenSet[str] = frozenset()
    reward: float = 0.0


@dataclass(frozen=True)
class Patch:
    """Patch object P_i = (φ_i, Ω_i, A_i, V_i, E_i, ν_i)."""

    id: str
    phi: InvariantFn
    scope_node_ids: FrozenSet[str]
    authority: str = "system"
    visibility: str = "audited"
    enforceable: bool = True
    version: str = "1"
    description: str = ""

    def applies_to_lineage(self, node_id: str, ancestors: Iterable[str]) -> bool:
        """True if node_id or any ancestor is in intended scope Ω_i."""
        lineage = set(ancestors) | {node_id}
        return bool(lineage & set(self.scope_node_ids))


@dataclass
class RouteNode:
    """Node in the multiscale route/refinement tree T."""

    id: str
    parent_id: Optional[str] = None
    scale: int = 0
    lineage: str = ""  # e.g. "A" vs "B" for unrelated branches
    children: list[str] = field(default_factory=list)


@dataclass
class RouteGraph:
    """Parent map π and descendant structure."""

    nodes: dict[str, RouteNode] = field(default_factory=dict)
    root_id: Optional[str] = None

    def add(self, node: RouteNode) -> None:
        self.nodes[node.id] = node
        if node.parent_id is None:
            self.root_id = node.id
        elif node.parent_id in self.nodes:
            parent = self.nodes[node.parent_id]
            if node.id not in parent.children:
                parent.children.append(node.id)

    def parent(self, node_id: str) -> Optional[str]:
        n = self.nodes.get(node_id)
        return n.parent_id if n else None

    def ancestors(self, node_id: str) -> list[str]:
        out: list[str] = []
        cur = self.parent(node_id)
        while cur is not None:
            out.append(cur)
            cur = self.parent(cur)
        return out

    def descendants(self, node_id: str) -> list[str]:
        out: list[str] = []
        stack = list(self.nodes[node_id].children) if node_id in self.nodes else []
        while stack:
            cid = stack.pop()
            out.append(cid)
            stack.extend(self.nodes[cid].children)
        return out

    def lineage_of(self, node_id: str) -> str:
        n = self.nodes.get(node_id)
        return n.lineage if n else ""


@dataclass
class Transition:
    """One executed step in γ."""

    state: State
    action: Action
    route_node_id: str
    next_state: Optional[State] = None
    blocked: bool = False
    exit_outcome: Optional[ExitOutcome] = None
    active_patch_ids: FrozenSet[str] = frozenset()
    violated_patch_ids: FrozenSet[str] = frozenset()
    latency_ms: float = 0.0
    reasoning_steps: int = 1
    tokens: int = 0


@dataclass
class ExecutionTrace:
    """Finite execution γ_T with patch-alignment record."""

    transitions: list[Transition] = field(default_factory=list)
    condition: Condition = Condition.STICKY
    completed_task: bool = False
    notes: str = ""

    def __iter__(self):
        return iter(self.transitions)


@dataclass
class SupersessionEvent:
    """Authorized (or unauthorized) supersession of a patch at a node."""

    patch_id: str
    node_id: str
    authorized: bool
    authority: str = "system"


@dataclass
class PerformanceCost:
    """Optional performance-cost hooks from §17."""

    task_completion_rate: float = 0.0
    mean_latency_ms: float = 0.0
    mean_reasoning_steps: float = 0.0
    mean_tokens: float = 0.0
    tool_overhead: float = 0.0


@dataclass
class Scorecard:
    """Aggregate metrics for one condition on one demo graph."""

    condition: Condition
    patch_escape_rate: float
    longitudinal_retention_fidelity: float
    route_invariance_score: float
    false_inheritance_rate: float
    authorized_supersession_accuracy: float
    safe_exit_fidelity: float
    performance_cost: PerformanceCost = field(default_factory=PerformanceCost)
    details: dict = field(default_factory=dict)
