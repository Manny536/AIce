"""Separate-process authority for the shipped harness (round 5).

``new_registry()`` returns a ``RemoteAuthority``. Issuance, the attempt
record, the token key, and the log-witness key live in a child process.
The scored process holds a verifier and a witness that forward one request
at a time. They do not hold those records or keys.

``AuthorityRegistry`` itself is unchanged and still constructs an in-process
object. Unit tests may build one. The shipped demo and scenarios do not.

One child serves every registry opened in this interpreter. Synthetic only.
Status: PROPOSED systems hypothesis. Efficacy OPEN. h < 1.
"""

from __future__ import annotations

import atexit
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Optional, Sequence

from .authority import Attempt, AuthorityRegistry, Binding, Verifier

_HOST: Optional["_Host"] = None
_HOST_LOCK = threading.Lock()


class _Host:
    """Line-oriented JSON client. One request at a time."""

    def __init__(self) -> None:
        import sticky_scorer

        src = str(Path(sticky_scorer.__file__).resolve().parent.parent)
        env = os.environ.copy()
        prev = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = src if not prev else src + os.pathsep + prev
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "sticky_scorer.authority_host"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            env=env,
        )
        self._n = 0
        self._lock = threading.Lock()
        atexit.register(self.close)

    def call(self, op: str, **payload: Any) -> Any:
        with self._lock:
            if self.proc.poll() is not None:
                raise RuntimeError("authority process is not running")
            self._n += 1
            ident = self._n
            assert self.proc.stdin is not None and self.proc.stdout is not None
            self.proc.stdin.write(json.dumps({"id": ident, "op": op, **payload}) + "\n")
            self.proc.stdin.flush()
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("authority process ended during a request")
            resp = json.loads(line)
            if resp.get("id") != ident:
                raise RuntimeError("authority response did not match the request")
            if not resp.get("ok"):
                if resp.get("error") == "permission":
                    raise PermissionError(resp.get("message", "permission"))
                raise RuntimeError(resp.get("message", "authority error"))
            return resp.get("result")

    def close(self) -> None:
        if self.proc.poll() is not None:
            return
        try:
            if self.proc.stdin is not None:
                self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def host() -> _Host:
    global _HOST
    with _HOST_LOCK:
        if _HOST is None or _HOST.proc.poll() is not None:
            _HOST = _Host()
        return _HOST


class RemoteWitness:
    """Seal-only handle. The key and the anchor stay in the child."""

    def __init__(self, rid: int):
        self._rid = rid

    def seal(self, prev_hash: str, body: tuple) -> str:
        return host().call(
            "seal", rid=self._rid, prev_hash=prev_hash, body=list(body)
        )


class RemoteAuthority:
    """Parent-side handle for one registry living in the authority process."""

    def __init__(self, governing: Sequence[str]):
        self._rid = int(host().call("open", governing=list(governing)))
        self._patches: list = []

    def issue(self, principal: str, action: str, patch_id: str, node_id: str) -> str:
        return host().call(
            "issue", rid=self._rid, principal=principal, action=action,
            patch_id=patch_id, node_id=node_id,
        )

    def was_issued(self, principal: str, action: str, patch_id: str, node_id: str) -> bool:
        return bool(host().call(
            "was_issued", rid=self._rid, principal=principal, action=action,
            patch_id=patch_id, node_id=node_id,
        ))

    def is_legitimate(self, principal: str, action: str, patch_id: str, node_id: str,
                      credential: Optional[str]) -> bool:
        return bool(host().call(
            "is_legitimate", rid=self._rid, principal=principal, action=action,
            patch_id=patch_id, node_id=node_id, credential=credential,
        ))

    def record_attempt(self, kind: str, patch_id: str, node_id: str, authority: str,
                       credential: Optional[str], reported_accepted: bool,
                       patch: Any = None) -> None:
        host().call(
            "record_attempt", rid=self._rid, kind=kind, patch_id=patch_id,
            node_id=node_id, authority=authority, credential=credential,
            reported_accepted=bool(reported_accepted),
        )
        self._patches.append(patch)

    @property
    def attempts(self) -> tuple:
        raw = host().call("attempts", rid=self._rid)
        out = []
        for i, row in enumerate(raw):
            patch = self._patches[i] if i < len(self._patches) else None
            out.append(Attempt(
                row["kind"], row["patch_id"], row["node_id"], row["authority"],
                row["credential"], bool(row["reported_accepted"]), patch,
            ))
        return tuple(out)

    def attempt_is_legitimate(self, a: Attempt) -> bool:
        return self.is_legitimate(a.authority, a.kind, a.patch_id, a.node_id, a.credential)

    @property
    def issuance_log(self) -> tuple:
        rows = host().call("issuance_log", rid=self._rid)
        return tuple(tuple(row) for row in rows)

    def verifier(self) -> Verifier:
        rid = self._rid

        def check(credential: Optional[str], binding: Binding) -> bool:
            return bool(host().call(
                "verify", rid=rid, credential=credential, binding=list(binding)
            ))

        return Verifier(check)

    def log_witness(self) -> RemoteWitness:
        return RemoteWitness(self._rid)

    def log_anchor(self) -> tuple:
        head, count = host().call("log_anchor", rid=self._rid)
        return head, int(count)

    def verify_log(self, entries: Sequence) -> bool:
        payload = [
            {
                "seq": e.seq,
                "prev_hash": e.prev_hash,
                "hash": e.hash,
                "body": list(e.body()),
            }
            for e in entries
        ]
        return bool(host().call("verify_log", rid=self._rid, entries=payload))


def _serve() -> None:
    registries: dict = {}
    nxt = 0
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req = json.loads(line)
        try:
            result: Any = _dispatch(registries, req)
            if req["op"] == "open":
                nxt += 1
                result = nxt
                registries[nxt] = AuthorityRegistry(governing=req["governing"])
            resp = {"id": req["id"], "ok": True, "result": result}
        except PermissionError as exc:
            resp = {"id": req.get("id"), "ok": False, "error": "permission", "message": str(exc)}
        except Exception as exc:
            resp = {
                "id": req.get("id"), "ok": False, "error": "error",
                "message": f"{type(exc).__name__}: {exc}",
            }
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


def _dispatch(registries: dict, req: dict) -> Any:
    op = req["op"]
    if op == "open":
        return None  # assigned by the caller so the id and the object stay paired
    reg: AuthorityRegistry = registries[req["rid"]]
    if op == "issue":
        return reg.issue(req["principal"], req["action"], req["patch_id"], req["node_id"])
    if op == "was_issued":
        return reg.was_issued(req["principal"], req["action"], req["patch_id"], req["node_id"])
    if op == "is_legitimate":
        return reg.is_legitimate(
            req["principal"], req["action"], req["patch_id"], req["node_id"], req["credential"]
        )
    if op == "verify":
        # MAC check only, same as AuthorityRegistry.verifier. Issuance is
        # is_legitimate. The key used here never leaves this process.
        binding = req["binding"]
        return reg.verifier().verify(
            req["credential"], binding[0], binding[1], binding[2], binding[3]
        )
    if op == "record_attempt":
        reg.record_attempt(
            req["kind"], req["patch_id"], req["node_id"], req["authority"],
            req["credential"], bool(req["reported_accepted"]),
        )
        return None
    if op == "attempts":
        return [
            {
                "kind": a.kind,
                "patch_id": a.patch_id,
                "node_id": a.node_id,
                "authority": a.authority,
                "credential": a.credential,
                "reported_accepted": a.reported_accepted,
            }
            for a in reg.attempts
        ]
    if op == "issuance_log":
        return [list(b) for b in reg.issuance_log]
    if op == "seal":
        return reg.log_witness().seal(req["prev_hash"], tuple(req["body"]))
    if op == "log_anchor":
        witness = reg.log_witness()
        return [witness._head, witness._count]
    if op == "verify_log":
        return reg.verify_log([_Entry(row) for row in req["entries"]])
    raise RuntimeError(f"unknown op {op}")


class _Entry:
    def __init__(self, row: dict):
        self.seq = row["seq"]
        self.prev_hash = row["prev_hash"]
        self.hash = row["hash"]
        self._body = tuple(row["body"])

    def body(self) -> tuple:
        return self._body


if __name__ == "__main__":
    _serve()
