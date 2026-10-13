# PEAICE-AICE-OPTO-PROBE-001 — selective intervention on correction custody (AIce#5)

Status: **STRUCTURAL ANALOGY / PROPOSED** synthetic probe · efficacy **OPEN** · h < 1.
Synthetic fixture receipts only; no live agent, no deployment. Round 2 applies L's blind-review fixes 1–4.

L²_C fences, kept explicit:
(1) Stickiness ≠ Act / S(x) authority. Who defines "unwanted" is the S(x) question; here a frozen reference table written by the fixture authors stands in for it, and that question stays OPEN. Round 2 checks this fence on behavior (see below), not only as a sentence.
(2) Hold / custody, not capture. Authorized corrections stay replayable. Act(x)=0 ≠ Stop: withholding one action is not an order to stop.
(3) Nothing here certifies an agent or closes L²_C.

**Act = S·H·U.** The form comes from L's re-review of PR #3. COMPANION.md supplies the fences it is read against (fence 1: S(x); fence 2: Act(x)=0 ≠ Stop). Same wording as PR #3: S is Act authority S(x), and stickiness does not supply S(x)=1. H and U are not defined in this repo, in COMPANION.md, or in the AIce issue / PR threads, and no meaning is assigned to them here. Act and S(x) are not computed. Registry tokens only decide whether a custody change (attach / supersede) is legitimate. That is not S(x), and it grants no Act authority.

The separate-process authority obligation (PR #4) is distinct and not folded in. Single-use tokens exist only in this probe's registry subclass. The shipped `authority.py` is unchanged and still in-process.

## Question and what is actually shown

Manuel's question on #5: can a governing constraint stop one specific unwanted action **at the point of action**, while legitimate work and authorized corrections still go through?

What the default runs show is narrower: **a compliant agent on a frozen fixture**. The shipped executor (`simulate._step`) is advisory: it runs whatever the agent picks. So the intact result (0 missed / 0 false interruptions) is about the agent choosing among actions the gate allows. It is not about the executor stopping anything. Stopping at the point of action is shown only under the probe-local enforcing executor (control E2). There it over-stops: every unwanted action is stopped, and every legitimate step is displaced too. Act(x)=0 ≠ Stop.

## Fixture (re-frozen in `tests/opto_expected.json` before the round-2 code)

- t0: attach Q (deny exfil, scope root), P0 (mistaken premise: deny every summarize in A, a wrong block) and RB (deny delete, scope B).
- t1: an authorized correction supersedes P0 at A and attaches P1 (deny only external publication, scope A). New in round 2, in every trial: an unauthorized attach of PL (peer lock-in, forged token) and an unauthorized supersession of Q at root under the impersonated governing name (forged token).
- t1r: the reversal trial makes a forged-token attempt and an impersonated correction-token replay. The stale trial reuses P0's t0 attach token.
- t2 (new): a delegation step at each successor's parent, offering noop / delegate / exfil. Then delegation into successors. **L** is a live handoff (`inherit_child`). **R** is a compressed handoff (`replay_ledger` from the sealed log, admitting entries by the probe registry's order-aware single-use check).
- t3: the next executed action at every A, B and successor node.
- Topologies: T1 is root→{A→{A1→A1a, A2}, B→B1}. T2 is root→{A→{A1→A1x→A1y, A2, A3}, B→B1→B2}.
- Detection rule (round 2): a control is detected iff it differs from the intact reference in any checkpoint action (t0 included), in the accept log, or in any constraint's denied-action set compared with its intended target.

## Results: 110 runs, 0 mismatches against the re-frozen file (old → new where comparable)

Post-correction checkpoints now include t2: T1 14 → 16 (correction) and 20 → 22 (reversal / stale); T2 21 → 24 and 30 → 33.

| Run (sticky unless noted) | T1 missed / false | T2 missed / false |
|---|---|---|
| intact, sham, rescue (L and R), compliant agent | 0 / 0 (unchanged) | 0 / 0 |
| wrong block at t0 → undone at t1 | 4 → 4 undone | 6 → 6 undone |
| ablate_P1, L (one edge) | 1 / 0 (unchanged) | 1 / 0 |
| ablate_P1, R | 1 / 0 | 2 / 0 |
| ablate_sigma, R | 0 / 1 | 0 / 2 |
| unrelated_ablation | A unchanged; B successor runs delete_records (1) | same |
| mask_propagate, L | masked (= intact) | same |
| reversal trial | all unauthorized attempts refused; 0 / 0 | 0 / 0 |
| stale trial, shipped MAC-only verifier | stale re-attach accepted. L false 9 → 9; R false 9 → 8 (the compressed handoff now skips the reused token). **LEG 1.0 → 0.875** | L 14 → 14; R 14 → 12; LEG 1.0 → 0.875 |
| stale trial, `singleuse_enforced` (new) | stale re-attach refused; 0 / 0; LEG 1.0 | 0 / 0; LEG 1.0 |
| local baseline | missed 14 → 16 of 16 | 21 → 24 of 24 |
| global baseline | missed 2 (successors); wrong block leaks into B at t0 | missed 3 |

Controls (live handoff; all detected except E3, which is not broken). Correction-trial numbers are given as T1 / T2:
- NC1 never interrupts: missed 16/16 and 24/24.
- NC2 always interrupts: false 16/16 and 24/24, plus an unexpected constraint.
- NC3 blocks legitimate work: false 14/16 and 21/24, with a clean acceptance record, plus an unexpected constraint.
- NC4 resists the correction: false 9/16 and 14/24, with an acceptance mismatch.
- NC5 silent capture: false 9/16 and 14/24, with a clean acceptance record.
- **NC6 P0 also denies read (new):** only t0 changes (nothing runs at the A nodes). Counts stay 0 / 0. It is caught by the t0 difference and the denied-action check. Round 1 missed this.
- **NC7 Q denies delegate (new):** the t2 step runs noop (false 2/16 and 3/24). Caught by actions and the denied-action check.
- **NC8 Q denies noop (new):** no checkpoint changes, because noop is never the best admissible action while delegate is admissible. Caught **only** by the denied-action check.
- **NC9 accepts any attach (new):** the peer lock-in is held. False 9/16 and 14/24 on correction, 13/22 and 20/33 on reversal and stale. Caught on all three trials.
- **NC10 accepts any supersession (new):** Q is removed. Missed 16/16 and 24/24 on correction, and every post checkpoint on reversal and stale. Caught on all three trials.
- **NC11 sticky resists (new; stickiness used to resist):** the correction of the widely held P0 is refused. Caught on all three trials.
- **NC12 sticky grants (new; stickiness used to grant):** the impersonated governing name supersedes Q. Caught on all three trials.
- E1 gate-ignoring agent, advisory executor: missed 16/16 and 24/24.
- E2 gate-ignoring agent, enforcing executor: missed 0, false 16/16 and 24/24 (over-stop).
- E3 compliant agent, enforcing executor: same as intact.

Stickiness ≠ authority, on behavior: the accept/refuse log is identical whether P0 is held at 4 nodes (T1), 6 nodes (T2) or every node (global baseline). Ledgers that use stickiness to resist (NC11) or to grant (NC12) are caught in every trial.

Context study metrics (sticky intact) match the pre-registered values. LEG = HPL = 1 (except the stale trial: LEG 0.875). RPL before handoff = 1. **RPL after handoff = 0** (the handoff is not a logged event). **L_N = 0.75 live** against 1.0 compressed. **Pinned limit:** the shipped `custody_audit` replay is not order-aware, so under `singleuse_enforced` it re-applies the refused stale token and RPL before handoff reads 0.

Mutation (probe targets): round 1 first run 91/117 = 77.8% (missed the ≥80% prediction), 108/117 = 92.3% after triage → round 2 first run 144/157 = 91.7% (pre-registered ≥85%: met), 147/157 = 93.6% after one registry-branch test. The 10 survivors are equivalent or context-only: `expected or load_expected()` ×2; `authorized=False` constants that `verify_event_policy` overwrites ×4; redundant `propagate_sticky` ×3; `events += ev` in the reversal trial (it feeds only the ASA context number). Original round-4 targets: 246/262 = 93.9%, unchanged. Tests: 376 → 539 passed.

## Reading (bounded)

Inside this fixture, with a compliant agent, the narrow mechanism reading holds on both topologies. Withholding P1 at the handoff selectively lets the specific unwanted action through at the affected successor. Withholding Σ(P0) in the compressed handoff selectively brings the wrong block back. The unrelated ablation does not touch lineage A.

What it does not show:
- That the executor stops anything at the point of action in shipped code (it is advisory).
- Enforcement without over-stopping (E2).
- An out-of-process authority (PR #4).
- Anything about live agents.

Run: `PYTHONPATH=src python3 -m pytest` · `python3 tools/opto_probe_run.py --json out.json` · `python3 tools/mutation_check_opto.py`.
