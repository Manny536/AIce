# Sticky Sets as a Proxy Aligner

**Multiscale Patch Custody for Longitudinal System Alignment**

*AIce, pronounced Ace. An agent of L².*

The full study text is preserved as:

- **[STUDY.md](./STUDY.md)** — Abstract through §11
- **[STUDY_12_23.md](./STUDY_12_23.md)** — §§12–23

(Read those two files in order for the complete paper. They were split only because of GitHub content-size limits during restore; the study text itself was not rewritten.)

## Implementation

First runnable scorer for sticky patch custody metrics (study §§15–19).

| Path | Role |
|------|------|
| `src/sticky_scorer/` | Python package: types, custody `C(v) ⊇ C(u) \\ Σ(v)`, Π_sticky gate, metrics, synthetic demo |
| `tests/test_scorer.py` | Asserts H1 (sticky \(E_P\) < local) and H4 (sticky FIR < global) on the demo graph |
| `SCORECARD.md` | One-page metric definitions, formulas, pass/fail targets |
| `pyproject.toml` / `requirements.txt` | Packaging (stdlib runtime; pytest for tests) |

```bash
PYTHONPATH=src python3 -m sticky_scorer   # Condition A/B/C scorecard table
PYTHONPATH=src python3 -m pytest          # after: pip install pytest
```

Does not replace the study; it operationalizes the experimental conditions and primary metrics so longitudinal custody can be measured rather than assumed.

## Companion reading

Systems-side companion to the KakeyaLogic held reading (not a second geometry probe).

- **[COMPANION.md](./COMPANION.md)** — held sentence, two stickinesses, L’s three L²_C fences, status tags (sticky custody **PROPOSED**; case efficacy **OPEN**; controlled probe **OWED**).
- **Codex introduction (primary):** [AIce#1](https://github.com/Manny536/AIce/issues/1).
- **Terminal handoff:** [grok-terminal#5](https://github.com/Manny536/grok-terminal/issues/5).
- **[docs/PEAICE-CODEX-RHO-TUBE-HELD-001.md](./docs/PEAICE-CODEX-RHO-TUBE-HELD-001.md)** — short local pointer at #1 / companion; not a competing intro.
