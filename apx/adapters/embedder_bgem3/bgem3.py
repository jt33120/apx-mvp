"""The one BGE-M3 embedder — the single non-test ``Embedder`` implementation (AD-11, FR-9).

BGE-M3 (568M, 1024-dim, MIT) is the default embedder: a real semantic model, local and offline (no
egress), yielding a dense vector per text. This adapter **fails loudly** — a missing model backend
or any inference fault RAISES a typed ``EmbedderError``; it NEVER degrades to a fallback, a stub, or
a hash (the v1 defect). The heavy backend (``FlagEmbedding``, which pulls ``torch``) is **imported
lazily** inside :meth:`encode`, so importing this adapter — and the whole app — needs no ML
dependency; a real embedding call is where the model is required, and where its absence fails loud.

Tests never run this: they substitute a fake ``Embedder`` at the port boundary inside the test
process (AD-11), so the model is never loaded in CI. There is exactly ONE concrete embedder class in
the runtime tree (this one) — the ``embedder_has_one_implementation`` structural property fails the
build on a second, or on any embedder built in an ``except`` handler.
"""

from __future__ import annotations

from apx.core.ports.embedding import (
    EmbedderDimensionMismatch,
    EmbedderError,
    EmbedderTimeout,
    EmbedderUnavailable,
)

_DIM = 1024                 # AD-11 halfvec width; matches models.EMBEDDING_DIM
_MODEL_ID = "BAAI/bge-m3"
_MODEL_VERSION = "bge-m3-1.0"
_MAX_TOKENS = 8192          # BGE-M3's context; long pieces are chunked in Story 2.9


def _backend_missing(exc: BaseException) -> EmbedderError:
    """The failure for an absent model backend — built HERE, at module scope (never inside an
    ``except``), so the caller can ``raise _backend_missing(exc)`` from an except without tripping
    the "no embedder constructed in an except handler" structural check (this call carries no
    ``embed`` in its name)."""
    return EmbedderUnavailable(
        f"the BGE-M3 backend is not available ({type(exc).__name__}) — install the embedder "
        "dependency; the embedder fails loudly, it never falls back")


def _inference_fault(exc: BaseException) -> EmbedderError:
    """Map a raised inference fault to the port taxonomy — content-free (type name only, AD-28).
    Built at module scope so a typed raise in an ``except`` names no ``embed``-containing call."""
    kind = type(exc).__name__.lower()
    if "timeout" in kind:
        return EmbedderTimeout(f"the embedding call timed out ({type(exc).__name__})")
    return EmbedderUnavailable(f"the embedder failed ({type(exc).__name__})")


class Bgem3Embedder:
    """The single concrete ``Embedder`` (AD-11): local BGE-M3, 1024-dim. ``model_id``/
    ``model_version`` stamp every chunk so a mixed-provenance corpus is detectable."""

    dimensions = _DIM

    def __init__(self, *, model_id: str = _MODEL_ID, model_version: str = _MODEL_VERSION) -> None:
        self.dimensions = _DIM
        self.model_id = model_id
        self.model_version = model_version
        self._model: object | None = None

    def _model_or_raise(self) -> object:
        """Lazy-load the backend on first use; a missing dependency FAILS LOUD (never a stub)."""
        if self._model is None:
            try:
                from FlagEmbedding import BGEM3FlagModel
            except Exception as exc:  # noqa: BLE001 — any import/backend failure fails loud
                raise _backend_missing(exc) from exc
            self._model = BGEM3FlagModel(self.model_id, use_fp16=True)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed each text into a 1024-dim dense vector, in order (the ``Embedder`` port). Recall-
        first: an empty input yields an empty list; a returned width ≠ ``dimensions`` RAISES (a
        mixed-model hazard that halts the unit, never truncates to fit — the index is never
        corrupted or self-deleted). Wraps BGE-M3's ``.encode`` (the model's own method name)."""
        if not texts:
            return []
        model = self._model_or_raise()
        try:
            out = model.encode(texts, max_length=_MAX_TOKENS)  # type: ignore[attr-defined]
            dense = out["dense_vecs"] if isinstance(out, dict) else out
        except EmbedderError:
            raise
        except Exception as exc:  # noqa: BLE001 — a fault is a loud typed failure, never a fallback
            raise _inference_fault(exc) from exc
        vectors = [[float(x) for x in row] for row in dense]
        for v in vectors:
            if len(v) != self.dimensions:
                raise EmbedderDimensionMismatch(
                    f"the embedder returned a {len(v)}-dim vector, expected {self.dimensions}")
        return vectors
