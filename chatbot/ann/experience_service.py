"""Controlled persistence and review of ANN learning experiences."""

import hashlib
import re

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from chatbot.models import ANNExperience, ANNReviewedExample

from .protocol_records import load_protocol_records


def _positive_id(value):

    if type(value) is not int or value <= 0:
        raise ValidationError("Invalid identifier.")

    return value


def _step_ids(values):

    if not isinstance(values, (list, tuple)):
        raise ValidationError("Expected a list of step IDs.")

    if len(values) > 100:
        raise ValidationError("Too many step IDs.")

    result = [_positive_id(value) for value in values]

    if len(result) != len(set(result)):
        raise ValidationError("Duplicate step IDs.")

    return result


def _version(value):

    if (
        not isinstance(value, str)
        or not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", value)
    ):
        raise ValidationError("Invalid version identifier.")

    return value


def _require_permission(user, permission):

    if not (
        user is not None
        and user.is_authenticated
        and user.is_active
        and user.is_staff
        and user.has_perm(permission)
    ):
        raise PermissionDenied("Learning review access denied.")


def _instruction_hash(instruction):

    return hashlib.sha256(
        instruction.encode("utf-8")
    ).hexdigest()


def _current_record(protocol_id, step_id):

    _positive_id(protocol_id)
    _positive_id(step_id)

    if protocol_id == 16:
        raise ValidationError("Non-clinical protocol excluded.")

    matches = [
        record
        for record in load_protocol_records(protocol_id)
        if record["protocol_id"] == protocol_id
        and record["step_id"] == step_id
    ]

    if len(matches) != 1:
        raise ValidationError(
            "Current instruction is unavailable."
        )

    return matches[0]


def record_experience(
    *,
    protocol_id,
    model_version,
    feature_version="",
    outcome,
    retrieved_step_ids=(),
    returned_step_ids=(),
    needs_clinical_team=False,
    latency_ms=0,
):

    if protocol_id is not None:
        _positive_id(protocol_id)

    if outcome not in ANNExperience.Outcome.values:
        raise ValidationError("Invalid experience outcome.")

    if type(needs_clinical_team) is not bool:
        raise ValidationError("Invalid escalation flag.")

    if (
        type(latency_ms) is not int
        or not 0 <= latency_ms <= 2147483647
    ):
        raise ValidationError("Invalid latency.")

    retrieved = _step_ids(retrieved_step_ids)
    returned = _step_ids(returned_step_ids)

    if protocol_id is None and (retrieved or returned):
        raise ValidationError(
            "Evidence requires an assigned protocol."
        )

    if outcome == ANNExperience.Outcome.GROUNDED:

        if len(returned) != 1:
            raise ValidationError(
                "Grounded response requires one source."
            )

        if returned[0] not in retrieved:
            raise ValidationError(
                "Returned source was not retrieved."
            )

    if outcome == ANNExperience.Outcome.OVERVIEW:
        if not returned:
            raise ValidationError(
                "Overview requires stored sources."
            )

    experience = ANNExperience(
        protocol_id=protocol_id,
        model_version=_version(model_version),
        feature_version=(
            _version(feature_version)
            if feature_version else ""
        ),
        outcome=outcome,
        retrieved_step_ids=retrieved,
        returned_step_ids=returned,
        needs_clinical_team=needs_clinical_team,
        latency_ms=latency_ms,
    )

    experience.full_clean()
    experience.save(force_insert=True)

    return experience


@transaction.atomic
def submit_review_example(
    *,
    user,
    experience_id,
    question,
    language,
    step_id,
    deidentified=False,
):

    _require_permission(
        user,
        "chatbot.add_annreviewedexample",
    )

    if deidentified is not True:
        raise ValidationError(
            "Explicit de-identification confirmation required."
        )

    if (
        not isinstance(question, str)
        or not question.strip()
        or len(question) > 2000
    ):
        raise ValidationError("Invalid review question.")

    if language not in ANNReviewedExample.Language.values:
        raise ValidationError("Unsupported language label.")

    experience = (
        ANNExperience.objects.select_for_update()
        .get(pk=experience_id)
    )

    if experience.protocol_id is None:
        raise ValidationError(
            "Experience has no assigned protocol."
        )

    record = _current_record(
        experience.protocol_id,
        step_id,
    )

    instruction = record["instruction"]

    example = ANNReviewedExample(
        experience=experience,
        question=question.strip(),
        language=language,
        protocol_id=experience.protocol_id,
        step_id=step_id,
        instruction_snapshot=instruction,
        instruction_sha256=_instruction_hash(instruction),
        review_status=ANNReviewedExample.ReviewStatus.PENDING,
    )

    example.full_clean()
    example.save(force_insert=True)

    return example


@transaction.atomic
def review_example(
    *,
    user,
    example_id,
    approve,
    relevance_label=None,
    requires_escalation=None,
):

    _require_permission(
        user,
        "chatbot.change_annreviewedexample",
    )

    if type(approve) is not bool:
        raise ValidationError("Invalid review decision.")

    example = (
        ANNReviewedExample.objects.select_for_update()
        .get(pk=example_id)
    )

    if (
        example.review_status
        != ANNReviewedExample.ReviewStatus.PENDING
    ):
        raise ValidationError(
            "Only pending examples may be reviewed."
        )

    if approve:

        if (
            relevance_label
            not in ANNReviewedExample.Relevance.values
        ):
            raise ValidationError(
                "Valid relevance label required."
            )

        if type(requires_escalation) is not bool:
            raise ValidationError(
                "Explicit escalation decision required."
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
                "Instruction changed. New review required."
            )

        example.relevance_label = relevance_label
        example.requires_escalation = requires_escalation

        example.review_status = (
            ANNReviewedExample.ReviewStatus.APPROVED
        )

    else:

        example.relevance_label = None
        example.requires_escalation = None

        example.review_status = (
            ANNReviewedExample.ReviewStatus.REJECTED
        )

    example.reviewer = user
    example.reviewed_at = timezone.now()

    example.full_clean()
    example.save()

    return example
