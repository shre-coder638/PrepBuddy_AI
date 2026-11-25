"""Lazy, source-grounded multilingual E5 retrieval.

This module is isolated from the existing Ollama RAG implementation.
It does not load PyTorch or Sentence Transformers until retrieval is used.
"""

from __future__ import annotations

import hashlib
import threading
from typing import Any


MODEL_NAME = "intfloat/multilingual-e5-small"
MODEL_REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
DEFAULT_TOP_K = 3

_model = None
_model_lock = threading.Lock()

_index_lock = threading.Lock()
_cached_fingerprint: str | None = None
_cached_passage_vectors = None


def _get_model():
    """Load the E5 model once, only when retrieval is requested."""
    global _model

    if _model is None:
        with _model_lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer(
                    MODEL_NAME,
                    revision=MODEL_REVISION,
                    device="cpu",
                    trust_remote_code=False,
                )

    return _model


def _fingerprint(records: list[dict[str, Any]]) -> str:
    """Create a stable fingerprint of the ordered passage texts."""
    digest = hashlib.sha256()

    for record in records:
        text = str(record.get("text", ""))
        digest.update(text.encode("utf-8"))
        digest.update(b"\0")

    return digest.hexdigest()


def _get_passage_vectors(records: list[dict[str, Any]]):
    """Return cached normalized passage embeddings, refreshing if needed."""
    global _cached_fingerprint, _cached_passage_vectors

    fingerprint = _fingerprint(records)

    with _index_lock:
        if (
            _cached_fingerprint != fingerprint
            or _cached_passage_vectors is None
        ):
            model = _get_model()

            passages = [
                "passage: " + str(record["text"])
                for record in records
            ]

            vectors = model.encode(
                passages,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )

            _cached_passage_vectors = vectors
            _cached_fingerprint = fingerprint

        return _cached_passage_vectors


def retrieve_e5_steps(
    question: str,
    *,
    limit: int = DEFAULT_TOP_K,
    protocol_id: int | None = None,
) -> list[dict[str, Any]]:
    """Retrieve ranked protocol steps using multilingual E5.

    When protocol_id is supplied, only records from that protocol
    are eligible for retrieval.

    Similarity values are ranking scores, not calibrated confidence values.
    The returned records retain their original protocol metadata.
    """
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be a non-empty string")

    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit must be a positive integer")

    from chatbot.evaluation.load_protocols import load_active_protocols

    if protocol_id is not None and (
        not isinstance(protocol_id, int)
        or isinstance(protocol_id, bool)
        or protocol_id < 1
    ):
        raise ValueError("protocol_id must be a positive integer or None")

    records = load_active_protocols()

    eligible_indices = [
        index
        for index, record in enumerate(records)
        if protocol_id is None
        or record["protocol_id"] == protocol_id
    ]

    if not eligible_indices:
        return []

    model = _get_model()
    passage_vectors = _get_passage_vectors(records)

    query_vector = model.encode(
        ["query: " + question.strip()],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )[0]

    import numpy as np

    similarities = np.matmul(passage_vectors, query_vector)

    # Original record index provides deterministic tie-breaking.
    ranked_indices = sorted(
        eligible_indices,
        key=lambda index: (-float(similarities[index]), index),
    )

    results = []

    for index in ranked_indices[:limit]:
        result = dict(records[index])
        result["similarity"] = float(similarities[index])
        results.append(result)

    return results


def clear_e5_cache() -> None:
    """Clear cached model and passage embeddings (useful for tests/admin)."""
    global _model, _cached_fingerprint, _cached_passage_vectors

    # Keep the same lock order as _get_passage_vectors().
    with _index_lock:
        with _model_lock:
            _model = None

        _cached_fingerprint = None
        _cached_passage_vectors = None
