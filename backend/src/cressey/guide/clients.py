"""Model adapters behind Protocols. Models only read and label; code decides."""

from typing import Protocol

import numpy as np


class ModelUnavailable(Exception):
    """A model call failed (SDK error, timeout, 429 after retries, missing key, cache miss in replay)."""


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> np.ndarray:
        """Rows L2-normalized, shape (len(texts), dim)."""
        ...
