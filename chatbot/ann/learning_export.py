"""Export reviewed ANN learning examples for offline training."""

from django.core.exceptions import ValidationError

from chatbot.models import ANNReviewedExample

from .experience_service import (
    _require_permission,
    _current_record,
    _instruction_hash,
)


def export_approved_examples(*, user):

    _require_permission(
        user,
        "chatbot.view_annreviewedexample",
    )

    _require_permission(
        user,
        "chatbot.change_annreviewedexample",
    )

    examples = (
        ANNReviewedExample.objects
        .filter(review_status="approved")
        .select_related("experience", "reviewer")
        .order_by("created_at", "pk")
    )

    output = []
    seen = {}

    for example in examples:

        if (
            example.reviewer_id is None
            or example.reviewed_at is None
            or example.requires_escalation is None
            or example.relevance_label
            not in ANNReviewedExample.Relevance.values
        ):
            raise ValidationError(
                "Incomplete approved review."
            )

        if example.protocol_id != example.experience.protocol_id:
            raise ValidationError("Protocol mismatch.")

        record = _current_record(
            example.protocol_id,
            example.step_id,
        )

        if (
            _instruction_hash(example.instruction_snapshot)
            != example.instruction_sha256
            or _instruction_hash(record["instruction"])
            != example.instruction_sha256
        ):
            raise ValidationError(
                "Approved instruction changed. New review required."
            )

        normalized_question = " ".join(
            example.question.casefold().split()
        )

        if not normalized_question:
            raise ValidationError("Empty review question.")

        key = (
            example.protocol_id,
            example.step_id,
            normalized_question,
            example.instruction_sha256,
        )

        label = (
            example.relevance_label,
            example.requires_escalation,
        )

        if key in seen:

            if seen[key] != label:
                raise ValidationError(
                    "Conflicting duplicate review labels."
                )

            continue

        seen[key] = label

        output.append({
            "example_id": str(example.pk),
            "question": example.question,
            "language": example.language,
            "protocol_id": example.protocol_id,
            "step_id": example.step_id,
            "instruction": example.instruction_snapshot,
            "instruction_sha256": example.instruction_sha256,
            "relevance_label": example.relevance_label,
            "target": int(
                example.relevance_label == "direct_support"
            ),
            "requires_escalation": example.requires_escalation,
            "review_status": "approved",
            "reviewed_at": example.reviewed_at.isoformat(),
            "group": f"protocol_{example.protocol_id}",
            "source": "reviewed_experience",
            "experimental_only": True,
            "clinical_release_approved": False,
        })

    return output
