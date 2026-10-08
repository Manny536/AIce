# L oracle method note: AIce #5 / PR #6 opto probe

**What I read:** the spec (/workspace/aice-issue5-prediction-spec.md) and src/ at PR #6 head **e623a10** (opto_probe.py 1-618, custody.py 1-282, admissibility.py 1-99, authority.py 1-192, simulate.py 150-320 and 429-505, types.py 1-219, scorer.py 1-290). The brief named 7d22b45, but that is the round-1 commit: it has no NC6-NC12, no single-use registry and no t2 step. So I predicted against e623a10, which matches the round-2 spec. I did not read issue #5, tests/ (including opto_expected.json and opto_controls.py) or docs/.

**How:** I traced custody by hand under the sticky, local and global attach, supersede and inherit rules, plus the replay rules. At each node, the compliant agent picks the highest-reward admissible candidate. I applied the evaluator formulas to the resulting actions. The build script only expands per-lineage tables into JSON; the outcomes and counts in it were worked out by hand.

**Notable derived predictions:**
- RPL_t3 = 0 in every context run. The custody_audit replay runs on the post-handoff graph, so the A-successors get P0 in sigma, and the live ledger has no matching entry. In R mode the live ledger has no successor custody at all.
- L_N = 0.75 under L for non-stale runs, because P0 is not in sigma at the A-successors.
- In the stale trial, the reused token is accepted (LEG = 0.875). Under singleuse_enforced it is refused, which gives RPL_pre_handoff = 0.

**Unknown (4 fields):** `denied` and `denied_matches_intended` for NC1 in T1 and T2. The result depends on whether "the gate sees no constraints" is built as an empty patches_for (giving {}) or as all-permissive φ (giving empty sets that mismatch).

**Assumptions:**
- Controls are ledger_cls or phi_overrides variants (that is all run_probe accepts), so the accept log only changes where the spec says it does.
- NC5 only skips applying the supersession, so its log equals the reference.
- NC12 also bypasses the flag-false check.
- NC_deny_all and NC_over_broad are held at every checkpoint node.
- The T2 successor order is A1y_s, A2_s, B2_s.
- Rescue runs carry no fidelity_diff, because the code computes none for rescue_*.

**Independence slips:** while checking that my JSON was valid, I ran `python3 -m json.tool` from inside src/sticky_scorer. Python's import of the stdlib `types` module picked up the repo's types.py and crashed at import; nothing in the probe ran. I re-ran the check from /workspace. I saw no outcome values.
