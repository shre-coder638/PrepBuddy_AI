"""Experimental grouped evaluation of neural relevance classification."""

from __future__ import annotations

import json
import time
import random
import hashlib

from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import torch

from torch import nn

from sklearn.linear_model import LogisticRegression

from sklearn.model_selection import (
    StratifiedGroupKFold,
)

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    roc_auc_score,
    average_precision_score,
)

from chatbot.ann.relevance_model import (
    RelevanceANN,
    MODEL_VERSION,
)

from chatbot.ann.relevance_features import (
    FEATURE_DIM,
    FEATURE_VERSION,
)


ROOT = Path(__file__).resolve().parent.parent

FEATURES = (
    ROOT
    / "datasets"
    / "relevance_features_experimental_v1.npz"
)

METADATA = FEATURES.with_suffix(".json")

SOURCE = (
    ROOT
    / "datasets"
    / "relevance_training_experimental_v1.jsonl"
)

RESULTS = ROOT / "evaluation" / "results"

SEED = 42

EPOCHS = 100

LEARNING_RATE = 0.001

WEIGHT_DECAY = 0.01


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def metrics(y, scores, threshold):

    predicted = (
        scores >= threshold
    ).astype(np.int64)

    tn, fp, fn, tp = confusion_matrix(
        y,
        predicted,
        labels=[0, 1],
    ).ravel()

    return {
        "threshold": float(threshold),
        "accuracy": float(
            accuracy_score(y, predicted)
        ),
        "precision": float(
            precision_score(
                y, predicted,
                zero_division=0,
            )
        ),
        "recall": float(
            recall_score(
                y, predicted,
                zero_division=0,
            )
        ),
        "f1": float(
            f1_score(
                y, predicted,
                zero_division=0,
            )
        ),
        "roc_auc": (
            float(roc_auc_score(y, scores))
            if len(np.unique(y)) == 2
            else None
        ),
        "average_precision": (
            float(average_precision_score(y, scores))
            if len(np.unique(y)) == 2
            else None
        ),
        "true_positive": int(tp),
        "true_negative": int(tn),
        "false_positive": int(fp),
        "false_negative": int(fn),
        "accepted": int(tp + fp),
    }


def train_ann(X, y, seed):

    set_seed(seed)

    model = RelevanceANN()

    features = torch.from_numpy(
        X.astype(np.float32)
    )

    targets = torch.from_numpy(
        y.astype(np.float32)
    )

    positives = int(y.sum())
    negatives = len(y) - positives

    if not positives or not negatives:
        raise ValueError(
            "Training fold requires both classes"
        )

    criterion = nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor(
            negatives / positives,
            dtype=torch.float32,
        )
    )

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
    )

    initial_weights = [
        parameter.detach().clone()
        for parameter in model.parameters()
    ]

    losses = []

    model.train()

    for epoch in range(EPOCHS):

        optimizer.zero_grad()

        logits = model(features)

        loss = criterion(logits, targets)

        if not torch.isfinite(loss):
            raise RuntimeError(
                "Non-finite training loss"
            )

        loss.backward()

        optimizer.step()

        losses.append(float(loss.item()))

    changed = any(
        not torch.equal(
            initial,
            current.detach(),
        )
        for initial, current in zip(
            initial_weights,
            model.parameters(),
        )
    )

    if not changed:
        raise RuntimeError(
            "ANN weights did not change"
        )

    model.eval()

    return model, {
        "initial_training_loss": losses[0],
        "final_training_loss": losses[-1],
        "epochs": EPOCHS,
        "weights_updated": changed,
    }


def cosine_training_threshold(y, scores):

    # Select using training-fold labels only.
    # Validation data is not used to choose this threshold.

    candidates = np.unique(scores)

    return float(max(
        candidates,
        key=lambda threshold: (
            f1_score(
                y,
                scores >= threshold,
                zero_division=0,
            ),
            threshold,
        ),
    ))


def main():

    started = time.perf_counter()

    torch.set_num_threads(2)

    metadata = json.loads(
        METADATA.read_text(encoding="utf-8")
    )

    assert metadata["experimental_only"] is True
    assert metadata["clinical_approval"] is False

    assert (
        metadata["feature_version"]
        == FEATURE_VERSION
    )

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
        languages = data["languages"]
        pair_ids = data["pair_ids"]
        question_ids = data["question_ids"]

    assert X.shape == (153, FEATURE_DIM)
    assert y.shape == (153,)
    assert np.isfinite(X).all()
    assert set(np.unique(y)) == {0, 1}
    assert int(y.sum()) == 55
    assert len(set(groups)) == 10

    splitter = StratifiedGroupKFold(
        n_splits=5,
        shuffle=True,
        random_state=SEED,
    )

    model_names = (
        "cosine",
        "logistic",
        "ann",
    )

    oof_scores = {
        name: np.full(len(y), np.nan)
        for name in model_names
    }

    oof_predictions = {
        name: np.full(len(y), -1)
        for name in model_names
    }

    fold_assignments = np.full(
        len(y),
        -1,
    )

    fold_reports = []

    for fold, (train, valid) in enumerate(
        splitter.split(X, y, groups),
        start=1,
    ):

        assert not (
            set(groups[train])
            & set(groups[valid])
        )

        assert not (
            set(question_ids[train])
            & set(question_ids[valid])
        )

        assert len(np.unique(y[train])) == 2
        assert len(np.unique(y[valid])) == 2

        assert np.all(
            fold_assignments[valid] == -1
        )

        fold_assignments[valid] = fold

        # Model 1: cosine similarity baseline.

        cosine_scores = X[valid, -1]

        cosine_threshold = cosine_training_threshold(
            y[train],
            X[train, -1],
        )

        # Model 2: logistic regression baseline.

        logistic = LogisticRegression(
            C=1.0,
            class_weight="balanced",
            max_iter=2000,
            random_state=SEED,
        )

        logistic.fit(
            X[train],
            y[train],
        )

        logistic_scores = logistic.predict_proba(
            X[valid]
        )[:, 1]

        # Model 3: actual neural network training.

        ann, training = train_ann(
            X[train],
            y[train],
            seed=SEED + fold,
        )

        ann_scores = ann.predict_scores(
            torch.from_numpy(
                X[valid].astype(np.float32)
            )
        ).numpy()

        predictions = {
            "cosine": (
                cosine_scores,
                cosine_threshold,
            ),
            "logistic": (
                logistic_scores,
                0.5,
            ),
            "ann": (
                ann_scores,
                0.5,
            ),
        }

        fold_metrics = {}

        for name, (scores, threshold) in (
            predictions.items()
        ):

            assert np.isfinite(scores).all()

            oof_scores[name][valid] = scores

            oof_predictions[name][valid] = (
                scores >= threshold
            ).astype(np.int64)

            fold_metrics[name] = metrics(
                y[valid],
                scores,
                threshold,
            )

        fold_reports.append({
            "fold": fold,
            "training_pairs": len(train),
            "validation_pairs": len(valid),
            "training_groups": sorted(
                set(groups[train])
            ),
            "validation_groups": sorted(
                set(groups[valid])
            ),
            "training": training,
            "metrics": fold_metrics,
        })

        print(
            f"Fold {fold} | "
            f"Train={len(train)} | "
            f"Validation={len(valid)} | "
            f"ANN loss="
            f"{training['initial_training_loss']:.4f}"
            f" -> "
            f"{training['final_training_loss']:.4f} | "
            f"ANN F1="
            f"{fold_metrics['ann']['f1']:.4f}",
            flush=True,
        )

    assert np.all(fold_assignments > 0)

    def aggregate(mask, name):

        actual = y[mask]

        scores = oof_scores[name][mask]

        predicted = oof_predictions[name][mask]

        assert np.isfinite(scores).all()
        assert np.all(predicted >= 0)

        tn, fp, fn, tp = confusion_matrix(
            actual,
            predicted,
            labels=[0, 1],
        ).ravel()

        return {
            "pairs": int(mask.sum()),
            "accuracy": float(
                accuracy_score(actual, predicted)
            ),
            "precision": float(
                precision_score(
                    actual,
                    predicted,
                    zero_division=0,
                )
            ),
            "recall": float(
                recall_score(
                    actual,
                    predicted,
                    zero_division=0,
                )
            ),
            "f1": float(
                f1_score(
                    actual,
                    predicted,
                    zero_division=0,
                )
            ),
            "roc_auc": (
                float(roc_auc_score(actual, scores))
                if len(np.unique(actual)) == 2
                else None
            ),
            "true_positive": int(tp),
            "true_negative": int(tn),
            "false_positive": int(fp),
            "false_negative": int(fn),
        }

    overall = {
        name: aggregate(
            np.ones(len(y), dtype=bool),
            name,
        )
        for name in model_names
    }

    by_language = {
        language: {
            name: aggregate(
                languages == language,
                name,
            )
            for name in model_names
        }
        for language in ("en", "hi", "hinglish")
    }

    ann_threshold_analysis = {
        str(threshold): metrics(
            y,
            oof_scores["ann"],
            threshold,
        )
        for threshold in (
            0.5, 0.6, 0.7, 0.8, 0.9
        )
    }

    report = {
        "model_version": MODEL_VERSION,
        "feature_version": FEATURE_VERSION,
        "experimental_only": True,
        "clinical_approval": False,
        "dataset_sha256": metadata["dataset_sha256"],
        "feature_file_sha256": (
            metadata["feature_file_sha256"]
        ),
        "seed": SEED,
        "epochs": EPOCHS,
        "learning_rate": LEARNING_RATE,
        "weight_decay": WEIGHT_DECAY,
        "folds": fold_reports,
        "overall": overall,
        "by_language": by_language,
        "ann_threshold_analysis": ann_threshold_analysis,
        "predictions": [
            {
                "pair_id": str(pair_ids[index]),
                "question_id": str(question_ids[index]),
                "group": str(groups[index]),
                "language": str(languages[index]),
                "fold": int(fold_assignments[index]),
                "target": int(y[index]),
                "scores": {
                    name: float(
                        oof_scores[name][index]
                    )
                    for name in model_names
                },
                "predictions": {
                    name: int(
                        oof_predictions[name][index]
                    )
                    for name in model_names
                },
            }
            for index in range(len(y))
        ],
    }

    RESULTS.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%dT%H%M%S%fZ")

    output = RESULTS / (
        f"relevance_ann_cv_{timestamp}.json"
    )

    report["elapsed_seconds"] = round(
        time.perf_counter() - started,
        3,
    )

    with output.open(
        "x",
        encoding="utf-8",
    ) as handle:

        json.dump(
            report,
            handle,
            indent=2,
        )

    print("\n--- MODEL COMPARISON ---")

    for name, result in overall.items():

        print(
            f"{name.upper()} | "
            f"Accuracy={result['accuracy']:.4f} | "
            f"Precision={result['precision']:.4f} | "
            f"Recall={result['recall']:.4f} | "
            f"F1={result['f1']:.4f} | "
            f"AUC={result['roc_auc']:.4f} | "
            f"FP={result['false_positive']} | "
            f"FN={result['false_negative']}"
        )

    print("\n--- ANN LANGUAGE PERFORMANCE ---")

    for language, result in by_language.items():

        print(language, json.dumps(
            result["ann"]
        ))

    print("\n--- ANN THRESHOLD ANALYSIS ---")

    for threshold, result in (
        ann_threshold_analysis.items()
    ):

        print(
            f"Threshold={threshold} | "
            f"Precision={result['precision']:.4f} | "
            f"Recall={result['recall']:.4f} | "
            f"FP={result['false_positive']} | "
            f"Accepted={result['accepted']}"
        )

    print("\nQuestion-family isolation: PASS")
    print("Out-of-fold prediction coverage: PASS")
    print("Actual ANN weight updates: PASS")
    print("Clinical approval: NOT APPROVED")
    print("Production weights saved: NO")
    print("Elapsed seconds:", report["elapsed_seconds"])
    print("Report saved:", output)
    print("EXPERIMENTAL ANN TRAINING COMPLETED")


if __name__ == "__main__":
    main()
