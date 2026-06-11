from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def make_windows(values: np.ndarray, window_size: int) -> np.ndarray:
    if len(values) < window_size:
        raise ValueError("not enough rows for the requested window size")
    windows = [values[i : i + window_size].reshape(-1) for i in range(len(values) - window_size + 1)]
    return np.asarray(windows, dtype=np.float64)


@dataclass
class Standardizer:
    mean: np.ndarray
    std: np.ndarray

    @classmethod
    def fit(cls, values: np.ndarray) -> "Standardizer":
        mean = values.mean(axis=0)
        std = values.std(axis=0)
        std[std < 1e-8] = 1.0
        return cls(mean, std)

    def transform(self, values: np.ndarray) -> np.ndarray:
        return (values - self.mean) / self.std


class USADNumpy:
    """A dependency-light USAD reproduction with one encoder and two decoders.

    The implementation keeps the USAD structure used in the paper: a shared
    encoder and two reconstruction paths. It uses simple full-batch NumPy
    backpropagation so the project can run without PyTorch.
    """

    def __init__(self, input_dim: int, latent_dim: int = 12, lr: float = 1e-3, seed: int = 7):
        rng = np.random.default_rng(seed)
        scale = 0.08
        self.we = rng.normal(0, scale, (input_dim, latent_dim))
        self.be = np.zeros(latent_dim)
        self.wd1 = rng.normal(0, scale, (latent_dim, input_dim))
        self.bd1 = np.zeros(input_dim)
        self.wd2 = rng.normal(0, scale, (latent_dim, input_dim))
        self.bd2 = np.zeros(input_dim)
        self.lr = lr

    def _encode(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        u = x @ self.we + self.be
        z = np.tanh(u)
        return u, z

    def _decode(self, z: np.ndarray, decoder: int) -> np.ndarray:
        if decoder == 1:
            return z @ self.wd1 + self.bd1
        return z @ self.wd2 + self.bd2

    def reconstruct(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        _, z = self._encode(x)
        return self._decode(z, 1), self._decode(z, 2)

    def _train_decoder(self, x: np.ndarray, decoder: int, weight: float = 1.0) -> float:
        _, z = self._encode(x)
        w = self._decode(z, decoder)
        err = w - x
        loss = float(np.mean(err**2))
        grad_y = weight * 2.0 * err / x.shape[0]

        if decoder == 1:
            grad_wd = z.T @ grad_y
            grad_bd = grad_y.sum(axis=0)
            grad_z = grad_y @ self.wd1.T
            self.wd1 -= self.lr * grad_wd
            self.bd1 -= self.lr * grad_bd
        else:
            grad_wd = z.T @ grad_y
            grad_bd = grad_y.sum(axis=0)
            grad_z = grad_y @ self.wd2.T
            self.wd2 -= self.lr * grad_wd
            self.bd2 -= self.lr * grad_bd

        grad_u = grad_z * (1.0 - z**2)
        self.we -= self.lr * (x.T @ grad_u)
        self.be -= self.lr * grad_u.sum(axis=0)
        return loss

    def fit(self, x_train: np.ndarray, epochs: int = 120) -> list[float]:
        history: list[float] = []
        for epoch in range(1, epochs + 1):
            # The first decoder learns a stable reconstruction. The second
            # decoder is trained with slightly increasing pressure to model
            # reconstruction disagreement, matching USAD's two-decoder idea.
            loss1 = self._train_decoder(x_train, decoder=1, weight=1.0)
            loss2 = self._train_decoder(x_train, decoder=2, weight=1.0 + epoch / epochs)
            history.append((loss1 + loss2) / 2.0)
        return history

    def score(self, x: np.ndarray, alpha: float = 0.5) -> np.ndarray:
        w1, w2 = self.reconstruct(x)
        e1 = np.mean((x - w1) ** 2, axis=1)
        e2 = np.mean((x - w2) ** 2, axis=1)
        return alpha * e1 + (1 - alpha) * e2
