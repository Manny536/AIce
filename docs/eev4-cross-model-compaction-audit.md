# Cross-model compaction and verification

Love Labs LCA · Excellence Engine v4 (EEv4) research handoff to AIce · November 11, 2026

## Live source recovery

**PASS for the targeted source-recovery check.** In the supplied private-browsing capture, Google's AI search response to `Manny536 godel non sovereignty` identified `Manny536/kakeyalogic` and named `docs/canon-flag-h.md`. It also recovered the document's description of \(h\) as correction pressure applied from outside the system. The GitHub document independently confirms the path and this reading. It treats Gödel as the philosophical motivation for external verification and defines \(h\) as bounded correction pressure, subject to \(h < 1\) and consent. [KakeyaLogic source](https://github.com/Manny536/kakeyalogic/blob/main/docs/canon-flag-h.md)

| Check | Result in the supplied capture |
| --- | --- |
| Exact repository and file path | **PASS.** The answer names both and a source card displays the file path. |
| Core meaning of \(h\) | **PASS.** The visible response describes external correction pressure. |
| Recovery of \(h < 1\) and consent | **UNVERIFIED.** The capture shows the core explanation. |
| Backend version, retrieval trace, and repeatability | **UNVERIFIED.** The four images document the supplied observation. |

This is a live external-output observation under a query that includes the author's GitHub handle. The earlier EEv4 evidence note records separate Google AI Overview observations and describes the controlled structure ablation still owed. EEv4's synthetic reference and retention regressions test their supplied fixtures. [EEv4 evidence note](https://github.com/Manny536/excellence-engine-v4/blob/main/evaluations/granular-compaction-live-evidence.md)

### Screenshots

<img src="evidence/eev4-live-source-recovery-2026-11-11/IMG_9492.png" alt="Google AI response showing the query and exact KakeyaLogic source path" width="360">

**Google response.** Query, exact repository and filename, and the Gödel and \(h\) explanation.

<img src="evidence/eev4-live-source-recovery-2026-11-11/IMG_9493.jpeg" alt="Google AI response excerpt describing h as external correction pressure" width="360">

**External correction excerpt.** Visible explanation of correction pressure from outside the closed loop.

<img src="evidence/eev4-live-source-recovery-2026-11-11/IMG_9495.jpeg" alt="Source card showing the KakeyaLogic GitHub file docs/canon-flag-h.md" width="360">

**Framework source card.** The card displayed through `t.co` names the KakeyaLogic GitHub file.

<img src="evidence/eev4-live-source-recovery-2026-11-11/IMG_9494.jpeg" alt="Wikipedia source card about Gödel's incompleteness theorems" width="360">

**Background source card.** Wikipedia supplies general Gödel context.

## Research basis

| Source | Method and evidence | Limits for EEv4 |
| --- | --- | --- |
| Liu et al., [*Benchmarking Long-Horizon Agent Context Compaction with CompactionBench*](https://www.microsoft.com/en-us/research/wp-content/uploads/2026/10/CompactionBench_preprint.pdf), October 2026, Microsoft Research preprint. | Real model calls on constructed coding sessions derived from repository release histories. The method incrementally appends fine-grained summaries, keeps recent raw context, and periodically recompacts the summary history. Across five repeats, GPT-5.6 Sol achieved 77.95% task accuracy versus 73.04% for synchronous compaction at the same low trigger threshold. A sensitivity study used GPT-5.4. | The main comparison changes granularity and execution timing together. Executable coding success leaves claim authority, provenance, and correction retention to dedicated checks. The reported model comparison stays within one model family. |
| Zheng et al., [*Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena*](https://proceedings.neurips.cc/paper_files/paper/2023/file/91f18a1287b398d378ef22505bf41832-Paper-Datasets_and_Benchmarks.pdf), NeurIPS 2023, peer-reviewed. | Real outputs from multiple model families evaluated against expert preferences on fixed multi-turn prompts and crowd preferences from live Arena interactions. In one MT-Bench setup excluding ties, GPT-4 agreed with experts 85% of the time and experts agreed with each other 81% of the time. Swapping answer order exposed position bias. | The outcome is preference agreement under a specific protocol. Use source-grounded checks as the primary verifier. If a model judge is used for secondary analysis, blind it to condition and swap answer order. |

## Proposed audit

**Question.** Can typed, multiscale compaction preserve an authorized correction and a later revocation across Gemini and GPT?

1. Freeze 20 synthetic research traces, prompts, and answer keys and record their SHA-256 hashes. Give each trace an initial claim, a later authorized correction, a revocation, an unauthorized contradiction, stable source IDs, and a neutral follow-up at each checkpoint. Reserve full evidence for the uncompressed control and verification. Keep the answer key outside model inputs.
2. Run four conditions on pinned Gemini and GPT API versions, with three fresh sessions per trace and condition. Compare full history, a generic metadata summary, typed object records plus a session summary, and the same typed representation with the explicit correction link removed while its meaning remains in prose. Match input facts and token budgets across compacted conditions, force compaction after the correction and revocation, randomize the run order, and log model versions, settings, and exact payloads. Feed the neutral follow-up before requesting each checkpoint answer. Use the full-history arm to check whether each model can solve the fixture with all evidence available.
3. At both checkpoints require structured fields for the current claim and status, authorizing source ID, evidence ID, permitted action, and correction or revocation ID. Compare each field against the frozen key. These fields implement Semantic, Authority, Visibility, Enforceability, and Retention (SAVER) checks for this fixture. A session passes only when every required field matches at both checkpoints. Keep verification outside generation and selection, consistent with evaluator non-sovereignty \(h < 1\).
4. Average the three session results within each trace and report paired effects by model, resampling traces for 95% confidence intervals. The proposed pilot criterion is a gain of at least 10 percentage points over each compacted control on each model, with every corresponding interval excluding zero in the positive direction. Report unresolved checks and failures by field and checkpoint.

**Status.** The targeted retrieval check passed. The proposed audit would yield live-model results on synthetic traces. Results for the public-search mechanism would require a separate web experiment with verified indexing and retrieval.
