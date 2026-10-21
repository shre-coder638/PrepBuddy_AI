from frontend.models import StaffProfile
from datetime import timedelta
from reminders.views import sync_procedure_status
from django.test import TestCase
from django.utils import timezone

from patients.models import Patient
from procedures.models import Procedure
from protocols.models import PrepProtocol, PrepStep
from reminders.models import Reminder
from reminders.services import generate_reminders_for_procedure

from django.contrib.auth import get_user_model
from django.urls import reverse
from reminders.models import ReminderFollowUp


class ReminderTokenTests(TestCase):
    def setUp(self):
        self.patient = Patient.objects.create(
            first_name="Test",
            last_name="Patient",
            phone_number="+919999000001",
        )

        self.protocol = PrepProtocol.objects.create(
            name="Test Protocol",
            is_active=True,
        )

        self.step = PrepStep.objects.create(
            protocol=self.protocol,
            title="Test preparation step",
            instruction="Test instruction only",
            minutes_before_procedure=60,
        )

        self.procedure = Procedure.objects.create(
            patient=self.patient,
            protocol=self.protocol,
            procedure_name="Test Procedure",
            scheduled_at=timezone.now() + timedelta(days=3),
        )

    def test_new_reminder_gets_unique_confirmation_token(self):
        reminder = Reminder.objects.create(
            procedure=self.procedure,
            prep_step=self.step,
            scheduled_at=self.procedure.scheduled_at
            - timedelta(minutes=self.step.minutes_before_procedure),
        )

        self.assertTrue(reminder.confirmation_token)
        self.assertEqual(len(reminder.confirmation_token), 43)

    def test_generated_reminder_has_correct_schedule(self):
        reminders = generate_reminders_for_procedure(self.procedure)

        self.assertEqual(len(reminders), 1)
        self.assertEqual(
            reminders[0].scheduled_at,
            self.procedure.scheduled_at - timedelta(minutes=60),
        )
        self.assertTrue(reminders[0].confirmation_token)

    def test_generating_reminders_twice_does_not_duplicate_them(self):
        first_result = generate_reminders_for_procedure(self.procedure)
        second_result = generate_reminders_for_procedure(self.procedure)

        self.assertEqual(len(first_result), 1)
        self.assertEqual(len(second_result), 1)
        self.assertEqual(
            Reminder.objects.filter(procedure=self.procedure).count(),
            1,
        )


class ConfirmReminderTests(ReminderTokenTests):
    def setUp(self):
        super().setUp()

        self.reminder = Reminder.objects.create(
            procedure=self.procedure,
            prep_step=self.step,
            scheduled_at=(
                self.procedure.scheduled_at
                - timedelta(minutes=self.step.minutes_before_procedure)
            ),
            status="sent",
            sent_at=timezone.now(),
        )

        self.url = (
            f"/api/reminders/"
            f"{self.reminder.confirmation_token}/confirm/"
        )

    def test_valid_confirmation_updates_status_and_timestamp(self):
        response = self.client.post(self.url)

        self.reminder.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.reminder.status, "confirmed")
        self.assertIsNotNone(self.reminder.confirmed_at)
        self.assertEqual(response.data["status"], "confirmed")

    def test_invalid_token_returns_404(self):
        response = self.client.post(
            "/api/reminders/invalid-token/confirm/"
        )

        self.assertEqual(response.status_code, 404)

    def test_repeated_confirmation_preserves_original_timestamp(self):
        first_response = self.client.post(self.url)
        self.reminder.refresh_from_db()
        original_timestamp = self.reminder.confirmed_at

        second_response = self.client.post(self.url)

        self.reminder.refresh_from_db()

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(
            self.reminder.confirmed_at,
            original_timestamp,
        )

    def test_missed_reminder_cannot_be_confirmed(self):
        self.reminder.status = "missed"
        self.reminder.save(update_fields=["status"])

        response = self.client.post(self.url)

        self.reminder.refresh_from_db()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.reminder.status, "missed")
        self.assertIsNone(self.reminder.confirmed_at)

    def test_cancelled_reminder_cannot_be_confirmed(self):
        self.reminder.status = "cancelled"
        self.reminder.save(update_fields=["status"])

        response = self.client.post(self.url)

        self.reminder.refresh_from_db()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.reminder.status, "cancelled")
        self.assertIsNone(self.reminder.confirmed_at)

    def test_pending_reminder_can_be_confirmed_early(self):
        self.reminder.status = "pending"
        self.reminder.save(update_fields=["status"])
    
        response = self.client.post(self.url)
    
        self.reminder.refresh_from_db()
    
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.reminder.status, "confirmed")
        self.assertIsNotNone(self.reminder.confirmed_at)


    def test_failed_delivery_reminder_can_be_confirmed(self):
        self.reminder.status = "failed"
        self.reminder.save(update_fields=["status"])
    
        response = self.client.post(self.url)
    
        self.reminder.refresh_from_db()
    
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.reminder.status, "confirmed")
        self.assertIsNotNone(self.reminder.confirmed_at)


class ProcedureStatusSyncTests(ReminderTokenTests):
    def test_all_confirmed_reminders_make_procedure_ready(self):
        self.reminder = Reminder.objects.create(
            procedure=self.procedure,
            prep_step=self.step,
            scheduled_at=self.procedure.scheduled_at
            - timedelta(minutes=self.step.minutes_before_procedure),
            status="confirmed",
            confirmed_at=timezone.now(),
        )

        self.procedure.status = "scheduled"
        self.procedure.save(update_fields=["status"])

        sync_procedure_status(self.procedure)
        self.procedure.refresh_from_db()

        self.assertEqual(self.procedure.status, "ready")

    def test_unconfirmed_reminder_sets_prep_in_progress(self):
        self.reminder = Reminder.objects.create(
            procedure=self.procedure,
            prep_step=self.step,
            scheduled_at=self.procedure.scheduled_at
            - timedelta(minutes=self.step.minutes_before_procedure),
            status="sent",
            sent_at=timezone.now(),
        )

        sync_procedure_status(self.procedure)
        self.procedure.refresh_from_db()

        self.assertEqual(self.procedure.status, "prep_in_progress")

    def test_attention_needed_status_is_preserved(self):
        self.procedure.status = "attention_needed"
        self.procedure.save(update_fields=["status"])

        sync_procedure_status(self.procedure)
        self.procedure.refresh_from_db()

        self.assertEqual(self.procedure.status, "attention_needed")

    def test_cancelled_status_is_preserved(self):
        self.procedure.status = "cancelled"
        self.procedure.save(update_fields=["status"])

        sync_procedure_status(self.procedure)
        self.procedure.refresh_from_db()

        self.assertEqual(self.procedure.status, "cancelled")

    def test_completed_status_is_preserved(self):
        self.procedure.status = "completed"
        self.procedure.save(update_fields=["status"])

        sync_procedure_status(self.procedure)
        self.procedure.refresh_from_db()

        self.assertEqual(self.procedure.status, "completed")


class ReminderFollowUpAPITests(TestCase):
    
    
    def setUp(self):
        self.patient = Patient.objects.create(
            first_name="Follow-up",
            last_name="Patient",
            phone_number="+919999000002",
        )
    
        self.protocol = PrepProtocol.objects.create(
            name="Follow-up Test Protocol",
            is_active=True,
        )
    
        self.step = PrepStep.objects.create(
            protocol=self.protocol,
            title="Follow-up preparation step",
            instruction="Test instruction only",
            minutes_before_procedure=60,
        )
    
        self.procedure = Procedure.objects.create(
            patient=self.patient,
            protocol=self.protocol,
            procedure_name="Follow-up Test Procedure",
            scheduled_at=timezone.now() + timedelta(days=3),
        )
    
        self.user = get_user_model().objects.create_user(
            username="followup_staff",
            password="test-password-123",
        )
        
        StaffProfile.objects.create(
            user=self.user,
            role="clinic_staff",
        )
        
        self.reminder = Reminder.objects.create(
            procedure=self.procedure,
            prep_step=self.step,
            scheduled_at=timezone.now() - timedelta(minutes=30),
            status="missed",
        )
    
        self.url = reverse("create-reminder-follow-up")

    def test_unauthenticated_user_cannot_create_follow_up(self):
        response = self.client.post(
            self.url,
            {
                "reminder_id": self.reminder.id,
                "contact_outcome": "reached",
                "preparation_status": "completed",
            },
        )

        self.assertIn(response.status_code, [401, 403])
        self.assertEqual(ReminderFollowUp.objects.count(), 0)

    def test_invalid_contact_outcome_is_rejected(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            {
                "reminder_id": self.reminder.id,
                "contact_outcome": "invalid",
                "preparation_status": "unknown",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(ReminderFollowUp.objects.count(), 0)

    def test_authenticated_user_can_record_follow_up(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            {
                "reminder_id": self.reminder.id,
                "contact_outcome": "reached",
                "preparation_status": "completed",
                "notes": "Patient reports completing the step.",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)

        follow_up = ReminderFollowUp.objects.get()

        self.assertEqual(follow_up.reminder, self.reminder)
        self.assertEqual(follow_up.created_by, self.user)
        self.assertEqual(follow_up.contact_outcome, "reached")
        self.assertEqual(follow_up.preparation_status, "completed")
        self.assertTrue(follow_up.requires_clinical_review)

        self.reminder.refresh_from_db()
        self.assertEqual(self.reminder.status, "missed")

    def test_follow_up_cannot_be_created_for_non_missed_reminder(self):
        self.client.force_login(self.user)
        self.reminder.status = "pending"
        self.reminder.save(update_fields=["status"])

        response = self.client.post(
            self.url,
            {
                "reminder_id": self.reminder.id,
                "contact_outcome": "reached",
                "preparation_status": "unknown",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(ReminderFollowUp.objects.count(), 0)
