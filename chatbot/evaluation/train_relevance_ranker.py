"""Experimental residual ANN ranking and checkpoint generation."""

import json
import hashlib
import time
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import torch
import torch.nn.functional as F

from safetensors.torch import save_file, load_file
from sklearn.model_selection import StratifiedGroupKFold

from chatbot.ann.relevance_model import RelevanceANN
from chatbot.ann.relevance_features import FEATURE_DIM

from chatbot.evaluation.train_relevance_ann import (
    FEATURES,
    METADATA,
    SOURCE,
    SEED,
    set_seed,
)


VERSION = "relevance-ranker-experimental-v1"

EPOCHS = 100
COSINE_SCALE = 20.0

RESULTS = (
    Path(__file__).resolve().parent / "results"
)


def rank_scores(model, X):

    return (
        COSINE_SCALE * X[:, -1]
        + model(X)
    )


def train_ranker(X, y, question_ids, seed):

    set_seed(seed)

    model = RelevanceANN()

    features = torch.from_numpy(
        X.astype(np.float32)
    )

    positive_indices = []
    negative_indices = []
    weights = []
    competitive_questions = 0

    for question_id in sorted(set(question_ids)):

        indices = np.flatnonzero(
            question_ids == question_id
        )

        positive = indices[y[indices] == 1]
        negative = indices[y[indices] == 0]

        if not len(positive) or not len(negative):
            continue

        competitive_questions += 1

        weight = 1.0 / (
            len(positive) * len(negative)
        )

        for p in positive:
            for n in negative:

                positive_indices.append(int(p))
                negative_indices.append(int(n))
                weights.append(weight)

    if not positive_indices:
        raise ValueError("No usable ranking pairs.")

    p = torch.tensor(positive_indices)
    n = torch.tensor(negative_indices)

    weights = torch.tensor(
        weights,
        dtype=torch.float32,
    )

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=0.001,
        weight_decay=0.01,
    )

    before = [
        parameter.detach().clone()
        for parameter in model.parameters()
    ]

    losses = []

    model.train()

    for _ in range(EPOCHS):

        optimizer.zero_grad()

        scores = rank_scores(model, features)

        differences = scores[p] - scores[n]

        loss = (
            F.softplus(-differences) * weights
        ).sum() / weights.sum()

        if not torch.isfinite(loss):
            raise RuntimeError("Invalid ranking loss.")

        loss.backward()
        optimizer.step()

        losses.append(float(loss.item()))

    assert any(
        not torch.equal(old, new.detach())
        for old, new in zip(
            before,
            model.parameters(),
        )
    )

    model.eval()

    return model, {
        "comparisons": len(p),
        "competitive_questions": competitive_questions,
        "initial_loss": losses[0],
        "final_loss": losses[-1],
        "weights_updated": True,
    }


def evaluate_ranking(y, scores, questions, competitive_only):

    ranks = []

    for question in sorted(set(questions)):

        indices = np.flatnonzero(
            questions == question
        )

        labels = y[indices]

        if not np.any(labels == 1):
            continue

        if competitive_only and not np.any(labels == 0):
            continue

        order = indices[
            np.argsort(
                -scores[indices],
                kind="stable",
            )
        ]

        rank = int(
            np.flatnonzero(y[order] == 1)[0]
        ) + 1

        ranks.append(rank)

    if not ranks:
        return {"questions": 0}

    return {
        "questions": len(ranks),
        "top1": float(np.mean([
            rank == 1 for rank in ranks
        ])),
        "top3": float(np.mean([
            rank <= 3 for rank in ranks
        ])),
        "mrr": float(np.mean([
            1.0 / rank for rank in ranks
        ])),
    }


def main():

    started = time.perf_counter()

    torch.set_num_threads(2)

    metadata = json.loads(
        METADATA.read_text(encoding="utf-8")
    )

    assert metadata["experimental_only"] is True
    assert metadata["clinical_approval"] is False

    assert hashlib.sha256(
        FEATURES.read_bytes()
    ).hexdigest() == metadata["feature_file_sha256"]

    assert hashlib.sha256(
        SOURCE.read_bytes()
    ).hexdigest() == metadata["dataset_sha256"]

    with np.load(
        FEATURES,
        allow_pickle=False,
    ) as data:

        X = data["X"]
        y = data["y"]
        groups = data["groups"]
        questions = data["question_ids"]

    assert X.shape == (153, FEATURE_DIM)
    assert np.isfinite(X).all()

    splitter = StratifiedGroupKFold(
        n_splits=5,
        shuffle=True,
        random_state=SEED,
    )

    oof = np.full(len(y), np.nan)
    folds = []

    for fold, (train, valid) in enumerate(
        splitter.split(X, y, groups),
        start=1,
    ):

        assert not (
            set(groups[train])
            & set(groups[valid])
        )

        assert not (
            set(questions[train])
            & set(questions[valid])
        )

        assert np.isnan(oof[valid]).all()

        model, training = train_ranker(
            X[train],
            y[train],
            questions[train],
            SEED + fold,
        )

        with torch.inference_mode():

            oof[valid] = rank_scores(
                model,
                torch.from_numpy(X[valid]),
            ).numpy()

        folds.append(training)

        print(
            f"Fold {fold} | "
            f"Comparisons={training['comparisons']} | "
            f"Loss={training['initial_loss']:.4f}"
            f" -> {training['final_loss']:.4f}",
            flush=True,
        )

    assert np.isfinite(oof).all()

    comparison = {}

    for name, scores in (
        ("cosine", X[:, -1]),
        ("ann_ranker", oof),
    ):

        comparison[name] = {
            "all_positive_questions": evaluate_ranking(
                y, scores, questions, False,
            ),
            "competitive_questions_only": evaluate_ranking(
                y, scores, questions, True,
            ),
        }

    print("\n--- RANKING COMPARISON ---")

    print(json.dumps(comparison, indent=2))

    # Train a separate experimental checkpoint
    # using all available provisional examples.

    final_model, final_training = train_ranker(
        X,
        y,
        questions,
        SEED,
    )

    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%dT%H%M%S%fZ")

    output = RESULTS / (
        f"{VERSION}_{timestamp}"
    )

    output.mkdir(parents=True, exist_ok=False)

    weights_path = output / "weights.safetensors"

    save_file(
        {
            key: value.detach().cpu().contiguous()
            for key, value
            in final_model.state_dict().items()
        },
        str(weights_path),
    )

    restored = RelevanceANN()

    restored.load_state_dict(
        load_file(str(weights_path)),
        strict=True,
    )

    restored.eval()

    with torch.inference_mode():

        features = torch.from_numpy(X)

        assert torch.allclose(
            rank_scores(final_model, features),
            rank_scores(restored, features),
            atol=1e-7,
        )

    manifest = {
        "model_version": VERSION,
        "feature_version": metadata["feature_version"],
        "encoder": metadata["encoder"],
        "encoder_revision_verified": False,
        "experimental_only": True,
        "clinical_approval": False,
        "production_enabled": False,
        "dataset_sha256": metadata["dataset_sha256"],
        "feature_file_sha256": metadata["feature_file_sha256"],
        "weights_sha256": hashlib.sha256(
            weights_path.read_bytes()
        ).hexdigest(),
        "input_dimensions": FEATURE_DIM,
        "hidden_dimensions": 16,
        "dropout": 0.3,
        "cosine_scale": COSINE_SCALE,
        "epochs": EPOCHS,
        "seed": SEED,
        "folds": folds,
        "comparison": comparison,
        "final_training": final_training,
        "training_source": "provisional_development_data",
        "elapsed_seconds": round(
            time.perf_counter() - started, 3
        ),
    }

    with (output / "manifest.json").open(
        "x",
        encoding="utf-8",
    ) as handle:

        json.dump(manifest, handle, indent=2)

    print("\nFinal training:", final_training)
    print("Checkpoint round-trip: PASS")
    print("Question-family isolation: PASS")
    print("Experimental weights saved:", weights_path)
    print("Production enabled: NO")
    print("Clinical approval: NO")
    print("ANN RANKING TRAINING COMPLETED")


if __name__ == "__main__":
    main()
