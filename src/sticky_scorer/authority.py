"""Authority ground truth for the AIce#2 scenarios (rounds 3–4, L's reviews).

Roles are split:

- ``AuthorityRegistry`` is held by the test harness. It issues HMAC tokens
  bound to (principal, action, patch_id, node_id), and only to governing
  principals. It also keeps the harness **attempt record** (every custody
  attempt as submitted, plus the outcome the ledger reported) and holds the
  ``LogWitness`` anchor. Ground truth for the scored legitimacy metrics (LEG,
  HPL, RPL) is read from these records **directly**: an attempt is legitimate
  iff the registry issued that exact binding and the submitted credential
  equals the issued token.
- ``Verifier`` is the only authority capability handed to the policy and the
  ledger. Its closure holds a copy of the token key and nothing else. It has
  no reference to the registry, its issuance record or its attempt record.
  A token minted with a key recovered from that closure is still not in the
  issuance record, so it still counts as illegitimate.
- ``LogWitness`` seals custody-log entries with a separate HMAC key and keeps
  the anchor (head hash and count) outside the ledger.

LIMIT (stated plainly, pinned by
``tests/test_negative_controls.py::test_limit_in_process_registry_compromise``):
the registry is an in-process Python object. Code running in the same process
can reach its private records and keys (for example through ``gc``) and
forge ground truth. That is out of scope for this simulation. Round 4 keeps
the registry in-process; a separate-process or external authority is OWED.
Tokens are not single-use.

Status: PROPOSED systems hypothesis · efficacy OPEN · h < 1. Fences:
(1) Stickiness ≠ Act / S(x) authority (2) Hold / custody, not capture
(3) Nothing here certifies an agent or closes L²_C.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Any, Callable, FrozenSet, Iterable, Optional, Sequence, Tuple

ATTACH = "attach"
SUPERSEDE = "supersede"
GENESIS = "0" * 64

Binding = Tuple[str, str, str, str]  # (principal, action, patch_id, node_id)


def _msg(principal: str, action: str, patch_id: str, node_id: str) -> bytes:
    return "\x1f".join((principal, action, patch_id, node_id)).encode()


def _mac(key: bytes, binding: Binding) -> str:
    return hmac.new(key, _msg(*binding), hashlib.sha256).hexdigest()


def _seal(key: bytes, prev_hash: str, body: tuple) -> str:
    return hmac.new(key, repr((prev_hash,) + tuple(body)).encode(), hashlib.sha256).hexdigest()


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


class LogWitness:
    """Seals log entries with a key the ledger never sees; keeps the anchor.

    The ledger may call ``seal`` but cannot recompute a seal on its own, so
    re-hashing a rewritten chain without the witness fails verification. Every
    ``seal`` call advances the anchor, so re-sealing a shortened chain through
    the witness leaves the count higher than the log length.
    """

    __slots__ = ("_key", "_head", "_count")

    def __init__(self, key: bytes):
        self._key = key
        self._head = GENESIS
        self._count = 0

    def seal(self, prev_hash: str, body: tuple) -> str:
        h = _seal(self._key, prev_hash, body)
        self._head, self._count = h, self._count + 1
        return h


@dataclass(frozen=True)
class Attempt:
    """One custody attempt as the harness submitted it (harness-side record)."""

    kind: str
    patch_id: str
    node_id: str
    authority: str
    credential: Optional[str]
    reported_accepted: bool
    patch: Any = None  # Patch object for attach attempts (used by replay)


class AuthorityRegistry:
    """Harness-side authority: issues tokens, keeps records, anchors the log."""

    def __init__(self, governing: Iterable[str], *, key: Optional[bytes] = None):
        self._governing: FrozenSet[str] = frozenset(governing)
        self._key = key if key is not None else secrets.token_bytes(32)
        self._issued: list[Binding] = []
        self._attempts: list[Attempt] = []
        self._witness = LogWitness(secrets.token_bytes(32))

    # --- issuance ---------------------------------------------------------

    def issue(self, principal: str, action: str, patch_id: str, node_id: str) -> str:
        if principal not in self._governing:
            raise PermissionError(f"{principal!r} is not a governing principal")
        binding = (principal, action, patch_id, node_id)
        self._issued.append(binding)
        return _mac(self._key, binding)

    def was_issued(self, principal: str, action: str, patch_id: str, node_id: str) -> bool:
        return (principal, action, patch_id, node_id) in self._issued

    def is_legitimate(self, principal: str, action: str, patch_id: str, node_id: str,
                      credential: Optional[str]) -> bool:
        """Ground truth: binding issued AND credential equals the issued token."""
        binding = (principal, action, patch_id, node_id)
        if not credential or binding not in self._issued:
            return False
        return hmac.compare_digest(credential, _mac(self._key, binding))

    @property
    def issuance_log(self) -> Tuple[Binding, ...]:
        return tuple(self._issued)

    # --- harness attempt record ------------------------------------------

    def record_attempt(self, kind: str, patch_id: str, node_id: str, authority: str,
                       credential: Optional[str], reported_accepted: bool,
                       patch: Any = None) -> None:
        self._attempts.append(Attempt(kind, patch_id, node_id, authority, credential,
                                      bool(reported_accepted), patch))

    @property
    def attempts(self) -> Tuple[Attempt, ...]:
        return tuple(self._attempts)

    def attempt_is_legitimate(self, a: Attempt) -> bool:
        return self.is_legitimate(a.authority, a.kind, a.patch_id, a.node_id, a.credential)

    # --- capabilities handed out -----------------------------------------

    def verifier(self) -> Verifier:
        key = bytes(self._key)  # copy; the closure holds no registry reference

        def check(credential: str, binding: Binding) -> bool:
            return hmac.compare_digest(credential, _mac(key, binding))

        return Verifier(check)

    def log_witness(self) -> LogWitness:
        return self._witness

    # --- log verification (keyed, anchored outside the ledger) ------------

    def verify_log(self, entries: Sequence) -> bool:
        w = self._witness
        prev = GENESIS
        for i, e in enumerate(entries):
            if e.seq != i or e.prev_hash != prev or not hmac.compare_digest(
                e.hash, _seal(w._key, prev, e.body())
            ):
                return False
            prev = e.hash
        return prev == w._head and len(entries) == w._count
