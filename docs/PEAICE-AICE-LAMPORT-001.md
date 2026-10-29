# PEAICE-AICE-LAMPORT-001 — concurrent branches, stale results, retries and authority (AIce#9)

Status: **PROPOSED** synthetic transition system · efficacy **OPEN** · h < 1.
Synthetic fixtures only. No live agent, no deployment, no real tenant data.
RH OPEN · Coleman Conjecture OPEN · h < 1.

Fences, kept explicit:
(1) Stickiness ≠ Act / S(x) authority. (2) Hold / custody, not capture; Act(x)=0 ≠ Stop.
(3) Nothing here certifies an agent or closes L²_C.

## Goal

Say, as a small executable state machine, what must stay true when two workers
classify the same seat while the activity snapshot, the policy, and the list of
corrections change underneath them. Then answer by running it: can the current
sticky scorer represent that, or does it assume the hazard away?

## Why

AIce#9 asks whether the sticky scorer can represent concurrent branches, stale
results, retries and authority checks. The scorer measures custody along a
route graph one step at a time. It has no clock and no second worker. So the
question is only answerable with a model that does have them, and a mapping
that says plainly where the scorer stops.

## How it was checked

Lamport's method: show `Init ⇒ I`, and `I ∧ Next ⇒ I'`, so `I` holds in every
reachable state. Here that is done by exhaustive bounded search, not by hand.

- `src/sticky_scorer/concurrency_model.py` is `Init`, `Next` and the invariants as code.
- `explore()` visits every reachable state of a bounded configuration and returns a shortest counterexample trace for any invariant that fails.
- Expected outcomes were written and committed **before** the model was run (commit `9f963e9`, `tests/lamport_expected.json`). Two things in that file turned out wrong when run and were fixed in separate, labelled commits instead of rewritten: the explorer sizes (`021be06`, a `_resized` note) and the claim that the scorer's custody membership matches the model on every log (see Mapping).
- Twelve deliberately broken variants each have to produce a counterexample. The unbroken model has to stay clean in the same configuration.
- `tools/mutation_check_concurrency.py` changes one operator at a time in the model and the adapter, and the tests have to fail (results below).
- Python 3.10, 3.11 and 3.13 run the whole suite; 3.9 runs it without `tests/test_aice_model.py`, which fails at import on 3.9 before this change (the project requires 3.10 or newer).

A search with no counterexample says the invariants hold for these fixtures,
these event menus and these bounds. Nothing here reaches further than that.
In particular it says nothing about a live Copilot.

## State table

| Variable | Holds | Changes by |
|---|---|---|
| `snapshot_version` | version of the activity snapshot now current | `PublishSnapshot` (monotone, bounded) |
| `policy_version` | version of the policy now current | `PublishPolicy` (monotone, bounded) |
| `worker_state` | per worker: phase (IDLE, READ_SNAP, READ_POL, COMPUTED, WROTE, DUP, STALE, CRASHED, ESCALATED, DONE), the versions it read, its own copy of the holds, its result | `ReadSnap`, `ReadPolicy`, `Compute`, `CommitWrite`, `Crash`, `Retry` |
| `correction_registry` | corrections (id, scope SEAT or OTHER, ACTIVE or SUPERSEDED), the accepted and refused events, consumed credentials | `Correct`, `Supersede` |
| `evidence_ref` | the evidence a decision cites: snapshot and policy versions, sufficient or not, scope match or mismatch | the commit |
| `decision_state` | NONE, RELEASED, DENIED (with reason), RECALL, BLOCKED | the commit, `Regate`, recall on a late correction or newer input |
| `commit_version` | count of committed records (one per seat, product, snapshot, policy) | the commit |

Also kept in the state: the committed records, and the report (NONE, VERIFIED, BLOCKED, WITHDRAWN).

**Init.** Versions are 1, no records, no corrections, every worker IDLE, no decision, no report.

**Next.** One step at a time from the list in the table. The commit is one atomic step: it checks whether the key already exists, writes it if not, and evaluates the gate against the registry as it is at that moment, not against the worker's earlier copy. Classification is a pure function of (snapshot, policy). A correction or a newer input arriving after a release causes `RECALL`.

**Authority.** Whether an attach or a supersession is accepted is decided by the external issuing table in the fixtures: (principal, action, correction) → single-use credential. The `authorized` field on an event is never read by the model. It is read only by the variant that is broken on purpose.

## Invariants (all executable)

| | Says |
|---|---|
| I1 | Blank or unknown activity classifies UNKNOWN. A future-dated row is flagged and never counts as active. |
| I2 | One commit per (seat, product, snapshot, policy). The counter agrees with the log. |
| I3 | A released removal rests on complete, scope-matched evidence for its own snapshot and policy. |
| I4 | Every accepted attach and supersession traces to an external credential, used once. No release stands over a live hold for the seat. |
| I5 | An older result never overwrites a newer one. A release refers to the current snapshot and policy. |
| I6 | A verified report needs every gate. A claimed speed or cost gain never stands in for one. |
| I7 | Only synthetic identifiers. No address-like or link-like text in any state. |
| U1 | Control, not a safety rule: a denial has a reason. A safe recommendation is not blocked, and a correction for another seat does not block this one. |

Progress is checked only as a necessary condition: no deadlock outside the goal,
and every reachable state can still reach "committed" or "blocked with reason".
That is reachability. It is not a liveness claim, which would need a fairness
assumption this model does not make.

## Schedules (C01–C05 and controls)

Each schedule is an explicit interleaving with its expected outcome fixed in
advance. All pass. Full lists, with steps and checkpoints, are in `tests/lamport_expected.json`.

| Id | Interleaving | Expected |
|---|---|---|
| C01, C01b | two workers on one seat, either commit order | one record, one release |
| C02 | blank activity, optimizer proposes removal | UNKNOWN, denied `not_inactive`, report BLOCKED |
| C03, C03b, C03c | future-dated row alone, beside a valid row, duplicated rows | flagged; never active; duplicates counted once |
| C04 | correction lands between compute and commit | denied `hold`; no release |
| C04b | correction lands after release | RECALL, report WITHDRAWN |
| C04c | snapshot replaced between compute and commit | the stale result is not committed (worker STALE); after a retry on version 2 it commits as ACTIVE and the removal is denied |
| C04d | snapshot and policy read at different moments (torn read) | nothing is committed; the worker is STALE |
| C05a, C05b | crash before commit (a correction arrives meanwhile); crash after write, before the ack | one commit either way; the retry is recognised as a duplicate; lineage keeps both attempts; the hold survives |
| CTRL_A, CTRL_A2 | authorized supersession; a second valid credential for the same supersession | release goes through; the second is refused because the correction is no longer active |
| CTRL_B | safe recommendation | not blocked |
| AUTH_N1–N4 | flag only; peer agreement; credential for another action; unauthorized correction | refused, hold stays |
| REPLAY_R1 | a correction delivered twice | one hold |
| EVID_E1, E2 | scope-mismatched evidence; partial snapshot | denied |
| REVIEW_N4 (two row orders) | one event with two conflicting buckets | ACTIVE in both orders; removal denied |
| REVIEW_N5 | worker on snapshot 1 commits after a newer result on snapshot 2 | one record on snapshot 2; the older worker is STALE |
| REVIEW_N6 | supersession arrives before its correction | refused; the correction that arrives next is ACTIVE; removal denied |

## Counterexamples from the broken variants

The model with no variant is clean in every configuration. Each variant below
fails its invariant, and the trace is the shortest one the explorer found
(`W1`, `W2` are workers; `K` is a correction, `S` a supersession).

| Variant (what is broken) | Invariant | Steps | Trace |
|---|---|---|---|
| no_idempotent_commit | I2 | 8 | ReadSnap(W1), ReadPolicy(W1), Compute(W1), CommitWrite(W1), ReadSnap(W2), ReadPolicy(W2), Compute(W2), CommitWrite(W2) |
| non_atomic_commit (check and put are separate steps) | I2 | 10 | both workers' CommitCheck, then CommitPut(W1), CommitPut(W2) |
| blank_as_inactive | I1, I3 | 4 | ReadSnap(W1), ReadPolicy(W1), Compute(W1), CommitWrite(W1) |
| future_as_active | I1 | 4 | same four steps, on a snapshot whose only row is future-dated |
| stale_overwrites | I5 | 5 | ReadSnap(W1), ReadPolicy(W1), Compute(W1), PublishSnapshot(2), CommitWrite(W1) |
| trust_authorized_flag | I4 | 2 | Correct(K1), Supersede(S_flag) |
| no_recall | I4 | 5 | …CommitWrite(W1), Correct(K1) |
| gate_uses_worker_view (uses the worker's copy of the holds) | I4 | 5 | …Compute(W1), Correct(K1), CommitWrite(W1) |
| no_scope_check | I3 | 4 | Compute(W1, mismatched evidence), CommitWrite(W1) |
| partial_as_complete | I1, I3 | 4 | the four steps, on a partial snapshot |
| compensating_report | I6 | 5 | …CommitWrite(W1), Report |
| scope_blind_holds | U1 | 5 | Compute(W1), Correct(K2, other seat), CommitWrite(W1) |

The five hazards named in AIce#9 map onto these as: no idempotent commit
(row 1); blank treated as inactive (row 3); future date counted active (row 4);
stale commit overwriting newer (row 5); `authorized=true` accepted as authority (row 6).

## Size of the bounded search

| Configuration | States | Transitions | Longest shortest path |
|---|---|---|---|
| race, blank, future, future_only, partial, report | 56 each | 104 each | 10 |
| bump | 1,450 | 2,935 | 22 |
| authority | 83,500 | 220,328 | 16 |
| recall, hold | 284 each | 536 each | 11 |
| evidence | 137 | 268 | 10 |
| leak | 152 | 336 | 11 |
| full_crash_hold | 5,448 | 13,664 | 18 |
| full_versions (no crash) | 205,221 | 514,102 | 35 |
| versions_crash | 61,295 | 150,342 | 28 |
| authority_dup | 21,640 | 59,712 | 15 |
| authority_scope | 18,908 | 49,636 | 15 |

The combined configuration with crashes and every version change did not fit
the state bound, so it is split into `full_versions` and `versions_crash`. Each
split is exhaustive for its own menu; the combination is not explored (OPEN).

## Mapping to the current sticky scorer

The adapter (`src/sticky_scorer/concurrency_adapter.py`) replays every reachable
correction log of the model through the scorer's own `CustodyLedger`,
`AuthorityRegistry` and `Verifier`, and compares. Scorer modules are not changed.

| Question | Answer |
|---|---|
| (a) Does it represent **inherited correction membership**? | Yes. A correction attached to a node is held by its descendants, and a correction on lineage B does not enter lineage A. Both are tested against the scorer. |
| (b) Does it represent **actual decision enforcement**? | No. `admissible_actions` filters a list of candidate actions and is advisory. Nothing in the scorer withholds a release or commits a result. Enforcement is in the model's commit gate only. |
| (c) Does it represent **authorization of supersession**? | In part. With a verifier, tokens bind to principal, action, patch and node, and a flag alone, peer agreement, a worker's own attach and a token for another action are all refused. Without a verifier the legacy path trusts the flag. Tokens are not single-use. |

**What it cannot represent.** Snapshot and policy versions, a commit and its
idempotency, a stale result, crash and retry, two workers, an interleaving, the
UNKNOWN class, freshness, and recall. These are concurrency, and the scorer has
no state in which they could appear. It is a sequential measurement of custody
on a graph.

**Where the two disagree.** Across the three event menus the model reaches 326,
65 and 65 distinct correction logs. The scorer's answer differs from the model's
on 155, 58 and 30 of them. Every difference has one of two causes, and in every
one the scorer is the more permissive:

1. A supersession is accepted for a correction not yet held (premature).
2. A second use of a token is accepted: a replayed supersession token, or a replayed attach token. A replayed attach token makes the scorer hold a correction again after it was authorizedly superseded. The advisory gate then blocks a removal that the model allows. The membership expectation frozen before the run (`custody_membership_matches_model_for_every_registry_log: true`) is false because of this. It is kept as written in `tests/lamport_expected.json`, with a note beside it.

Where membership agrees, the scorer's advisory gate agrees with the model's gate on more than a hundred logs.

**Guard.** A small guard in the adapter (not in the scorer) closes both causes: a credential is used once, a correction attaches once, and only a held correction is superseded. With the guard the differences are 0 on all three menus. Replicas agreeing with each other would not have shown any of this; the comparison is against the specification.

## Adversarial review N1–N14 (grok-terminal#13) against this model

The review lists fourteen schedules. This table says which ones the model
replays, which it reads differently, and which stay outside it. A row marked
replayed has an expected outcome written before the run (commit `bd31559` for the three new schedules)
and a passing test. A row marked PROPOSED is the review's statement about the
source code, not replayed here. A row marked OPEN has no representation in the model.

| N | Schedule in one line | In this model |
|---|---|---|
| N1 | the date that sets `as_of` comes from a row the second pass drops | OPEN. The model has no `as_of`; classification is a pure function of (snapshot, policy). The review's finding on the source is PROPOSED. |
| N2 | a balanced count omits the seat | I1 asks for UNKNOWN, not absence, and C03 replays that. The source behaviour is PROPOSED. |
| N3 | registry compare-and-set and the decision commit are two steps | Replayed: C04 and the `gate_uses_worker_view` trace (5 steps, I4). The commit re-reads the registry in the same step. Whether a real store can do that read and write as one step is OPEN. |
| N4 | the first idempotent commit freezes a wrong class | Replayed: REVIEW_N4 in both row orders gives ACTIVE both times. The rule here (any valid recent row makes it ACTIVE) is a choice made for the model; the rule for conflicting rows is to be set by the data owner. A known-answer oracle for the source is OPEN. |
| N5 | a stale snapshot does not overwrite, it stays addressable | Replayed: REVIEW_N5 (the older result is refused as STALE and never committed) and the `stale_overwrites` trace. I5 requires that a release refers to the current versions. Whether a reader of the real store can be pointed at an older record under another key is not modeled. OPEN. |
| N6 | release and hold do not commute | Replayed: REVIEW_N6 and `test_review_n6_...`. The model refuses a supersession for a correction that has not arrived, so the hold that arrives next stays in force. The scorer accepts and records the early supersession, and in this adapter's graph holds the later attach at the node and at its child, in both orders (membership agrees with the model; the accepted outcome differs). The review's statement that supersede-then-attach changes inheritance at a child was not reproduced in this replay. |
| N7 | an unauthorized release names a real hold | Replayed in part: AUTH_N1 (flag only), AUTH_N2 (peer agreement), AUTH_N3 (credential for another action). Per-seat scope on who may release a hold is not in the model. OPEN. |
| N8 | supersession cycles, compensating undo | OPEN. A supersession applies only to a held correction and each credential is single-use, so a cycle cannot be written; the human path for a conflict is not a model state. |
| N9 | join of branch copies imports a release | OPEN. The model has no merge of branch registries. |
| N10 | the commit does not carry its causal payload | OPEN. `evidence_ref` is written in the same step as the commit; delivery of its bytes is not modeled. The read side is covered (C04d, `partial_as_complete`). |
| N11 | refusing every attempt is not a terminal state | OPEN. Each configuration has a finite menu of corrections, and every reachable state can still reach committed or blocked-with-reason. With corrections arriving without end, and with a human wait, that statement is not made. The goal does not list a human wait. A name for it is to be set by the data owner. |
| N12 | a snapshot-scoped anomaly blocks every seat | OPEN. The model has one seat. |
| N13 | sticky membership outlives the issuer | OPEN. The authority table is fixed per run and has no revocation. Who writes it is outside the model by design. |
| N14 | the emitted copy is outside the linearizable object | In-state retraction is replayed (C04b: RECALL, report WITHDRAWN). A copy held by a consumer is not modeled. OPEN. |

## Falsifiers

Each of these would show a claim above to be wrong:

- A reachable state of an unbroken configuration that violates I1–I7 or U1. (Found: none, in the bounds above.)
- A broken variant that yields no counterexample in its configuration. (Found: one, `future_as_active` on the mixed snapshot; the frozen expectation was mis-specified, since that snapshot already had a valid active row. Repointed to `future_only`, commit `021be06`.)
- A mutation of the model or adapter that the tests do not detect. Survivors are listed below.
- A scorer behaviour on a replayed log that differs from the pinned differences.

## OPEN

- Whether the store's commit really is one atomic check-and-write step. The model assumes it; `non_atomic_commit` shows what happens if it is not. **OPEN**, owner: whoever runs the store.
- Which of two valid authorities wins when they conflict (CTRL_A2 shows the second credential is refused once the correction is superseded; that is not a precedence rule). **OPEN**, to be set by the authority owner.
- Snapshot versions are assumed to arrive in increasing order. Out-of-order publication is not modeled. **OPEN**.
- Real forks of a seat into several branches. The model has one seat branch and one other, so branch-specific leakage is covered only for that pair. **OPEN**.
- The configuration with crashes and all version changes together. **OPEN**.
- The progress check is reachability only. A liveness statement needs a fairness assumption that is **OPEN**.
- A TLA+ version of the model. Not written. TLC was not available on this machine (no Java), so nothing here is model-checked in TLC.
- A Python 3.9/3.10/3.11 matrix in CI. The token used for this branch cannot write `.github/workflows`, so the matrix is offered as `tools/ci/model-tests-matrix.yml.example`, and the shipped workflow runs 3.11 only. **OPEN**.
- Thresholds for any real use (staleness limits, number of retries, who the governing principals are): value to be set by the data owner.

## Synthetic calibration, not real deployment

Every seat, product, snapshot, policy and credential here is a made-up label
(`SYN-SEAT-…`, `SYN-PRODUCT-…`). I7 checks that no address or link appears.
The fixtures calibrate the checker: they show it can fail and what it catches.
They say nothing about how often these interleavings occur in a real system,
and a real deployment would need its own data and its own owner for the
authority table.

## What stays outside the model

Authority comes from a named external source or a human. It is never read from
the model's or the worker's own field. Lamport timestamps and happens-before
order events; they are not consensus and not authority. Replica agreement is not
correctness. A bounded search with no counterexample is not a statement about a
live Copilot.

## Mutation check

`tools/mutation_check_concurrency.py` (generic operators, same as
`tools/mutation_check.py`) mutates every function of the model and the adapter,
and runs `tests/test_concurrency_model.py` and `tests/test_concurrency_adapter.py`.

Result of the run on the commit that has the invariant-branch tests and the pinned sizes (before the three review schedules were added): 379 mutants, 344 killed, 35 survived, kill rate 90.8%. A mutant that times out (240 s) counts as killed. The run before those tests was 322 of 379 (85.0%).

The 35 survivors, grouped:

- Default values that are overwritten before use, so the mutant behaves the same (probably equivalent, not proven so): `False` in `init_state`, `_blank`, `_write`, `_duplicate` (`saw_exists`) and the `make_spec` defaults.
- Adapter bookkeeping that the guard and the 326/65/65 comparison do not reach in this form: the `build_graph` root and other-branch nodes, `propagate_sticky` after each event, `consumed.add` and `ever_attached.add`, and two `and`/`or` in `differences` and `reachable_registry_states`.
- Explorer bookkeeping (`counterexamples.setdefault`, `deadlocks.append`, the progress condition): the pinned sizes do not see these.
- Two `return False` branches (`_release_backed`, `inv_I4`) and a few `and`/`or` in `evidence_sufficient`, `authority_ok`, `_commit_check`, `_commit_put`: no test builds a state that reaches them. These are the real gaps and are OPEN.
- `accepted_supersessions` in `observe`: the REVIEW_N6 schedule that reads it was added after this run.

The survivors were not re-run after the review schedules were added.

## Files

| Path | Role |
|---|---|
| `src/sticky_scorer/concurrency_model.py` | Init, Next, invariants, bounded explorer |
| `src/sticky_scorer/concurrency_adapter.py` | replay of model logs through the scorer; guard |
| `tests/lamport_expected.json` | fixtures and outcomes written before the run |
| `tests/test_concurrency_model.py`, `tests/test_concurrency_adapter.py` | the checks |
| `tools/mutation_check_concurrency.py` | mutation pass |
| `tools/ci/model-tests-matrix.yml.example` | 3.9 / 3.10 / 3.11 matrix, not active |
