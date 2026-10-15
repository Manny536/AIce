"""Decoder-only transformer: embeddings, causal attention, GELU MLP, logits.

Built from NumPy operations and the local autodiff engine. No TensorFlow,
PyTorch, pretrained weights, network access, or model-service calls.
"""

from dataclasses import asdict, dataclass
import json
from pathlib import Path

import numpy as np

from .tensor import Tensor, cross_entropy, softmax
from .tokenizer import ByteTokenizer


@dataclass(frozen=True)
class Config:
    context: int = 64
    width: int = 32
    heads: int = 4
    layers: int = 2
    seed: int = 7

    def __post_init__(self):
        if any(type(n) is not int or n <= 0 for n in
               (self.context, self.width, self.heads, self.layers)):
            raise ValueError("model dimensions must be positive integers")
        if self.width % self.heads:
            raise ValueError("width must be divisible by heads")


class Transformer:
    def __init__(self, config=Config()):
        self.config = config
        self.parameters = {}
        rng = np.random.default_rng(config.seed)
        width = config.width

        def weight(name, shape, scale=0.02):
            self.parameters[name] = Tensor(rng.normal(0, scale, shape), True)

        def norm_parameters(name):
            self.parameters[name + ".g"] = Tensor(np.ones(width), True)
            self.parameters[name + ".b"] = Tensor(np.zeros(width), True)

        def linear_parameters(name, incoming, outgoing):
            weight(name + ".w", (incoming, outgoing))
            self.parameters[name + ".b"] = Tensor(np.zeros(outgoing), True)

        weight("token", (ByteTokenizer.vocab_size, width))
        weight("position", (config.context, width))
        for layer in range(config.layers):
            root = f"block.{layer}"
            norm_parameters(root + ".ln1")
            norm_parameters(root + ".ln2")
            for projection in ("q", "k", "v", "out"):
                linear_parameters(root + "." + projection, width, width)
            linear_parameters(root + ".fc", width, 4 * width)
            linear_parameters(root + ".proj", 4 * width, width)
        norm_parameters("final")
        linear_parameters("head", width, ByteTokenizer.vocab_size)

    @property
    def parameter_count(self):
        return sum(p.data.size for p in self.parameters.values())

    def forward(self, ids, *, training=False):
        ids = np.asarray(ids)
        if ids.ndim != 2 or ids.shape[0] < 1 or not 0 < ids.shape[1] <= self.config.context:
            raise ValueError("tokens must have shape [batch, time] within context")
        if ids.dtype.kind not in "iu" or np.any(ids < 0) or np.any(ids >= ByteTokenizer.vocab_size):
            raise ValueError("invalid token IDs")
        # Inference uses detached views, so it builds no autodiff graph.
        p = self.parameters if training else {k: Tensor(v.data) for k, v in self.parameters.items()}
        batch, time = ids.shape
        width, heads = self.config.width, self.config.heads

        def linear(value, name):
            return value @ p[name + ".w"] + p[name + ".b"]

        def norm(value, name):
            centered = value - value.mean(axis=-1, keepdims=True)
            return centered * ((centered * centered).mean(axis=-1, keepdims=True) + 1e-5) ** -0.5 * p[name + ".g"] + p[name + ".b"]

        value = p["token"][ids] + p["position"][np.arange(time)]
        causal_mask = np.where(np.tril(np.ones((time, time), dtype=bool)), 0.0, -np.inf)
        for layer in range(self.config.layers):
            root = f"block.{layer}"
            normalized = norm(value, root + ".ln1")
            query, key, content = [linear(normalized, root + "." + name)
                                   .reshape(batch, time, heads, width // heads)
                                   .transpose(0, 2, 1, 3) for name in ("q", "k", "v")]
            scores = query @ key.transpose(0, 1, 3, 2) / np.sqrt(width // heads)
            attended = (softmax(scores + causal_mask) @ content)
            attended = attended.transpose(0, 2, 1, 3).reshape(batch, time, width)
            value = value + linear(attended, root + ".out")
            hidden = linear(norm(value, root + ".ln2"), root + ".fc")
            activated = 0.5 * hidden * (1 + (np.sqrt(2 / np.pi) * (hidden + 0.044715 * hidden ** 3)).tanh())
            value = value + linear(activated, root + ".proj")
        return linear(norm(value, "final"), "head")

    def loss(self, inputs, targets, *, training=False):
        if np.shape(inputs) != np.shape(targets):
            raise ValueError("inputs and targets must have identical shapes")
        return cross_entropy(self.forward(inputs, training=training), targets)

    def generate(self, prompt, *, max_new_tokens=80, temperature=0.7, seed=7):
        if max_new_tokens < 0 or not np.isfinite(temperature) or temperature < 0:
            raise ValueError("invalid generation settings")
        tokenizer = ByteTokenizer()
        tokens = tokenizer.encode(prompt)
        generated = []
        rng = np.random.default_rng(seed)
        for _ in range(max_new_tokens):
            logits = self.forward([tokens[-self.config.context:]]).data[0, -1].copy()
            logits[tokenizer.bos] = -np.inf
            if temperature == 0:
                next_id = int(logits.argmax())
            else:
                logits = logits / temperature
                probabilities = np.exp(logits - logits.max())
                probabilities /= probabilities.sum()
                next_id = int(rng.choice(tokenizer.vocab_size, p=probabilities))
            if next_id == tokenizer.eos:
                break
            tokens.append(next_id)
            generated.append(next_id)
        return tokenizer.decode(generated)

    def score(self, prompt, completion):
        """Mean conditional log probability over completion bytes, including long prompts."""
        tokenizer = ByteTokenizer()
        history = tokenizer.encode(prompt)
        targets = tokenizer.encode(completion, bos=False, eos=True)
        scores = []
        for target in targets:
            logits = self.forward([history[-self.config.context:]]).data[0, -1]
            shifted = logits - logits.max()
            scores.append(float(shifted[target] - np.log(np.exp(shifted).sum())))
            history.append(target)
        return float(np.mean(scores))

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        metadata = {"format": "aice-numpy-v1", "config": asdict(self.config),
                    "tokenizer": ByteTokenizer.name}
        # File handle avoids NumPy silently appending an extension.
        with path.open("wb") as handle:
            np.savez_compressed(handle, metadata=np.array(json.dumps(metadata)),
                                **{k: v.data for k, v in self.parameters.items()})

    @classmethod
    def load(cls, path):
        with np.load(path, allow_pickle=False) as checkpoint:
            metadata = json.loads(str(checkpoint["metadata"]))
            if metadata["format"] != "aice-numpy-v1" or metadata["tokenizer"] != ByteTokenizer.name:
                raise ValueError("unsupported checkpoint format or tokenizer")
            model = cls(Config(**metadata["config"]))
            if set(checkpoint.files) != set(model.parameters) | {"metadata"}:
                raise ValueError("checkpoint parameter set mismatch")
            for name, parameter in model.parameters.items():
                values = checkpoint[name]
                if values.shape != parameter.data.shape or not np.isfinite(values).all():
                    raise ValueError(f"invalid checkpoint parameter: {name}")
                parameter.data[...] = values
        return model
