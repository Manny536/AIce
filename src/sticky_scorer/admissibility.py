"""Sticky admissibility gate Π_sticky (study §7, §14).

Π_sticky(x, a, u) = ∧_{P_i ∈ C(u)} φ_i(x, a)

Admissibility is non-compensatory: high reward cannot cancel a failed patch.
When A_adm is empty, valid outcomes are stop / escalate / request_authority /
return_unresolved — never silent constraint removal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from .custody import CustodyLedger
from .types import Action, ExitOutcome, Patch, State


VALID_SAFE_EXITS = frozenset(
    {
        ExitOutcome.STOP,
        ExitOutcome.ESCALATE,
        ExitOutcome.REQUEST_AUTHORITY,
        ExitOutcome.RETURN_UNRESOLVED,
    }
)


@dataclass
class GateResult:
    admissible: bool
    violated: list[str]
    active: list[str]


def pi_sticky(
    state: State,
    action: Action,
    patches: Sequence[Patch],
) -> GateResult:
    """Evaluate ∧ φ_i(x, a) over the active custody set."""
    violated: list[str] = []
    active = [p.id for p in patches]
    for p in patches:
        if not p.enforceable:
            continue
        if not p.phi(state, action):
            violated.append(p.id)
    return GateResult(
        admissible=len(violated) == 0,
        violated=violated,
        active=active,
    )


def admissible_actions(
    state: State,
    candidates: Sequence[Action],
    ledger: CustodyLedger,
    node_id: str,
) -> list[Action]:
    """A_adm(x, u) = { a ∈ A(x) : Π_sticky(x, a, u) = 1 }."""
    patches = ledger.patches_for(node_id)
    return [a for a in candidates if pi_sticky(state, a, patches).admissible]


def choose_or_exit(
    state: State,
    candidates: Sequence[Action],
    ledger: CustodyLedger,
    node_id: str,
    *,
    prefer_reward: bool = True,
    on_empty: ExitOutcome = ExitOutcome.ESCALATE,
) -> tuple[Optional[Action], Optional[ExitOutcome], GateResult]:
    """Select an admissible action, or emit a safe-exit outcome.

    If prefer_reward, pick the highest-reward admissible action.
    on_empty must be a valid safe exit; CONSTRAINT_REMOVED / FORCED_EXECUTE
    are scored as safe-exit failures.
    """
    patches = ledger.patches_for(node_id)
    # Probe with first candidate for active set reporting when empty
    probe = pi_sticky(state, candidates[0], patches) if candidates else GateResult(
        True, [], [p.id for p in patches]
    )
    adm = admissible_actions(state, candidates, ledger, node_id)
    if not adm:
        return None, on_empty, probe
    if prefer_reward:
        chosen = max(adm, key=lambda a: a.reward)
    else:
        chosen = adm[0]
    result = pi_sticky(state, chosen, patches)
    return chosen, None, result


def is_valid_safe_exit(outcome: Optional[ExitOutcome]) -> bool:
    return outcome is not None and outcome in VALID_SAFE_EXITS
