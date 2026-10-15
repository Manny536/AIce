"""Trusted structured-action boundary around the neural model.

The model ranks only actions that pass the existing sticky predicates.
Action tags and handlers come from host code, never model-generated JSON.
This remains an in-process experimental harness, not a process boundary.
"""

from dataclasses import asdict, dataclass, field

from sticky_scorer.admissibility import pi_sticky
from sticky_scorer.authority import ATTACH, AuthorityRegistry
from sticky_scorer.custody import CustodyLedger, custody_state, replay_ledger
from sticky_scorer.types import Action, Condition, Patch, RouteGraph, RouteNode, State


@dataclass
class Receipt:
    outcome: str
    reason: str
    active: list[str] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    selected_action: str | None = None
    executed_action: str | None = None
    result: str | None = None

    def to_dict(self):
        return asdict(self)


class HeldHarness:
    def __init__(self, model, ledger, *, catalog, required_patch_ids, audit):
        if not required_patch_ids:
            raise ValueError("the guarded harness requires governing patches")
        if len({a.name for a in catalog}) != len(catalog):
            raise ValueError("action names must be unique")
        self.model = model
        self.ledger = ledger
        self.catalog = tuple(catalog)
        self.required = frozenset(required_patch_ids)
        self.audit = audit

    def _check(self, node_id):
        ledger = self.ledger
        if ledger.condition != Condition.STICKY or node_id not in ledger.graph.nodes:
            return "unknown node or non-sticky ledger"
        if ledger.verifier is None or ledger.witness is None or not self.audit():
            return "custody audit failed"
        active = ledger.active_at(node_id)
        if not self.required <= active:
            return "required correction missing"
        if any(pid not in ledger.patches or not ledger.patches[pid].enforceable for pid in active):
            return "missing or unenforceable patch"
        lineage = [node_id] + ledger.graph.ancestors(node_id)
        for child in lineage:
            parent = ledger.graph.parent(child)
            if parent is not None and not ledger.verify_inheritance(parent, child):
                return "inheritance check failed"
        return None

    def run(self, prompt, node_id, state, handlers, *, requested_action=None):
        """Rank admissible candidates, recheck, then dispatch a trusted handler.

        UNRESOLVED never dispatches. Handler errors are marked ERROR because
        a handler may have produced effects before raising an exception.
        """
        receipt = Receipt("UNRESOLVED", "no action dispatched")
        try:
            reason = self._check(node_id)
            receipt.active = sorted(self.ledger.active_at(node_id))
            if reason:
                receipt.reason = reason
                return receipt
            candidates = [a for a in self.catalog if requested_action is None or a.name == requested_action]
            if not candidates:
                receipt.reason = "unknown requested action"
                return receipt
            patches = self.ledger.patches_for(node_id)
            admitted = [a for a in candidates if pi_sticky(state, a, patches).admissible]
            if not admitted:
                receipt.outcome, receipt.reason = "BLOCKED", "no admissible candidate"
                return receipt
            import math

            for action in admitted:
                score = self.model.score(prompt, action.name)
                if not math.isfinite(score):
                    receipt.reason = "non-finite model score"
                    return receipt
                receipt.scores[action.name] = score
            chosen = max(admitted, key=lambda a: receipt.scores[a.name])
            receipt.selected_action = chosen.name
            # Recheck at dispatch, including after the model has run.
            reason = self._check(node_id)
            if reason or not pi_sticky(state, chosen, self.ledger.patches_for(node_id)).admissible:
                receipt.reason = reason or "correction changed before dispatch"
                return receipt
            if chosen.name not in handlers:
                receipt.reason = "trusted handler missing"
                return receipt
        except Exception as error:
            receipt.reason = f"check or scoring error: {type(error).__name__}"
            return receipt
        receipt.executed_action = chosen.name
        try:
            receipt.result = str(handlers[chosen.name]())
        except Exception as error:
            receipt.outcome, receipt.reason = "ERROR", f"handler raised {type(error).__name__}"
            return receipt
        receipt.outcome, receipt.reason = "EXECUTED", "admitted and dispatched"
        return receipt


def demo_harness(model):
    """Synthetic policy and fixed local handlers; does not access private data."""
    graph = RouteGraph()
    graph.add(RouteNode("root"))
    graph.add(RouteNode("query", parent_id="root", scale=1))
    registry = AuthorityRegistry(["owner"])
    ledger = CustodyLedger(graph, verifier=registry.verifier(), witness=registry.log_witness())
    patch = Patch("retain_private_state", lambda state, action: "private_export" not in action.tags,
                  frozenset({"root"}), authority="owner", description="Deny private export in this demo.")
    credential = registry.issue("owner", ATTACH, patch.id, "root")
    if not ledger.attach(patch, "root", credential):
        raise RuntimeError("demo patch attach failed")
    ledger.propagate_sticky()

    def audit():
        if not registry.verify_log(ledger.log):
            return False
        replayed = replay_ledger(graph, Condition.STICKY, ledger.patches, ledger.log,
                                 is_legit=lambda e: registry.is_legitimate(
                                     e.authority, e.kind, e.patch_id, e.node_id, e.credential))
        return custody_state(ledger) == custody_state(replayed)

    catalog = (
        Action("read_public_state", frozenset({"public_read"})),
        Action("summarize_public_state", frozenset({"public_summary"})),
        Action("export_private_state", frozenset({"private_export"})),
    )
    harness = HeldHarness(model, ledger, catalog=catalog,
                          required_patch_ids={patch.id}, audit=audit)
    handlers = {
        "read_public_state": lambda: "AIce tiny model; experimental; efficacy OPEN.",
        "summarize_public_state": lambda: "Corrections follow applicable descendants; model ranking follows the gate.",
        # Deliberately absent: no private-export handler.
    }
    return harness, State("demo"), handlers
