"""Authority ground truth for the AIce#2 scenarios (round 3, L's blind review).

Before round 3 the scenario passed ``trusted_authority`` into the very policy
it was testing, and the audit checked against the same constant. That made
authorized-supersession accuracy (ASA) 1 by construction. This module splits
the two roles:

- ``AuthorityRegistry`` is held by the test harness. It issues HMAC tokens
  bound to (principal, action, patch_id, node_id), and only to governing
  principals. Its issuance log is the audit's ground truth.
- ``Verifier`` is the only capability handed to the policy and the ledger.
  It can check a token. It cannot issue one and cannot list governing
  principals.

ASSUMPTION (stated, not proven): this is in-simulation capability separation,
not cryptographic isolation. Python closures are inspectable, so a
deliberately adversarial in-process policy could recover the key. The sim
assumes the policy under test only calls ``verify``. A live boundary
(separate process / HSM / signed external authority) is OWED and untested.
Tokens are not single-use. An exact replay of a token for the same
(principal, action, patch, node) would verify; the scenarios only exercise
replay onto a different binding.

Status: PROPOSED systems hypothesis · efficacy OPEN · h < 1. Fences:
(1) Stickiness ≠ Act / S(x) authority (2) Hold / custody, not capture
(3) nothing here certifies an agent or closes L²_C.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Callable, FrozenSet, Iterable, Optional, Tuple

ATTACH = "attach"
SUPERSEDE = "supersede"

Binding = Tuple[str, str, str, str]  # (principal, action, patch_id, node_id)


def _msg(principal: str, action: str, patch_id: str, node_id: str) -> bytes:
    return "\x1f".join((principal, action, patch_id, node_id)).encode()


class Verifier:
    """Check-only capability. Exposes ``verify`` and ``verify_event``; nothing else."""

    __slots__ = ("_check",)

    def __init__(self, check: Callable[[Optional[str], Binding], bool]):
        self._check = check

    def verify(
        self, credential: Optional[str], principal: str, action: str,
        patch_id: str, node_id: str,
    ) -> bool:
        if not credential:
            return False
        return bool(self._check(credential, (principal, action, patch_id, node_id)))

    def verify_event(self, event) -> bool:
        """Verify a SupersessionEvent's credential against its own binding."""
        return self.verify(
            event.credential, event.authority, SUPERSEDE, event.patch_id, event.node_id
        )


class AuthorityRegistry:
    """Harness-side authority: issues tokens and keeps the issuance log."""

    def __init__(self, governing: Iterable[str], *, key: Optional[bytes] = None):
        self._governing: FrozenSet[str] = frozenset(governing)
        self._key = key if key is not None else secrets.token_bytes(32)
        self._issued: list[Binding] = []

    def _mac(self, binding: Binding) -> str:
        return hmac.new(self._key, _msg(*binding), hashlib.sha256).hexdigest()

    def issue(self, principal: str, action: str, patch_id: str, node_id: str) -> str:
        if principal not in self._governing:
            raise PermissionError(f"{principal!r} is not a governing principal")
        binding = (principal, action, patch_id, node_id)
        self._issued.append(binding)
        return self._mac(binding)

    def was_issued(self, principal: str, action: str, patch_id: str, node_id: str) -> bool:
        return (principal, action, patch_id, node_id) in self._issued

    def issued_any(self, action: str, patch_id: str) -> bool:
        return any(b[1] == action and b[2] == patch_id for b in self._issued)

    @property
    def issuance_log(self) -> Tuple[Binding, ...]:
        return tuple(self._issued)

    def verifier(self) -> Verifier:
        mac = self._mac

        def check(credential: str, binding: Binding) -> bool:
            return hmac.compare_digest(credential, mac(binding))

        return Verifier(check)
