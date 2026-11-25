"""Trainable neural relevance classifier."""

from __future__ import annotations

import torch
from torch import nn

from .relevance_features import FEATURE_DIM


MODEL_VERSION = "relevance-mlp-v1"

HIDDEN_DIM = 16

DROPOUT = 0.3


class RelevanceANN(nn.Module):

    def __init__(
        self,
        input_dim=FEATURE_DIM,
        hidden_dim=HIDDEN_DIM,
        dropout=DROPOUT,
    ):
        super().__init__()

        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, features):

        if features.ndim != 2:
            raise ValueError(
                "Expected a two-dimensional feature matrix"
            )

        if (
            features.shape[1]
            != self.network[0].in_features
        ):
            raise ValueError(
                "Unexpected feature dimensions"
            )

        return self.network(features).squeeze(-1)

    def predict_scores(self, features):

        if self.training:
            raise RuntimeError(
                "Model must be in evaluation mode"
            )

        with torch.inference_mode():
            return torch.sigmoid(
                self.forward(features)
            )
