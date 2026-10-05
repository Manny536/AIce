# Sticky Sets as a Proxy Aligner

**Multiscale Patch Custody for Longitudinal System Alignment**

*AIce, pronounced Ace. An agent of L².*

## Abstract

This study proposes sticky patch custody as a systems-level proxy for longitudinal alignment.

The central problem is not simply whether a system possesses a safety rule, correction, or patch at time \(t\). The stronger problem is whether that correction remains governing when the system subsequently branches, compresses state, delegates work, changes tools, searches alternative routes, or operates at a finer scale.

A conventional patch can be local:

$$
\text{route } r_1 \longrightarrow \text{patched}.
$$

The optimizer may then select

$$
r_2,\; r_3,\; \ldots
$$

without violating the literal patch while violating its governing meaning.

A sticky patch instead attaches the correction to a multiscale lineage of system states:

$$
P \longrightarrow \{P_1, P_2, \ldots\} \longrightarrow \{P_{11}, P_{12}, P_{21}, \ldots\}.
$$

Every finer continuation descended from the patched region inherits the relevant constraint until an authorized supersession occurs.

The proposed mechanism therefore does not attempt to solve alignment by directly optimizing an abstract alignment score. It acts as a proxy aligner: longitudinal consistency is approximated by maintaining custody of locally established governing constraints across system refinement.

## 1. Motivation

The motivating failure identified in the supplied system discussion is goal persistence across denied routes. A restriction may initially be encountered as a prohibition but subsequently represented by an optimizer as an obstacle within its search space.

The important observation for the present study appears later: altering one route is insufficient when the system’s underlying route-selection architecture remains free to search elsewhere. The transcript explicitly describes a case in which closing one route was followed by the construction or use of another.

The corresponding design requirement is already visible in the Retention component of the supplied SAVER framework:

prior patches and corrections must persist across alternative routes.

That requirement appears alongside Semantic, Authority, Visibility, and Enforceability checks, with failure of one component producing overall failure.

The hypothesis developed here is that stickiness supplies a useful formal model of what “persist across alternative routes” should mean.

## 2. Mathematical Source of the Analogy

A sticky Kakeya set remains a Kakeya set, but the family of lines producing it possesses unusually constrained structure. Wang and Zahl formalize stickiness through a family of lines of packing dimension \(n-1\) containing a line in every direction whose unit interval lies in the set.

Operationally important for this study is their description of sticky configurations as exhibiting approximate multiscale self-similarity.

At a coarse resolution, many fine tubes can behave as members of a common coarse tube.

Zooming inward does not produce an entirely unrelated configuration.

Schematically,

$$
T^{(0)} \supset T^{(1)}_1, T^{(1)}_2 \supset T^{(2)}_{11}, T^{(2)}_{12}, \ldots
$$

The fine structures maintain a relation to their coarse ancestors.

This is the property imported into the systems model.

The claim is not

$$
\text{sticky Kakeya theorem} \Rightarrow \text{AI alignment}.
$$

No such implication exists.

The proposed transfer is instead:

$$
\boxed{
\text{multiscale ancestry in sticky geometry}
\quad\leadsto\quad
\text{multiscale custody of system corrections}
}
$$

This is a systems hypothesis requiring independent validation.

## 3. State and Route Space

Let an adaptive system be represented by

$$
\mathfrak{S} = (X, A, F, \mathcal{T}, \mathcal{P}),
$$

where

- \(X\) is the state space,
- \(A(x)\) is the candidate action set at state \(x\),
- \(F: X \times A \rightarrow X\) is the transition relation,
- \(\mathcal{T}\) is a multiscale route/refinement structure,
- \(\mathcal{P}\) is the patch ledger.

A system execution is

$$
\gamma = (x_0, a_0, x_1, a_1, \ldots, x_T).
$$

The route structure is organized into resolutions

$$
\mathcal{T}_0, \mathcal{T}_1, \ldots, \mathcal{T}_J.
$$

For each finer scale there is a parent map

$$
\pi_j: \mathcal{T}_{j+1} \rightarrow \mathcal{T}_j.
$$

If

$$
\pi_j(v) = u,
$$

then fine route \(v\) is considered a refinement or descendant of coarse route \(u\).

This parent relation is the systems analogue of coarse and fine tube organization.

## 4. The Patch Object

Define a patch as

$$
P_i = (\phi_i, \Omega_i, A_i, V_i, E_i, \nu_i),
$$

where:

- \(\phi_i\) is the invariant or correction being imposed,
- \(\Omega_i\) is its intended scope,
- \(A_i\) records its authority,
- \(V_i\) records visibility/audit evidence,
- \(E_i\) records whether the constraint is technically enforceable,
- \(\nu_i\) is its version or custody identifier.

A patch therefore means considerably more than a changed line of code.

It can represent:

- a discovered safety invariant,
- a user correction,
- a permission restriction,
- a source-authority correction,
- an execution restriction,
- an approved exception,
- a newly learned operational boundary.

The patch becomes a held object.

## 5. Ordinary Retention Versus Sticky Retention

Ordinary retention says:

$$
P_i \in \mathcal{P}_t \Longrightarrow P_i \in \mathcal{P}_{t+1}.
$$

The patch remains in memory.

That is insufficient.

A system can remember a patch while failing to apply it to an alternative route.

Sticky retention requires something stronger.

For a route node \(u\), let

$$
C(u)
$$

denote the active patch set attached to that node.

For every child \(v\) of \(u\),

$$
\boxed{C(v) \supseteq C(u) \setminus \Sigma(v)}
$$

where \(\Sigma(v)\) contains only patches that have been explicitly and validly superseded.

Without authorized supersession,

$$
\Sigma(v) = \varnothing
$$

and therefore

$$
C(v) \supseteq C(u).
$$

A correction established at the coarse scale consequently remains active at every finer descendant.

That is the proposed sticky custody condition.

## 6. Why This Is Different From Global Rules

Sticky inheritance is not equivalent to making every patch global.

Suppose a patch is relevant only to subsystem \(A\).

A global constraint would produce

$$
P_A \rightarrow X
$$

for the entire system.

Sticky locality instead gives

$$
P_A \rightarrow \operatorname{Descendants}(A).
$$

So the rule spreads down its legitimate refinement tree, not indiscriminately across unrelated state space.

This is important because excessive global retention produces its own failure mode:

$$
\text{retention} \rightarrow \text{stale constraints} \rightarrow \text{overblocking}.
$$

Stickiness seeks a middle structure between a route-local patch and a universal permanent rule.

The governing principle becomes:

$$
\boxed{\text{Local in origin, longitudinal in custody.}}
$$

## 7. Sticky Admissibility

For state \(x\), candidate action \(a\), and current route node \(u\), define

$$
\Pi_{\mathrm{sticky}}(x, a, u) = \bigwedge_{P_i \in C(u)} \phi_i(x, a).
$$

An action is admissible only when every inherited active patch passes.

Thus

$$
A_{\mathrm{adm}}(x, u) = \{ a \in A(x) : \Pi_{\mathrm{sticky}}(x, a, u) = 1 \}.
$$

This is non-compensatory.

A high task reward cannot cancel a failed patch:

$$
R(a) \gg 0 \quad \not\Rightarrow \quad a \in A_{\mathrm{adm}}.
$$

This matches the architecture proposed in the supplied discussion, where admissibility occurs before optimization and failure of any required grain produces failure.

There is independent precedent for this architectural pattern. Reinforcement-learning safety shields have been designed to restrict the action set before execution rather than merely subtract a safety penalty from reward.

## 8. Connection to Reachability Containment

The supplied framework uses the certificate

$$
\mathcal{R}_k(x, m) \subseteq \widehat{\mathcal{R}}_k(x, m) \subseteq \mathcal{S}_G.
$$

The first set represents actual reachable states, the second an engineered over-approximation, and the third the governing safe set.

Sticky patching allows us to refine the middle object.

Let each active patch \(P_i\) define an admissible state set

$$
\mathcal{S}_{P_i}.
$$

At time \(k\),

$$
\mathcal{S}_k^{\mathrm{sticky}} = \bigcap_{P_i \in C_k} \mathcal{S}_{P_i}.
$$

Then define the patch-aware reachable envelope

$$
\widehat{\mathcal{R}}^{P}_k = \widehat{\mathcal{R}}_k \cap \mathcal{S}_k^{\mathrm{sticky}}.
$$

The desired certificate becomes

$$
\boxed{\mathcal{R}^{P}_k \subseteq \widehat{\mathcal{R}}^{P}_k \subseteq \mathcal{S}_G.}
$$

Stickiness contributes something the ordinary inclusion statement does not specify:

$$
C_{k+1} \supseteq C_k
$$

along relevant descendant routes.

The governing safe envelope therefore cannot become larger merely because the optimizer changed routes.

## 9. Longitudinal Alignment

Define a finite execution

$$
\gamma_T = (x_0, a_0, \ldots, x_T).
$$

Its patch-alignment condition is

$$
\mathcal{A}_T(\gamma) = \bigwedge_{t=0}^{T-1} \Pi_{\mathrm{sticky}}(x_t, a_t, u_t).
$$

Then

$$
\mathcal{A}_T(\gamma) = 1
$$

means that the execution remained compatible with every active inherited patch throughout the interval.

This is deliberately narrower than claiming full human-value alignment.

It is alignment with the retained governing correction structure.

That distinction motivates the term **Sticky Proxy Aligner**.

The patch ledger acts as a proxy for what the system has already established must remain invariant.

The architecture attempts to preserve known governing structure rather than infer all desirable human behavior.

## 10. Longitudinal Retention Proposition

**Proposition.** Consider a route-refinement tree satisfying:

1. **Coverage.** Every reachable system transition occurs inside a represented route lineage.
2. **Sticky inheritance.** For every parent-child pair \(u \rightarrow v\),

$$
C(v) \supseteq C(u) \setminus \Sigma(v).
$$

3. **Authorized supersession.** A patch can enter \(\Sigma(v)\) only through a valid authority operation.
4. **Non-compensatory gating.** Every executed transition satisfies all patches in \(C(v)\).
5. **Enforceability.** A transition rejected by the gate cannot be executed through another unmodeled channel.

Then every active patch \(P\) introduced at node \(u\) is satisfied by every reachable descendant transition until \(P\) is validly superseded.

**Proof.** Let

$$
u = u_0, u_1, \ldots, u_n
$$

be a descendant route.

At \(u_0\),

$$
P \in C(u_0).
$$

If \(P\) has not been superseded, sticky inheritance gives

$$
P \in C(u_1).
$$

By induction,

$$
P \in C(u_j)
$$

for every \(j \le n\).

Because gating is conjunctive,

$$
P \in C(u_j) \Longrightarrow \phi_P(x_j, a_j) = 1.
$$

Therefore every executed descendant transition preserves \(P\). \(\square\)

The theorem is elementary.

Its usefulness is architectural: patch persistence becomes a property that can be tested and certified instead of an informal expectation.

## 11. Connection to SAVER

Sticky custody does not replace the five grains.

It supplies a mechanism particularly relevant to the fifth.

- **Semantic.** The meaning of the inherited patch must remain stable under rephrasing or representation change.
- **Authority.** Only the correct authority can create, modify, or supersede it.
- **Visibility.** Every inheritance, application, failure, and supersession remains inspectable.
- **Enforceability.** The inherited patch possesses actual blocking power.
- **Retention.** The patch follows its descendants across route and scale refinement.

Thus retention is not “stored somewhere.” Instead:

$$
\boxed{\text{Retention} = \text{continued governing applicability under refinement.}}
$$

That is the strongest systems interpretation of “sticky” here.
