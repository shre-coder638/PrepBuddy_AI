import hashlib
from unittest.mock import patch

import numpy as np
import pytest

from chatbot.ann.learning_lifecycle import (
    retrain_from_reviewed_experiences,
    load_experimental_ranker,
)


MODULE = "chatbot.ann.learning_lifecycle"


class SyntheticEncoder:

    def encode(self, texts, **kwargs):

        vectors = []

        for text in texts:

            seed = int.from_bytes(
                hashlib.sha256(
                    text.encode("utf-8")
                ).digest()[:4],
                "big",
            )

            rng = np.random.default_rng(seed)

            vectors.append(
                rng.normal(size=384).astype(
                    np.float32
                )
            )

        return np.stack(vectors)


def synthetic_dataset():

    rows = []
    records = {}

    for index in range(10):

        protocol_id = 100 + index % 2

        for target in (0, 1):

            step_id = protocol_id * 10 + target

            instruction = (
                f"Synthetic instruction {step_id}"
            )

            records[(protocol_id, step_id)] = {
                "protocol_id": protocol_id,
                "step_id": step_id,
                "instruction": instruction,
                "text": instruction,
            }

            rows.append({
                "example_id": f"test-{index}-{target}",
                "protocol_id": protocol_id,
                "step_id": step_id,
                "question": f"Synthetic question {index}",
                "instruction": instruction,
                "instruction_sha256": hashlib.sha256(
                    instruction.encode("utf-8")
                ).hexdigest(),
                "target": target,
                "requires_escalation": False,
                "review_status": "approved",
                "experimental_only": True,
                "clinical_release_approved": False,
            })

    return rows, list(records.values())


def test_empty_dataset_blocks_training(tmp_path):

    with patch(
        MODULE + ".export_approved_examples",
        return_value=[],
    ):

        with pytest.raises(
            ValueError,
            match="No approved",
        ):

            retrain_from_reviewed_experiences(
                user=object(),
                output_root=tmp_path,
            )

    assert not list(tmp_path.iterdir())


def test_insufficient_data_blocks_training(tmp_path):

    rows, _ = synthetic_dataset()

    with patch(
        MODULE + ".export_approved_examples",
        return_value=rows[:2],
    ):

        with pytest.raises(
            ValueError,
            match="Insufficient competitive",
        ):

            retrain_from_reviewed_experiences(
                user=object(),
                output_root=tmp_path,
            )


def test_reviewed_training_and_checkpoint(tmp_path):

    rows, records = synthetic_dataset()

    with (
        patch(
            MODULE + ".export_approved_examples",
            return_value=rows,
        ),
        patch(
            MODULE + ".load_active_protocols",
            return_value=records,
        ),
        patch(
            MODULE + "._get_model",
            return_value=SyntheticEncoder(),
        ),
    ):

        output = retrain_from_reviewed_experiences(
            user=object(),
            output_root=tmp_path,
        )

    model, manifest = load_experimental_ranker(output)

    assert not model.training
    assert manifest["training"]["weights_updated"]
    assert manifest["training_pairs"] == 20
    assert manifest["competitive_questions"] == 10
    assert manifest["protocol_count"] == 2

    assert manifest["training_source"] == (
        "reviewed_experiences_only"
    )

    assert manifest["production_enabled"] is False
    assert manifest["clinical_approval"] is False

    # Verify that modified checkpoints cannot be loaded.

    weights = output / "weights.safetensors"

    weights.write_bytes(
        weights.read_bytes() + b"tampered"
    )

    with pytest.raises(
        ValueError,
        match="integrity failure",
    ):

        load_experimental_ranker(output)
