# AIce-Tiny-v0 model card

Love Labs LCA · AIce · 2026-10-15 · EXPERIMENTAL; efficacy OPEN.

`aice-tiny-v0.npz` contains 44,290 learned parameters, initialized from seed 7
and trained for 1,200 Adam updates on the included 4,041-byte synthetic
teaching corpus. It uses two decoder blocks, width 32, four attention heads,
a 64-token context, and a 258-token UTF-8 byte vocabulary. Each ordinary token
is one byte. No pretrained weights or outside model services are used.

| Measurement, nats per next token | Initial | Final |
| --- | ---: | ---: |
| Training text loss | 5.548650 | 1.476211 |
| Separate in-domain evaluation loss | 5.549118 | 2.428215 |

The sidecar `aice-tiny-v0.npz.json` holds the full configuration, file digests,
training history and measured losses. These are development measurements on
very small texts with shared subject matter, not independent evidence of
general competence. Free-text continuations are often malformed, repetitive,
or incorrect. Do not treat them as faithful retrieval of the study or as
instructions to execute. The model has no private-state access or connection
to the GPT conversation.

## Larger candidate: recorded negative result

A second fresh model used width 64, context 128, four heads and two blocks:
141,570 parameters and 4,000 updates on the same corpus. Its training loss
fell from 5.551956 to 0.179894 while evaluation loss fell only from 5.552168
to 5.437068. It reproduced teaching sentences more fluently but generalized
substantially worse than the selected smaller model on this evaluation text.
This is a strong overfitting signal. Its receipt is preserved at
`experiments/aice-141k-overfit.json`; its weights are not distributed here.
No broad capability claim follows from either run.

## Intended use

Inspect and change a complete transformer implementation; run local
training experiments; measure next-token learning; connect a queryable
neural candidate ranker to the existing structured custody harness.
The structured demo's readable state responses come from fixed host handlers,
not learned free-text answers. Its gate evaluates the supplied code predicates,
not the truth or meaning of arbitrary language. KakeyaLogic's implemented role
is lineage/custody at the dispatch boundary; neural attention is conventional.

## Run

```bash
python -m pip install -e '.[model]'
python -m aice_model query --checkpoint models/aice-tiny-v0.npz --prompt 'AIce is' --temperature 0
python examples/query_aice.py --checkpoint models/aice-tiny-v0.npz
```

The second command starts the persistent JSON-lines interface; send JSON
requests on stdin as described in `docs/AICE-MODEL-001.md`. For more useful
language behavior, the next development work is a substantially broader,
permissioned corpus, better tokenization/context choices, and explicit
evaluation tasks. More updates on the same tiny text can increase memorization.
