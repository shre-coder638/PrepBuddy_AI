"""Shared embedding-pair features for ANN relevance classification."""

from __future__ import annotations

import numpy as np


FEATURE_VERSION = "e5-pair-v1"

EMBEDDING_DIM = 384

FEATURE_DIM = EMBEDDING_DIM * 4 + 1


def _validate_embedding(vector):

    vector = np.asarray(
        vector,
        dtype=np.float32,
    )

    if vector.shape != (EMBEDDING_DIM,):
        raise ValueError(
            f"Unexpected embedding shape: {vector.shape}"
        )

    if not np.isfinite(vector).all():
        raise ValueError(
            "Embedding contains non-finite values"
        )

    norm = float(np.linalg.norm(vector))

    if norm <= 1e-8:
        raise ValueError("Zero-length embedding")

    return vector / norm


def build_pair_features(
    question_embedding,
    instruction_embedding,
):
    """Combine normalized E5 embeddings into relevance features."""

    question = _validate_embedding(
        question_embedding
    )

    instruction = _validate_embedding(
        instruction_embedding
    )

    similarity = float(
        np.clip(
            np.dot(question, instruction),
            -1.0,
            1.0,
        )
    )

    features = np.concatenate([
        question,
        instruction,
        np.abs(question - instruction),
        question * instruction,
        np.asarray(
            [similarity],
            dtype=np.float32,
        ),
    ]).astype(np.float32)

    if features.shape != (FEATURE_DIM,):
        raise ValueError(
            "Unexpected relevance feature dimensions"
        )

    if not np.isfinite(features).all():
        raise ValueError(
            "Non-finite relevance features"
        )

    return features
