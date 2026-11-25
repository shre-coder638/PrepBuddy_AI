from unittest.mock import patch

import pytest

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError

from chatbot.models import ANNExperience, ANNReviewedExample

from chatbot.ann.experience_service import (
    record_experience,
    submit_review_example,
    review_example,
)


pytestmark = pytest.mark.django_db


RECORD = {
    "protocol_id": 14,
    "step_id": 79,
    "instruction": "Synthetic instruction for software testing.",
}


@pytest.fixture
def experience():

    return record_experience(
        protocol_id=14,
        model_version="e5-test-v1",
        outcome="grounded",
        retrieved_step_ids=[79, 80],
        returned_step_ids=[79],
        latency_ms=35,
    )


@pytest.fixture
def pending_example(admin_user, experience):

    with patch(
        "chatbot.ann.experience_service.load_protocol_records",
        return_value=[RECORD],
    ):
        return submit_review_example(
            user=admin_user,
            experience_id=experience.pk,
            question="Synthetic preparation question.",
            language="en",
            step_id=79,
            deidentified=True,
        )


def test_persistent_experience(experience):

    saved = ANNExperience.objects.get(pk=experience.pk)

    assert saved.protocol_id == 14
    assert saved.outcome == "grounded"
    assert saved.retrieved_step_ids == [79, 80]
    assert saved.returned_step_ids == [79]
    assert saved.latency_ms == 35


def test_invalid_returned_source():

    with pytest.raises(ValidationError):

        record_experience(
            protocol_id=14,
            model_version="e5-test-v1",
            outcome="grounded",
            retrieved_step_ids=[79],
            returned_step_ids=[80],
        )


def test_pending_example(pending_example):

    assert pending_example.review_status == "pending"
    assert pending_example.reviewer is None
    assert pending_example.relevance_label is None
    assert pending_example.instruction_snapshot == RECORD["instruction"]


def test_unauthorized_submission(experience):

    with pytest.raises(PermissionDenied):

        submit_review_example(
            user=AnonymousUser(),
            experience_id=experience.pk,
            question="Synthetic question.",
            language="en",
            step_id=79,
            deidentified=True,
        )


def test_deidentification_required(admin_user, experience):

    with pytest.raises(ValidationError):

        submit_review_example(
            user=admin_user,
            experience_id=experience.pk,
            question="Synthetic question.",
            language="en",
            step_id=79,
            deidentified=False,
        )


def test_unauthorized_approval(pending_example):

    with pytest.raises(PermissionDenied):

        review_example(
            user=AnonymousUser(),
            example_id=pending_example.pk,
            approve=True,
            relevance_label="direct_support",
            requires_escalation=False,
        )


def test_approval(admin_user, pending_example):

    with patch(
        "chatbot.ann.experience_service.load_protocol_records",
        return_value=[RECORD],
    ):
        result = review_example(
            user=admin_user,
            example_id=pending_example.pk,
            approve=True,
            relevance_label="direct_support",
            requires_escalation=False,
        )

    result.refresh_from_db()

    assert result.review_status == "approved"
    assert result.reviewer == admin_user
    assert result.reviewed_at is not None
    assert result.relevance_label == "direct_support"


def test_stale_instruction_rejected(admin_user, pending_example):

    changed_record = {
        **RECORD,
        "instruction": "Modified synthetic instruction.",
    }

    with patch(
        "chatbot.ann.experience_service.load_protocol_records",
        return_value=[changed_record],
    ):
        with pytest.raises(ValidationError):

            review_example(
                user=admin_user,
                example_id=pending_example.pk,
                approve=True,
                relevance_label="direct_support",
                requires_escalation=False,
            )

    pending_example.refresh_from_db()

    assert pending_example.review_status == "pending"


def test_rejection(admin_user, pending_example):

    result = review_example(
        user=admin_user,
        example_id=pending_example.pk,
        approve=False,
    )

    assert result.review_status == "rejected"
    assert result.reviewer == admin_user
    assert result.reviewed_at is not None
    assert result.relevance_label is None


def test_repeat_review_rejected(admin_user, pending_example):

    review_example(
        user=admin_user,
        example_id=pending_example.pk,
        approve=False,
    )

    with pytest.raises(ValidationError):

        review_example(
            user=admin_user,
            example_id=pending_example.pk,
            approve=False,
        )


def test_duplicate_example_rejected(
    admin_user,
    experience,
    pending_example,
):

    with patch(
        "chatbot.ann.experience_service.load_protocol_records",
        return_value=[RECORD],
    ):
        with pytest.raises(ValidationError):

            submit_review_example(
                user=admin_user,
                experience_id=experience.pk,
                question="Synthetic preparation question.",
                language="en",
                step_id=79,
                deidentified=True,
            )

    assert ANNReviewedExample.objects.filter(
        experience=experience,
    ).count() == 1


from chatbot.ann.learning_export import export_approved_examples


def test_export_pending_excluded(admin_user, pending_example):

    assert export_approved_examples(user=admin_user) == []


def test_export_unauthorized():

    with pytest.raises(PermissionDenied):

        export_approved_examples(
            user=AnonymousUser(),
        )


def test_export_approved_example(admin_user, pending_example):

    with patch(
        "chatbot.ann.experience_service.load_protocol_records",
        return_value=[RECORD],
    ):

        review_example(
            user=admin_user,
            example_id=pending_example.pk,
            approve=True,
            relevance_label="direct_support",
            requires_escalation=False,
        )

        rows = export_approved_examples(
            user=admin_user,
        )

    assert len(rows) == 1
    assert rows[0]["target"] == 1
    assert rows[0]["review_status"] == "approved"
    assert rows[0]["clinical_release_approved"] is False
    assert rows[0]["experimental_only"] is True


def test_export_rejected_excluded(admin_user, pending_example):

    review_example(
        user=admin_user,
        example_id=pending_example.pk,
        approve=False,
    )

    assert export_approved_examples(user=admin_user) == []


def test_export_stale_approval_rejected(
    admin_user,
    pending_example,
):

    with patch(
        "chatbot.ann.experience_service.load_protocol_records",
        return_value=[RECORD],
    ):

        review_example(
            user=admin_user,
            example_id=pending_example.pk,
            approve=True,
            relevance_label="direct_support",
            requires_escalation=False,
        )

    changed = {
        **RECORD,
        "instruction": "Changed synthetic instruction.",
    }

    with patch(
        "chatbot.ann.experience_service.load_protocol_records",
        return_value=[changed],
    ):

        with pytest.raises(ValidationError):

            export_approved_examples(
                user=admin_user,
            )


from types import SimpleNamespace

from django.urls import reverse


def test_admin_learning_access_denied(
    client, admin_user, experience
):

    client.force_login(admin_user)

    with patch(
        "chatbot.admin.get_authorized_staff_profile",
        return_value=SimpleNamespace(role="clinic_staff"),
    ):

        response = client.get(
            reverse(
                "admin:ann_submit_example",
                args=[experience.pk],
            )
        )

    assert response.status_code == 403


def test_admin_learning_submission(
    client, admin_user, experience
):

    client.force_login(admin_user)

    with (
        patch(
            "chatbot.admin.get_authorized_staff_profile",
            return_value=SimpleNamespace(role="doctor"),
        ),
        patch(
            "chatbot.ann.experience_service.load_protocol_records",
            return_value=[RECORD],
        ),
    ):

        url = reverse(
            "admin:ann_submit_example",
            args=[experience.pk],
        )

        assert client.get(url).status_code == 200

        response = client.post(url, {
            "question": "Synthetic preparation question.",
            "language": "en",
            "step_id": 79,
            "deidentified": "on",
        })

    assert response.status_code == 302

    example = ANNReviewedExample.objects.get(
        experience=experience,
    )

    assert example.review_status == "pending"
    assert example.reviewer is None


def test_admin_learning_review(
    client, admin_user, pending_example
):

    client.force_login(admin_user)

    with (
        patch(
            "chatbot.admin.get_authorized_staff_profile",
            return_value=SimpleNamespace(role="doctor"),
        ),
        patch(
            "chatbot.ann.experience_service.load_protocol_records",
            return_value=[RECORD],
        ),
    ):

        url = reverse(
            "admin:ann_review_example",
            args=[pending_example.pk],
        )

        assert client.get(url).status_code == 200

        response = client.post(url, {
            "decision": "approve",
            "relevance_label": "direct_support",
            "escalation": "no",
        })

    assert response.status_code == 302

    pending_example.refresh_from_db()

    assert pending_example.review_status == "approved"
    assert pending_example.reviewer == admin_user


def test_admin_direct_edit_denied(
    client, admin_user, pending_example
):

    client.force_login(admin_user)

    with patch(
        "chatbot.admin.get_authorized_staff_profile",
        return_value=SimpleNamespace(role="doctor"),
    ):

        response = client.post(
            reverse(
                "admin:chatbot_annreviewedexample_change",
                args=[pending_example.pk],
            ),
            {"review_status": "approved"},
        )

    assert response.status_code == 403

    pending_example.refresh_from_db()
    assert pending_example.review_status == "pending"

