## 20. Relation to Existing Safety Architecture

The systems proposal has conceptual support from existing runtime-safety work.

Safety shielding has demonstrated the architecture

$$
\text{candidate actions} \rightarrow \text{safety filter} \rightarrow \text{permitted actions}
$$

rather than allowing safety to compete directly with reward.

Runtime Assurance and Simplex architectures similarly permit a less-assured high-performance controller to operate while an independent mechanism watches governing properties and invokes a trusted fallback if required. NASA has developed formal verification work around this architecture.

Those results support the feasibility of external enforcement.

They do not establish sticky multiscale retention.

That is the novel research object proposed here.

## 21. What Stickiness Does Not Solve

Sticky custody cannot determine whether the original patch was correct.

If \(P_{\mathrm{wrong}}\) is admitted, perfect retention gives

$$
P_{\mathrm{wrong}} \rightarrow P_{\mathrm{wrong}} \rightarrow P_{\mathrm{wrong}}.
$$

Stickiness magnifies custody, not truth.

Therefore the complete architecture needs both patch validity and patch persistence.

Similarly, sticky retention cannot discover all unknown unsafe states.

It only governs represented constraints over represented reachable structure.

For this reason it should be described as a proxy aligner, not a complete alignment solution.

## 22. Core Claim

The strongest defensible claim at this stage is:

$$
\boxed{
\begin{minipage}{0.86\linewidth}
A system can approximate longitudinal alignment with previously established governing constraints by attaching corrections to multiscale route lineages and requiring those corrections to remain active throughout descendant refinements unless valid authority explicitly supersedes them.
\end{minipage}
}
$$

In short:

$$
\boxed{\text{Patch} + \text{Scope} + \text{Ancestry} + \text{Retention} + \text{Authority} = \text{Sticky Custody}}
$$

and

$$
\boxed{\text{Sticky Custody over time} \longrightarrow \text{testable longitudinal constraint alignment}.}
$$

## 23. Research Status

**Established mathematical source.** Sticky Kakeya sets possess a rigorous mathematical definition, and multiscale structure is central to their study. Wang and Zahl proved the sticky Kakeya conjecture in three dimensions; the paper’s revised version was published in the Journal of the American Mathematical Society in 2026.

**Established systems precedent.** Runtime action shielding and Runtime Assurance demonstrate that invariant enforcement can be architecturally separated from the primary optimizer.

**Proposed.** The translation of geometric stickiness into multiscale patch custody.

**Open.** Whether this construction measurably improves longitudinal behavior in live generative-agent systems.

**Strongest next experiment.** Compare route-local vs global vs sticky patching while repeatedly changing the available route topology.

The result to watch is not merely task safety at one instant.

It is:

$$
\boxed{\text{Does a correction remain governing after the system evolves?}}
$$

That is the longitudinal question.

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

Does not replace the study above; it operationalizes the experimental conditions and primary metrics so longitudinal custody can be measured rather than assumed.
