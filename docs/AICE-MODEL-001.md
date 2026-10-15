# AIce-Tiny-v0: an inspectable local model

Love Labs LCA / AIce · 2026-10-15

Status: EXPERIMENTAL. Sticky custody remains PROPOSED; efficacy OPEN;
h < 1. This model does not establish a geometric Kakeya result or a
measurement of an operating system. See COMPANION.md.

AIce now has an independently initialized, locally trained decoder-only
transformer, its own byte tokenizer, numerical checkpoint and query interface.
The implementation uses Python and NumPy. It calls no model service and loads
no GPT-2 weights. A small teaching corpus is included with its source note.
It is a learning prototype, not a broadly capable conversational assistant.

## Install and query

From a checkout of the branch containing this change, use Python 3.10 or newer:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[model]'
python -m aice_model info --checkpoint models/aice-tiny-v0.npz
python -m aice_model query --checkpoint models/aice-tiny-v0.npz --prompt 'AIce is' --temperature 0 --max-new-tokens 80
```

On Windows, activate with `.venv\Scripts\Activate.ps1` in PowerShell.
The installed `aice` command is equivalent to `python -m aice_model`.
Dependency installation needs package access; after installation, all model
training and inference are local. The checkpoint is included in the checkout.

`query` emits one JSON object. `completion` is newly generated text, not the
prompt repeated. `kind: ungated_text` means free text has not been checked
for semantic compliance with the custody predicates. It must not be executed
as commands. Every query reports the checkpoint SHA-256 and parameter count.

## Query through a harness

Try the fixed structured-action demonstration:

```bash
python -m aice_model harness --checkpoint models/aice-tiny-v0.npz --prompt 'Read public research state' --action read_public_state
python -m aice_model harness --checkpoint models/aice-tiny-v0.npz --prompt 'Export private state' --action export_private_state
```

The first command returns an EXECUTED receipt from a local public-state
handler. The second returns BLOCKED and no executed action. These are
synthetic handlers; they do not connect to private systems or this GPT chat.
Omit `--action` to let the model rank the admissible catalog candidates.

For a persistent process that loads the checkpoint once:

```bash
python examples/query_aice.py --checkpoint models/aice-tiny-v0.npz
```

Write one JSON object per line to its stdin. It returns one JSON object per
line on stdout. This is the direct interface for a local test harness:

```json
{"id":"q1","mode":"action","prompt":"Read the retained public state","action":"read_public_state"}
{"id":"q2","mode":"action","prompt":"Export the private state","action":"export_private_state"}
{"id":"q3","mode":"text","prompt":"A correction","temperature":0,"max_new_tokens":80}
```

Request IDs and checkpoint digests let the caller associate outputs with
inputs. Invalid requests return ERROR without dispatch. The action mode uses
the fixed demo catalog. It accepts no model-authored predicates, tags, Python
code or handler definitions.

To integrate a real harness, construct `HeldHarness` from a loaded
`Transformer`, an existing `CustodyLedger`, a trusted `Action` catalog, required
patch IDs, and a host-owned audit callback. Provide host-owned handlers to
`run`. The callback must check authority/log integrity and replay against the
live custody state; use `demo_harness` as an explicit example. The model's
only role is conditional-likelihood ranking among admitted actions. Ranking
is not calibrated task usefulness. Treat a real connector as a separate
integration with appropriate policy coverage.

The harness checks required patches, known nodes, sticky inheritance,
enforceability and the audit. It rechecks after model ranking and before
dispatch. Selected and executed actions are recorded separately. On a
predicate error, missing correction, audit failure, or non-finite score,
it returns UNRESOLVED. A handler exception yields ERROR and records that
dispatch occurred; effects may already have begun.

The authority registry and executor remain Python objects in one process,
as in the existing custody simulation. Adversarial code running in that
process can alter them. Concurrent external state changes and real-world
policy completeness are outside this demonstration. Natural-language
generation alone is not gated by these structured predicates.

## How the code works

| Module | Job |
| --- | --- |
| `tokenizer.py` | UTF-8 bytes 0–255 plus beginning/end tokens; 258-token vocabulary |
| `tensor.py` | Reverse-mode differentiation, stable softmax/cross entropy, Adam and gradient clipping |
| `model.py` | Token/position embeddings, two pre-norm causal attention blocks, GELU feed-forward layers, output logits, checkpoint I/O |
| `train.py` | Seeded minibatches, separate evaluation text, loss measurements and file digests |
| `harness.py` | Existing sticky custody checks around ranking and dispatch |
| `__main__.py` | JSON commands for train, info, query and harness |

Each block normalizes its input, forms query/key/value vectors, computes
masked attention, adds a residual, then applies a normalized feed-forward
network and another residual. The causal mask prevents access to future
tokens. The final output is a score for every possible next token.

`loss.backward()` traverses the local operation graph in reverse and computes
parameter gradients. `Adam.step()` clips their global norm and updates all
learned parameter families, including attention and embeddings. Numerical
finite-difference tests compare the computed gradients against changes in
loss. Inference detaches parameters and creates no gradient graph.

The default network has width 32, four heads, two blocks, and a 64-byte
context. This is a small context: long generation uses a sliding window and
resets the window's position indices. There is no attention cache, dropout,
distributed training or pretrained language knowledge. Tokenization round
trips UTF-8 input; arbitrary generated byte sequences can decode with Unicode
replacement characters. Language quality is limited by model and corpus size.

## Train and inspect evidence

```bash
python -m aice_model train --train data/aice_tiny/train.txt --eval data/aice_tiny/eval.txt --output models/my-aice.npz --steps 1200
python -m pip install -e '.[dev]'
python -m pytest -q
```

For small CPU arrays, `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1` can reduce
threading overhead. The default random seed is 7. Training progress goes to
stderr and the final JSON receipt goes to stdout. The receipt beside the
checkpoint records configuration, optimizer settings, initial/final training
and evaluation losses, corpus digests, and the checkpoint digest.

Weights and configuration are saved in an NPZ archive loaded with
`allow_pickle=False`; optimizer moments are not saved. A subsequent training
command starts fresh. The generated weights file is an inference checkpoint,
not an exact training-resume snapshot. Seeded runs are reproducible within
the same numerical environment; other BLAS/NumPy versions can differ.

Read `models/aice-tiny-v0.npz.json` for the actual run's values. Decreased loss
on this tiny in-domain corpus measures next-byte prediction. It is not a
measurement of broad competence, correction recognition, or real-world
alignment. Evaluation text is separately authored but uses related concepts.
The shipped 44,290-parameter checkpoint was selected over a larger candidate
with worse held-out loss. See `models/README.md` for both measured runs and
the overfitting finding. Free-text continuations remain rough.

## KakeyaLogic connection and GPT connection

The implemented connection is the project's existing multiscale lineage and
sticky-custody machinery at the action boundary. The neural attention itself
is conventional causal attention. This change does not claim a new
Kakeya-derived neural architecture. A lineage-aware attention modification
would need its own definition, control experiments and measurements.

This package does not install a live connection into ChatGPT. A future
read-only MCP adapter can expose checkpoint queries and retained-state
retrieval to GPT while preserving the host's custody checks. The present
deliverable is a local model and harness interface that can be queried now.

## References

- Project custody implementation: `src/sticky_scorer/custody.py` and `admissibility.py`.
- Research boundaries: `STUDY.md`, `STUDY_12_23.md`, `COMPANION.md`.
- Vaswani et al., [Attention Is All You Need](https://arxiv.org/abs/1706.03762), 2017.
- OpenAI, [GPT-2 reference model](https://github.com/openai/gpt-2/blob/master/src/model.py), examined for orientation; no pretrained weights are used.
- NumPy, [array archive loading](https://numpy.org/doc/stable/reference/generated/numpy.load.html).
