"""Reproducible fresh training and held-out loss measurement."""

from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import numpy as np

from .model import Config, Transformer
from .tensor import Adam
from .tokenizer import ByteTokenizer


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_tokens(path):
    return np.array(ByteTokenizer().encode(Path(path).read_text(encoding="utf-8"), eos=True), dtype=np.int64)


def evaluate(model, tokens):
    total, count = 0.0, 0
    for start in range(0, len(tokens) - 1, model.config.context):
        window = tokens[start:start + model.config.context + 1]
        loss = model.loss(window[None, :-1], window[None, 1:])
        total += float(loss.data) * (len(window) - 1)
        count += len(window) - 1
    if not count:
        raise ValueError("evaluation text is empty")
    return total / count


def train(train_path, eval_path, output, *, config=Config(), steps=600,
          batch_size=4, learning_rate=0.003, progress=None):
    if steps < 1 or batch_size < 1:
        raise ValueError("steps and batch size must be positive")
    train_tokens, eval_tokens = read_tokens(train_path), read_tokens(eval_path)
    if len(train_tokens) <= config.context:
        raise ValueError("training text must be longer than context")
    if sha256(train_path) == sha256(eval_path):
        raise ValueError("training and evaluation files must differ")
    model = Transformer(config)
    optimizer = Adam(model.parameters, learning_rate)
    rng = np.random.default_rng(config.seed + 1)
    receipt = {
        "model": "AIce-Tiny-v0", "status": "EXPERIMENTAL; efficacy OPEN",
        "config": asdict(config), "parameters": model.parameter_count,
        "steps": steps, "batch_size": batch_size, "learning_rate": learning_rate,
        "numpy_version": np.__version__, "tokenizer": ByteTokenizer.name,
        "loss_unit": "nats_per_next_token",
        "train_sha256": sha256(train_path), "eval_sha256": sha256(eval_path),
        "train_bytes": Path(train_path).stat().st_size, "eval_bytes": Path(eval_path).stat().st_size,
        "initial_train_loss": evaluate(model, train_tokens),
        "initial_eval_loss": evaluate(model, eval_tokens),
        "history": [],
    }
    for step in range(1, steps + 1):
        starts = rng.integers(0, len(train_tokens) - config.context, size=batch_size)
        windows = np.stack([train_tokens[s:s + config.context + 1] for s in starts])
        loss = model.loss(windows[:, :-1], windows[:, 1:], training=True)
        loss.backward()
        optimizer.step()
        if step == 1 or step % 100 == 0 or step == steps:
            item = {"step": step, "batch_loss": float(loss.data)}
            receipt["history"].append(item)
            if progress:
                progress(item)
    receipt["final_train_loss"] = evaluate(model, train_tokens)
    receipt["final_eval_loss"] = evaluate(model, eval_tokens)
    model.save(output)
    receipt["checkpoint_sha256"] = sha256(output)
    receipt["optimizer_state_saved"] = False
    Path(str(output) + ".json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return model, receipt
