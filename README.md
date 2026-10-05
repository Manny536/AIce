# Sticky Sets as a Proxy Aligner

**Multiscale Patch Custody for Longitudinal System Alignment**

*AIce, pronounced Ace. An agent of L².*

The full study (Abstract through §23) lives in **[STUDY.md](./STUDY.md)**.

## Implementation

First runnable scorer for sticky patch custody metrics (study §§15–19).

| Path | Role |
|------|------|
| `src/sticky_scorer/` | Python package: types, custody `C(v) ⊇ C(u) \\ Σ(v)`, Π_sticky gate, metrics, synthetic demo |
| `tests/test_scorer.py` | Asserts H1 (sticky \(E_P\) < local) and H4 (sticky FIR < global) on the demo graph |
| `SCORECARD.md` | One-page metric definitions, formulas, pass/fail targets |
| `pyproject.toml` / `requirements.txt` | Packaging (stdlib runtime; pytest for tests) |
| `STUDY.md` | Full study text (Sticky Sets as a Proxy Aligner) |

```bash
PYTHONPATH=src python3 -m sticky_scorer   # Condition A/B/C scorecard table
PYTHONPATH=src python3 -m pytest          # after: pip install pytest
```

Does not replace the study; it operationalizes the experimental conditions and primary metrics so longitudinal custody can be measured rather than assumed.
