"""Small reverse-mode autodiff engine; all numerical work uses NumPy.

Each operation records a vector-Jacobian product. backward() visits the
operation graph in reverse order and accumulates parameter gradients.
"""

import numpy as np


def unbroadcast(grad, shape):
    while grad.ndim > len(shape):
        grad = grad.sum(axis=0)
    for axis, size in enumerate(shape):
        if size == 1:
            grad = grad.sum(axis=axis, keepdims=True)
    return grad.reshape(shape)


class Tensor:
    def __init__(self, data, requires_grad=False, parents=(), backward=None):
        self.data = np.asarray(data, dtype=np.float64)
        self.requires_grad = requires_grad
        self.grad = None
        self.parents = parents if requires_grad else ()
        self._backward = backward if requires_grad else None

    def accumulate(self, grad):
        if self.requires_grad:
            self.grad = grad.copy() if self.grad is None else self.grad + grad

    def backward(self):
        if self.data.size != 1 or not self.requires_grad:
            raise ValueError("backward requires a differentiable scalar")
        ordered, seen = [], set()

        def visit(node):
            if id(node) in seen:
                return
            seen.add(id(node))
            for parent in node.parents:
                visit(parent)
            ordered.append(node)

        visit(self)
        # Repeated backward calls start a fresh gradient computation.
        for node in ordered:
            node.grad = None
        self.grad = np.ones_like(self.data)
        for node in reversed(ordered):
            if node._backward is not None and node.grad is not None:
                node._backward(node.grad)

    def __add__(self, other):
        other = as_tensor(other)

        def backward(grad):
            self.accumulate(unbroadcast(grad, self.data.shape))
            other.accumulate(unbroadcast(grad, other.data.shape))

        return Tensor(self.data + other.data,
                      self.requires_grad or other.requires_grad, (self, other), backward)

    __radd__ = __add__

    def __neg__(self):
        return self * -1

    def __sub__(self, other):
        return self + -as_tensor(other)

    def __rsub__(self, other):
        return as_tensor(other) + -self

    def __mul__(self, other):
        other = as_tensor(other)

        def backward(grad):
            self.accumulate(unbroadcast(grad * other.data, self.data.shape))
            other.accumulate(unbroadcast(grad * self.data, other.data.shape))

        return Tensor(self.data * other.data,
                      self.requires_grad or other.requires_grad, (self, other), backward)

    __rmul__ = __mul__

    def __truediv__(self, other):
        return self * as_tensor(other) ** -1

    def __pow__(self, exponent):
        return Tensor(self.data ** exponent, self.requires_grad, (self,),
                      lambda grad: self.accumulate(grad * exponent * self.data ** (exponent - 1)))

    def __matmul__(self, other):
        other = as_tensor(other)
        if self.data.ndim < 2 or other.data.ndim < 2:
            raise ValueError("matmul expects matrices or batches of matrices")

        def backward(grad):
            self.accumulate(unbroadcast(grad @ np.swapaxes(other.data, -1, -2), self.data.shape))
            other.accumulate(unbroadcast(np.swapaxes(self.data, -1, -2) @ grad, other.data.shape))

        return Tensor(self.data @ other.data,
                      self.requires_grad or other.requires_grad, (self, other), backward)

    def reshape(self, *shape):
        return Tensor(self.data.reshape(*shape), self.requires_grad, (self,),
                      lambda grad: self.accumulate(grad.reshape(self.data.shape)))

    def transpose(self, *axes):
        if not axes:
            axes = tuple(reversed(range(self.data.ndim)))
        axes = tuple(axis % self.data.ndim for axis in axes)
        return Tensor(self.data.transpose(axes), self.requires_grad, (self,),
                      lambda grad: self.accumulate(grad.transpose(np.argsort(axes))))

    def sum(self, axis=None, keepdims=False):
        def backward(grad):
            if axis is not None and not keepdims:
                grad = np.expand_dims(grad, axis)
            self.accumulate(np.broadcast_to(grad, self.data.shape))

        return Tensor(self.data.sum(axis=axis, keepdims=keepdims),
                      self.requires_grad, (self,), backward)

    def mean(self, axis=None, keepdims=False):
        count = self.data.size if axis is None else self.data.shape[axis]
        return self.sum(axis, keepdims) / count

    def exp(self):
        value = np.exp(self.data)
        return Tensor(value, self.requires_grad, (self,),
                      lambda grad: self.accumulate(grad * value))

    def log(self):
        return Tensor(np.log(self.data), self.requires_grad, (self,),
                      lambda grad: self.accumulate(grad / self.data))

    def tanh(self):
        value = np.tanh(self.data)
        return Tensor(value, self.requires_grad, (self,),
                      lambda grad: self.accumulate(grad * (1 - value * value)))

    def __getitem__(self, index):
        def backward(grad):
            full = np.zeros_like(self.data)
            np.add.at(full, index, grad)  # repeated token IDs accumulate
            self.accumulate(full)

        return Tensor(self.data[index], self.requires_grad, (self,), backward)


def as_tensor(value):
    return value if isinstance(value, Tensor) else Tensor(value)


def softmax(value):
    shifted = value - value.data.max(axis=-1, keepdims=True)
    exponentials = shifted.exp()
    return exponentials / exponentials.sum(axis=-1, keepdims=True)


def cross_entropy(logits, targets):
    """Stable next-token negative log likelihood, averaged over batch/time."""
    flat = logits.reshape(-1, logits.data.shape[-1])
    labels = np.asarray(targets).reshape(-1)
    shifted = flat - flat.data.max(axis=-1, keepdims=True)
    log_partition = shifted.exp().sum(axis=-1).log()
    selected = shifted[np.arange(len(labels)), labels]
    return (log_partition - selected).mean()


class Adam:
    def __init__(self, parameters, learning_rate=0.003):
        if not np.isfinite(learning_rate) or learning_rate <= 0:
            raise ValueError("learning rate must be finite and positive")
        self.parameters = parameters
        self.learning_rate = learning_rate
        self.step_count = 0
        self.first = {key: np.zeros_like(p.data) for key, p in parameters.items()}
        self.second = {key: np.zeros_like(p.data) for key, p in parameters.items()}

    def step(self, max_norm=1.0):
        grads = [p.grad for p in self.parameters.values() if p.grad is not None]
        if any(not np.isfinite(g).all() for g in grads):
            raise FloatingPointError("non-finite gradient; weights unchanged")
        norm = np.sqrt(sum(float((g * g).sum()) for g in grads))
        scale = min(1.0, max_norm / (norm + 1e-12))
        self.step_count += 1
        for key, parameter in self.parameters.items():
            if parameter.grad is None:
                continue
            grad = parameter.grad * scale
            self.first[key] = 0.9 * self.first[key] + 0.1 * grad
            self.second[key] = 0.999 * self.second[key] + 0.001 * grad * grad
            first = self.first[key] / (1 - 0.9 ** self.step_count)
            second = self.second[key] / (1 - 0.999 ** self.step_count)
            parameter.data -= self.learning_rate * first / (np.sqrt(second) + 1e-8)
