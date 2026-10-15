# AIce tiny corpus

These two text files were authored for the AIce-Tiny-v0 implementation on
2026-10-15, based on the project's public vocabulary and the owner's request.
They are synthetic teaching material, not collected human interactions,
empirical incident records, private user data, or a GPT-2 dataset.

`train.txt` is used for gradient updates; `eval.txt` is separately authored
and used only for loss reporting. The evaluation is in-domain, small, and
shares vocabulary and ideas with training. It is not an independent test
of broad generalization or operational custody effectiveness.

The receipt records SHA-256 digests of both files. No corpus content is
silently fetched at training or inference time. Read STUDY.md and
COMPANION.md for research definitions; this teaching corpus is not their
replacement. All outputs remain experimental; efficacy OPEN.
