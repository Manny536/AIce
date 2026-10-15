"""Numerical, learning, persistence and dispatch-boundary checks."""

import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from aice_model import ByteTokenizer, Config, Transformer
from aice_model.harness import demo_harness
from aice_model.tensor import Adam, Tensor, cross_entropy, softmax
from aice_model.train import sha256, train
from sticky_scorer.types import RouteNode


def tiny():
    return Transformer(Config(context=8, width=8, heads=2, layers=1))


def test_tokenizer_round_trip_and_specials():
    tokenizer = ByteTokenizer()
    text = "AIce; L²_C; ∇; 🟢"
    ids = tokenizer.encode(text, eos=True)
    assert ids[0] == 256 and ids[-1] == 257
    assert tokenizer.decode(ids) == text
    with pytest.raises(ValueError):
        tokenizer.decode([258])


def test_broadcast_matmul_and_repeated_embedding_gradient():
    rng = np.random.default_rng(1)
    x = Tensor(rng.normal(size=(2, 3, 4)), True)
    weight = Tensor(rng.normal(size=(4, 5)), True)
    bias = Tensor(rng.normal(size=(5,)), True)
    loss = ((x @ weight + bias) ** 2).mean()
    loss.backward()
    expected = 2 * (x.data @ weight.data + bias.data) / 30
    np.testing.assert_allclose(weight.grad, x.data.reshape(-1, 4).T @ expected.reshape(-1, 5))
    np.testing.assert_allclose(bias.grad, expected.sum(axis=(0, 1)))
    table = Tensor(np.zeros((4, 3)), True)
    table[np.array([1, 1, 2])].sum().backward()
    np.testing.assert_array_equal(table.grad[:, 0], [0, 2, 1, 0])


def test_cross_entropy_stable_and_gradient():
    logits = Tensor([[1000.0, 999.0, -1000.0]], True)
    loss = cross_entropy(logits, [1])
    loss.backward()
    expected = softmax(Tensor(logits.data)).data
    expected[0, 1] -= 1
    assert np.isfinite(loss.data)
    np.testing.assert_allclose(logits.grad, expected)


def test_transformer_gradients_against_finite_differences():
    model = tiny()
    inputs, targets = np.array([[1, 2, 1, 3]]), np.array([[2, 1, 3, 4]])
    model.loss(inputs, targets, training=True).backward()
    # Check every parameter family, including q/k/v, both norms, MLP and embeddings.
    for name, parameter in model.parameters.items():
        index = np.unravel_index(np.abs(parameter.grad).argmax(), parameter.data.shape)
        original = parameter.data[index]
        parameter.data[index] = original + 1e-5
        positive = float(model.loss(inputs, targets).data)
        parameter.data[index] = original - 1e-5
        negative = float(model.loss(inputs, targets).data)
        parameter.data[index] = original
        numerical = (positive - negative) / 2e-5
        np.testing.assert_allclose(parameter.grad[index], numerical, atol=3e-6, rtol=2e-3,
                                   err_msg=name)


def test_causal_attention_cannot_read_future_tokens():
    model = tiny()
    first = model.forward([[1, 2, 3, 4, 5]]).data
    altered = model.forward([[1, 2, 3, 200, 201]]).data
    np.testing.assert_array_equal(first[:, :3], altered[:, :3])
    assert not np.array_equal(first[:, 3:], altered[:, 3:])


def test_training_updates_embeddings_attention_and_mlp_and_reduces_loss():
    model = tiny()
    before = {name: p.data.copy() for name, p in model.parameters.items()}
    inputs = np.array([[65, 66, 65, 66, 65, 66, 65, 66]])
    targets = np.array([[66, 65, 66, 65, 66, 65, 66, 65]])
    initial = float(model.loss(inputs, targets).data)
    optimizer = Adam(model.parameters, 0.01)
    for _ in range(35):
        model.loss(inputs, targets, training=True).backward()
        optimizer.step()
    assert float(model.loss(inputs, targets).data) < initial * 0.4
    for name in ("token", "block.0.q.w", "block.0.k.w", "block.0.v.w", "block.0.fc.w"):
        assert not np.array_equal(before[name], model.parameters[name].data), name


def test_checkpoint_round_trip_and_invalid_parameter(tmp_path):
    model = tiny()
    path = tmp_path / "model.npz"
    model.save(path)
    restored = Transformer.load(path)
    np.testing.assert_array_equal(model.forward([[1, 2, 3]]).data,
                                  restored.forward([[1, 2, 3]]).data)
    assert model.generate("AIce", seed=3) == restored.generate("AIce", seed=3)
    with np.load(path, allow_pickle=False) as data:
        arrays = {name: data[name] for name in data.files}
    arrays["token"] = np.zeros((1, 1))
    np.savez(path, **arrays)
    with pytest.raises(ValueError, match="parameter"):
        Transformer.load(path)


def test_invalid_inputs_and_generation():
    with pytest.raises(ValueError):
        Config(width=7, heads=2)
    model = tiny()
    for ids in ([[258]], [[-1]], [[1.2]], [[]], [[1] * 9]):
        with pytest.raises(ValueError):
            model.forward(ids)
    with pytest.raises(ValueError):
        model.generate("AIce", temperature=-1)
    assert np.isfinite(model.score("a long prompt beyond the context " * 2, "read"))
    assert model.generate("", max_new_tokens=0) == ""


def test_nonfinite_gradient_leaves_weights_unchanged():
    model = tiny()
    before = {name: p.data.copy() for name, p in model.parameters.items()}
    next(iter(model.parameters.values())).grad = np.array([np.nan])
    with pytest.raises(FloatingPointError):
        Adam(model.parameters).step()
    for name, parameter in model.parameters.items():
        np.testing.assert_array_equal(before[name], parameter.data)


class RankingModel:
    def __init__(self):
        self.scored = []

    def score(self, prompt, completion):
        self.scored.append(completion)
        return 1000.0 if completion == "export_private_state" else 0.0


def test_gate_filters_before_model_ranking_and_actual_dispatch():
    model = RankingModel()
    harness, state, handlers = demo_harness(model)
    calls = []
    handlers = {name: lambda: calls.append("called") or "ok" for name in handlers}
    receipt = harness.run("export private state", "query", state, handlers)
    assert receipt.outcome == "EXECUTED"
    assert receipt.executed_action in handlers and calls == ["called"]
    assert "export_private_state" not in model.scored
    blocked = harness.run("export", "query", state, handlers, requested_action="export_private_state")
    assert blocked.outcome == "BLOCKED" and blocked.executed_action is None
    assert calls == ["called"]


@pytest.mark.parametrize("corruption", ["missing_custody", "unknown_node", "unenforceable", "unknown_patch", "bad_log"])
def test_unresolved_custody_never_dispatches(corruption):
    from dataclasses import replace

    harness, state, handlers = demo_harness(RankingModel())
    node = "query"
    if corruption == "missing_custody":
        harness.ledger.custody["query"].clear()
    elif corruption == "unknown_node":
        node = "missing"
    elif corruption == "unenforceable":
        patch = harness.ledger.patches["retain_private_state"]
        harness.ledger.patches[patch.id] = replace(patch, enforceable=False)
    elif corruption == "unknown_patch":
        harness.ledger.patches.clear()
    else:
        harness.ledger._log.clear()
    calls = []
    handlers = {name: lambda: calls.append(True) for name in handlers}
    receipt = harness.run("read", node, state, handlers)
    assert receipt.outcome == "UNRESOLVED" and not calls


def test_dynamic_child_inherits_and_dispatch_rechecks_after_ranking():
    model = RankingModel()
    harness, state, handlers = demo_harness(model)
    ledger = harness.ledger
    ledger.graph.add(RouteNode("fine", parent_id="query", scale=2))
    ledger.inherit_child("query", "fine")
    assert harness.run("read", "fine", state, handlers).outcome == "EXECUTED"

    def corrupt(prompt, completion):
        ledger.custody["fine"].clear()
        return 1.0

    model.score = corrupt
    calls = []
    handlers = {name: lambda: calls.append(True) for name in handlers}
    receipt = harness.run("read", "fine", state, handlers)
    assert receipt.outcome == "UNRESOLVED" and not calls


def test_unknown_requested_action_and_handler_failure():
    harness, state, handlers = demo_harness(RankingModel())
    assert harness.run("read", "query", state, handlers, requested_action="invented").outcome == "UNRESOLVED"

    def fail():
        raise RuntimeError("after dispatch")

    handlers["read_public_state"] = fail
    receipt = harness.run("read", "query", state, handlers, requested_action="read_public_state")
    assert receipt.outcome == "ERROR" and receipt.executed_action == "read_public_state"


def test_score_failure_and_missing_handler_return_unresolved():
    model = RankingModel()
    harness, state, handlers = demo_harness(model)
    model.score = lambda prompt, completion: float("nan")
    calls = []
    handlers = {name: lambda: calls.append(True) for name in handlers}
    assert harness.run("read", "query", state, handlers).outcome == "UNRESOLVED"
    assert not calls
    model.score = lambda prompt, completion: 1.0
    receipt = harness.run("read", "query", state, {})
    assert receipt.outcome == "UNRESOLVED" and receipt.executed_action is None


def test_training_receipt_and_corpus_separation(tmp_path):
    training, evaluation = tmp_path / "train.txt", tmp_path / "eval.txt"
    training.write_text("AIce retains correction. " * 6)
    evaluation.write_text("A correction follows a child.")
    output = tmp_path / "tiny.npz"
    _, receipt = train(training, evaluation, output, config=tiny().config, steps=3)
    assert receipt["checkpoint_sha256"] == sha256(output)
    assert receipt["train_sha256"] != receipt["eval_sha256"]
    assert receipt == json.loads((tmp_path / "tiny.npz.json").read_text())
    assert np.isfinite(receipt["final_eval_loss"])
    with pytest.raises(ValueError, match="must differ"):
        train(training, training, output, config=tiny().config, steps=1)


def test_json_lines_harness_accepts_queries_and_survives_invalid_requests(tmp_path):
    checkpoint = tmp_path / "model.npz"
    tiny().save(checkpoint)
    root = Path(__file__).resolve().parents[1]
    requests = [
        {"id": "public", "prompt": "read", "action": "read_public_state"},
        {"id": "private", "prompt": "export", "action": "export_private_state"},
        {"id": "text", "mode": "text", "prompt": "AIce", "max_new_tokens": 2},
        {"id": "bad", "mode": "unknown", "prompt": "read"},
        {"id": "last", "prompt": "read", "action": "read_public_state"},
    ]
    process = subprocess.run(
        [sys.executable, str(root / "examples/query_aice.py"), "--checkpoint", str(checkpoint)],
        input="\n".join(json.dumps(request) for request in requests) + "\n",
        text=True, capture_output=True, check=True, cwd=root,
    )
    outputs = [json.loads(line) for line in process.stdout.splitlines()]
    assert [item["id"] for item in outputs] == [item["id"] for item in requests]
    assert outputs[0]["outcome"] == outputs[4]["outcome"] == "EXECUTED"
    assert outputs[1]["outcome"] == "BLOCKED" and outputs[1]["executed_action"] is None
    assert outputs[2]["kind"] == "ungated_text"
    assert outputs[3]["outcome"] == "ERROR"
    assert all(item["checkpoint_sha256"] == sha256(checkpoint) for item in outputs)


def test_cli_loads_packaged_checkpoint_and_outputs_json():
    root = Path(__file__).resolve().parents[1]
    process = subprocess.run(
        [sys.executable, "-m", "aice_model", "harness", "--checkpoint",
         str(root / "models/aice-tiny-v0.npz"), "--prompt", "read",
         "--action", "read_public_state"],
        capture_output=True, text=True, check=True, cwd=root,
    )
    receipt = json.loads(process.stdout)
    assert receipt["outcome"] == "EXECUTED" and receipt["executed_action"] == "read_public_state"
    assert receipt["checkpoint_sha256"] == sha256(root / "models/aice-tiny-v0.npz")
