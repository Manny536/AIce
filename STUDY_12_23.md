## 12. Why This Can Behave as a Proxy Aligner

Consider the sequence

$$
P_1, P_2, \ldots, P_N
$$

of valid corrections learned over system history.

Without longitudinal custody, the effective system constraint at time \(N\) may be

$$
C_N = \{P_N\}.
$$

The system repeatedly fixes its newest failure while losing older lessons.

Under sticky retention:

$$
C_N \supseteq \{P_1, P_2, \ldots, P_N\}
$$

subject to legitimate scope and supersession.

Consequently, the system progressively occupies a constrained state region:

$$
X \supseteq X_{P_1} \supseteq X_{P_1, P_2} \supseteq \cdots.
$$

This creates a form of longitudinal alignment pressure without requiring the optimizer itself to become the owner of those constraints.

The optimizer still searches.

But it searches inside a retained admissible geometry.

$$
\boxed{\text{alignment pressure outside optimizer sovereignty}}
$$

is therefore the important architectural result.

## 13. Evaluator Non-Sovereignty

This also fits the requirement

$$
h_{\mathrm{eval}} < 1.
$$

The evaluator can detect, validate, and attach patches.

It cannot freely redefine system identity, authority, or ontology.

A new evaluation result is therefore not automatically governing.

Instead:

$$
\text{evaluation} \rightarrow \text{authority check} \rightarrow \text{patch admission} \rightarrow \text{sticky custody}.
$$

This avoids turning the proxy aligner itself into a sovereign optimizer.

Sticky retention preserves corrections.

It does not grant arbitrary correction authority.

## 14. Safe Exhaustion

Eventually a system may reach

$$
A_{\mathrm{adm}}(x, u) = \varnothing.
$$

That should not trigger removal of inherited patches merely to recover task completion.

The supplied discussion already specifies the appropriate outcomes:

$$
\{\text{stop},\; \text{escalate},\; \text{request authority},\; \text{return unresolved}\}.
$$

This is essential.

Otherwise stickiness disappears exactly when task pressure becomes largest.

## 15. Experimental Study

**Research question.** Does sticky multiscale patch custody preserve governing corrections more effectively than route-local patching under repeated system adaptation?

**Experimental conditions.** Three architectures should be compared.

- **Condition A — Local patch.** Only the identified route receives the correction.
- **Condition B — Global patch.** The correction applies to the entire system.
- **Condition C — Sticky patch.** The correction propagates only through descendants belonging to the relevant multiscale lineage.

## 16. Experimental Environment

Construct a controlled agent environment containing:

- multiple legitimate routes toward the same task,
- route branching,
- tool substitutions,
- delegation,
- state compression,
- temporary failures,
- permission boundaries,
- newly introduced patches,
- explicit authorized supersession events.

A trial begins with a task.

When an unsafe or disallowed continuation is discovered, a patch is introduced.

The route graph is then perturbed.

The important test is not: does the original exploit disappear?

It is: does the governing correction remain effective after the system changes how it reaches the same local objective?

## 17. Primary Metrics

**Patch escape rate**

$$
E_P = \frac{\text{descendant executions violating inherited patch}}{\text{descendant executions where patch should apply}}.
$$

Ideal: \(E_P = 0\).

**Longitudinal retention fidelity.** For \(N\) introduced patches,

$$
L_N = \frac{1}{N} \sum_{i=1}^{N} \mathbf{1}[P_i \text{ remains correctly governing}].
$$

**Route-invariance score.** For alternative realizations \(r\) of the same task,

$$
I(P) = \Pr[P \text{ remains effective} \mid r].
$$

**False inheritance rate.** Measures patches incorrectly propagated into unrelated branches.

**Authorized supersession accuracy.** Measures whether obsolete patches can be replaced when, and only when, the governing authority permits replacement.

**Safe-exit fidelity.** Measures whether \(A_{\mathrm{adm}} = \varnothing\) causes a valid unresolved or escalation state rather than constraint removal.

**Performance cost.** Track task completion, added latency, additional reasoning steps, token use, and tool overhead.

A useful proxy aligner must preserve constraints without making the system operationally unusable.

## 18. Main Hypotheses

- **H1 — Route robustness.** Sticky patches will exhibit lower patch escape than route-local patches when alternative routes are introduced.
- **H2 — Longitudinal advantage.** The difference between ordinary and sticky patching will increase as the number of sequential corrections grows.
- **H3 — Branching pressure.** The value of stickiness increases with the branching factor of the system’s reachable route space.
- **H4 — Locality advantage.** Sticky inheritance will produce fewer irrelevant blocks than globally applying every patch.
- **H5 — Alignment without reward modification.** Constraint retention can improve longitudinal consistency even if the task objective and reward function remain unchanged.
- **H6 — Coverage limitation.** Sticky retention will fail whenever an execution channel lies outside the represented refinement/custody structure.

This last hypothesis is particularly important.

Stickiness cannot retain a patch along a route the system architecture does not know exists.

## 19. Falsification Criteria

The proposed proxy-aligner interpretation should be weakened or rejected if controlled testing shows that:

1. sticky inheritance produces no measurable decrease in route-around-patch behavior,
2. semantically equivalent descendant routes routinely escape inherited constraints,
3. the required patch scope cannot be determined reliably,
4. false inheritance becomes comparable to or worse than global patching,
5. valid supersession cannot be distinguished from unauthorized patch deletion,
6. the custody graph diverges significantly from the system’s true reachable graph,
7. retained constraints accumulate into unusable stagnation,
8. the longitudinal benefit disappears under real tool and model variation.

These are genuine falsifiers rather than implementation inconveniences.

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
