import hashlib
import hmac
import json
import logging
import requests

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from chatbot.views import answer_question
from chatbot.rag import safety_response
from chatbot.ann.clarification import assess_clarification
from chatbot.sentiment import analyze_patient_message
from chatbot.response_generator import select_communication_style
from chatbot.conversation import save_conversation_message
from patients.models import Patient
from reminders.models import Reminder
from django.utils.timezone import now
from django.db import transaction, IntegrityError
from procedures.models import Procedure
from chatbot.conversation import (
    save_conversation_message,
    get_recent_conversation,
    resolve_followup_question,
    is_context_dependent_followup,
)

from .whatsapp import send_openwa_message, WhatsAppOutboundError
from .models import (
    WhatsAppAssistantSession,
    ProcessedWhatsAppMessage,
    WhatsAppMessageAnalysis,
    WhatsAppOutboundMessage,
)

logger = logging.getLogger(__name__)

def mark_whatsapp_message_processed(message_record):
    if message_record is None or message_record.processing_started_at is None:
        return False

    claim_token = message_record.processing_started_at

    updated = ProcessedWhatsAppMessage.objects.filter(
        pk=message_record.pk,
        is_processed=False,
        processing_started_at=claim_token,
    ).update(
        is_processed=True,
        processed_at=timezone.now(),
        processing_started_at=None,
    )

    message_record.refresh_from_db()
    return updated == 1


def release_whatsapp_message_claim(message_record):
    if message_record is None or message_record.processing_started_at is None:
        return False

    claim_token = message_record.processing_started_at

    updated = ProcessedWhatsAppMessage.objects.filter(
        pk=message_record.pk,
        is_processed=False,
        processing_started_at=claim_token,
    ).update(
        processing_started_at=None,
    )

    message_record.refresh_from_db()
    return updated == 1

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

def claim_whatsapp_message(message_id):
    """
    Claim a message once. Claims older than five minutes can be retried.
    Returns (record, claimed).
    """
    lease_timeout = timedelta(minutes=5)

    try:
        with transaction.atomic():
            record, created = (
                ProcessedWhatsAppMessage.objects.get_or_create(
                    message_id=str(message_id)
                )
            )

            record = (
                ProcessedWhatsAppMessage.objects
                .select_for_update()
                .get(pk=record.pk)
            )

            current_time = timezone.now()

            if record.is_processed:
                return record, False

            lease_is_active = (
                record.processing_started_at is not None
                and record.processing_started_at
                > current_time - lease_timeout
            )

            if lease_is_active:
                return record, False

            record.processing_started_at = current_time
            record.save(update_fields=["processing_started_at"])

            return record, True

    except IntegrityError:
        # A concurrent request may have inserted the same message ID.
        with transaction.atomic():
            record = (
                ProcessedWhatsAppMessage.objects
                .select_for_update()
                .get(message_id=str(message_id))
            )

            current_time = timezone.now()

            if record.is_processed:
                return record, False

            lease_is_active = (
                record.processing_started_at is not None
                and record.processing_started_at
                > current_time - lease_timeout
            )

            if lease_is_active:
                return record, False

            record.processing_started_at = current_time
            record.save(update_fields=["processing_started_at"])

            return record, True

@csrf_exempt
def openwa_webhook(request):

    if request.method != "POST":
        return JsonResponse(
            {"error": "POST request required"},
            status=405
        )

    secret = settings.OPENWA_WEBHOOK_SECRET
    if not secret:
        logger.error("OpenWA webhook secret is not configured.")
        return JsonResponse(
            {"error": "Webhook authentication is not configured"},
            status=503,
        )

    received_signature = request.headers.get("X-OpenWA-Signature", "")
    expected_digest = hmac.new(
        secret.encode("utf-8"),
        request.body,
        hashlib.sha256,
    ).hexdigest()
    expected_signature = f"sha256={expected_digest}"

    if not hmac.compare_digest(received_signature, expected_signature):
        logger.warning("OpenWA webhook rejected: invalid signature.")
        return JsonResponse(
            {"error": "Invalid webhook signature"},
            status=401,
        )

    message_record = None

    try:
        payload = json.loads(request.body)

        logger.info("OpenWA webhook event received.")

        event = payload.get("event")
        data = payload.get("data", {})

        # Validate event data before processing it.
        if not isinstance(data, dict):
            return JsonResponse(
                {"error": "Invalid event data"},
                status=400,
            )

        # Ignore group and newsletter messages.
        if event == "message.received":
            sender_value = data.get("from", "")
            if not isinstance(sender_value, str):
                sender_value = ""

            if (
                data.get("isGroup") is True
                or "@g.us" in sender_value
                or "@newsletter" in sender_value
            ):
                return JsonResponse({
                    "received": True,
                    "ignored": True,
                    "reason": "Group and newsletter messages are not supported",
                })

        # Claim incoming messages to prevent concurrent duplicate processing.
        message_id = None
        message_record = None

        if event == "message.received":
            message_id = data.get("id") or data.get("messageId")

            if not message_id:
                logger.warning("OpenWA inbound event omitted its message ID.")
                return JsonResponse({
                    "received": True,
                    "processed": False,
                    "reason": "Missing message ID; duplicate protection unavailable",
                }, status=400)

            message_record, claimed = claim_whatsapp_message(
                str(message_id)
            )

            if not claimed:
                return JsonResponse({
                    "received": True,
                    "duplicate": True,
                })

        # Handle outbound-message delivery acknowledgements separately.
        if event in ("message.ack", "message.failed"):
            message_id = data.get("messageId") or data.get("id")

            raw_status = (
                "failed"
                if event == "message.failed"
                else data.get("status", data.get("ack"))
            )

            if not message_id:
                logger.warning("OpenWA acknowledgement omitted its message ID.")
                return JsonResponse({
                    "received": True,
                    "updated": False,
                    "reason": "Missing message ID",
                })

            delivery_status = (
                raw_status.strip().lower()
                if isinstance(raw_status, str)
                else None
            )

            allowed_statuses = {"sent", "delivered", "read", "failed"}

            if delivery_status not in allowed_statuses:
                logger.warning("OpenWA acknowledgement had an unrecognized status.")
                return JsonResponse({
                    "received": True,
                    "updated": False,
                    "reason": "Unrecognized delivery status",
                })

            message_id = str(message_id)

            # Never choose an arbitrary row when an OpenWA ID is duplicated.
            outbound_matches = list(
                WhatsAppOutboundMessage.objects.filter(
                    openwa_message_id=message_id,
                )[:2]
            )
            reminder_matches = list(
                Reminder.objects.filter(
                    openwa_message_id=message_id,
                )[:2]
            )

            status_rank = {
                "pending": 0,
                "accepted": 1,
                "sent": 2,
                "delivered": 3,
                "read": 4,
            }

            def apply_delivery_status(record):
                current_status = record.delivery_status

                # A late failure must not undo a confirmed delivery or read.
                if (
                    current_status in ("delivered", "read")
                    and delivery_status == "failed"
                ):
                    return False

                if (
                    delivery_status in status_rank
                    and current_status in status_rank
                    and status_rank[delivery_status] < status_rank[current_status]
                ):
                    return False

                if current_status != delivery_status:
                    record.delivery_status = delivery_status
                    record.save(update_fields=["delivery_status"])

                return True

            updated = False
            reminder_id = None
            ambiguous = False

            if len(outbound_matches) == 1:
                outbound = outbound_matches[0]
                if apply_delivery_status(outbound):
                    updated = True
                    logger.info(
                        "Outbound message %s delivery status updated to %s.",
                        outbound.id,
                        delivery_status,
                    )
            elif len(outbound_matches) > 1:
                ambiguous = True
                logger.warning(
                    "Ambiguous outbound message ID %s; no ledger row updated.",
                    message_id,
                )

            if len(reminder_matches) == 1:
                reminder = reminder_matches[0]
                if apply_delivery_status(reminder):
                    updated = True
                    reminder_id = reminder.id
                    logger.info(
                        "Reminder %s delivery status updated to %s.",
                        reminder.id,
                        delivery_status,
                    )
            elif len(reminder_matches) > 1:
                ambiguous = True
                logger.warning(
                    "Ambiguous reminder message ID %s; no reminder row updated.",
                    message_id,
                )

            if not updated:
                if ambiguous:
                    reason = "Ambiguous message ID"
                elif outbound_matches or reminder_matches:
                    reason = "Existing delivery state takes precedence"
                else:
                    reason = "No matching outbound message"

                return JsonResponse({
                    "received": True,
                    "updated": False,
                    "ignored": True,
                    "reason": reason,
                })

            response_data = {
                "received": True,
                "updated": True,
                "delivery_status": delivery_status,
            }

            if reminder_id is not None:
                response_data["reminder_id"] = reminder_id

            return JsonResponse(response_data)

        # Keep the existing inbound DONE handler unchanged.
        if event != "message.received":
            return JsonResponse({
                "received": True,
                "ignored": True,
            })

        sender_value = data.get("from")
        body_value = data.get("body")

        # Reject malformed inbound fields instead of allowing .strip()
        # to raise an unexpected exception.
        if not isinstance(sender_value, str) or not sender_value.strip():
            logger.warning("OpenWA inbound message has an invalid sender.")
            mark_whatsapp_message_processed(message_record)

            return JsonResponse({
                "received": True,
                "processed": True,
                "error": "Invalid sender",
            }, status=400)

        if not isinstance(body_value, str):
            logger.warning("OpenWA inbound message has an invalid body.")
            mark_whatsapp_message_processed(message_record)

            return JsonResponse({
                "received": True,
                "processed": True,
                "error": "Invalid message body",
            }, status=400)

        sender = sender_value.strip()
        message = body_value.strip()

        logger.info("OpenWA inbound patient message received.")

        # Empty but valid text messages are safely ignored.
        if not message:
            mark_whatsapp_message_processed(message_record)

            return JsonResponse({
                "received": True,
                "message": "Empty message ignored",
            })

        normalized_message = " ".join(message.strip().upper().split())

        is_done = normalized_message == "DONE"
        is_activation = normalized_message == "TALK TO ASSISTANT"

        # --------------------------------------------------
        # Resolve WhatsApp LID to the real phone number
        # --------------------------------------------------

        phone_url = (
            f"{settings.OPENWA_BASE_URL}"
            f"/api/sessions/{settings.OPENWA_SESSION_ID}"
            f"/contacts/{sender}/phone"
        )

        headers = {
            "X-API-Key": settings.OPENWA_API_KEY,
        }

        from .contact_relay import ContactNotAuthorized

        try:
            if getattr(
                settings, "OPENWA_CONTACT_RELAY_URL", ""
            ):
                from .contact_relay import resolve_contact_via_relay

                phone_data = resolve_contact_via_relay(sender)
            else:
                phone_response = requests.get(
                    phone_url,
                    headers=headers,
                    timeout=15,
                )

                logger.info(
                    "OpenWA contact lookup completed with HTTP %s.",
                    phone_response.status_code,
                )

                phone_response.raise_for_status()
                phone_data = phone_response.json()

            if not isinstance(phone_data, dict):
                raise ValueError("OpenWA returned an invalid contact response")

            raw_phone_number = phone_data.get("phone")

            if not isinstance(raw_phone_number, str):
                raise ValueError("OpenWA returned an invalid phone number")

            phone_number = raw_phone_number.strip().lstrip("+")

            if not phone_number:
                raise ValueError("OpenWA returned an empty phone number")

        except ContactNotAuthorized:
            mark_whatsapp_message_processed(message_record)

            return JsonResponse({
                "received": True,
                "authorized": False,
            })

        except Exception:
            logger.exception("OpenWA contact lookup failed.")

            release_whatsapp_message_claim(message_record)

            return JsonResponse({
                "received": True,
                "processed": False,
                "message": "Contact lookup temporarily unavailable",
            }, status=502)


        if getattr(settings, "STAGING_MODE", False):
            if (
                not getattr(
                    settings,
                    "STAGING_WHATSAPP_DEMO_ENABLED",
                    False,
                )
                or phone_number != getattr(
                    settings, "DEMO_ALLOWED_PHONE", ""
                )
            ):
                mark_whatsapp_message_processed(message_record)

                return JsonResponse({
                    "received": True,
                    "authorized": False,
                })

        # Only registered patients may interact with PrepBuddy.
        patient = Patient.objects.filter(
            phone_number__in=[
                phone_number,
                f"+{phone_number}",
            ]
        ).first()

        if patient is None:
            logger.warning("Ignored an inbound message from an unregistered sender.")
            mark_whatsapp_message_processed(message_record)
            return JsonResponse({
                "received": True,
                "authorized": False,
                "message": "Sender is not a registered patient",
            })

        # Retry the acknowledgement for a reminder already confirmed
        # by this exact inbound WhatsApp message.
        if is_done and message_record.confirmed_reminder_id:
            reminder = message_record.confirmed_reminder

            # Never allow a message to acknowledge another patient's reminder.
            if reminder.procedure.patient_id != patient.id:
                logger.error(
                    "DONE message is linked to a reminder belonging to another patient."
                )
                mark_whatsapp_message_processed(message_record)
                return JsonResponse({
                    "received": True,
                    "confirmed": False,
                    "message": "Reminder ownership mismatch",
                }, status=403)

            confirmation_message = (
                "\u2705 Your preparation step has been confirmed!\n\n"
                "Thank you. PrepBuddy has recorded your confirmation."
            )

            try:
                send_openwa_message(
                    chat_id=sender,
                    text=confirmation_message,
                    dedupe_key=f"inbound:{message_record.message_id}:done_ack",
                    purpose="done_ack",
                )
            except Exception:
                logger.exception(
                    "Retry of DONE acknowledgement failed for reminder %s.",
                    reminder.id,
                )
                release_whatsapp_message_claim(message_record)

                return JsonResponse({
                    "received": True,
                    "confirmed": True,
                    "reminder_id": reminder.id,
                    "acknowledgement_sent": False,
                }, status=500)

            mark_whatsapp_message_processed(message_record)

            return JsonResponse({
                "received": True,
                "confirmed": True,
                "reminder_id": reminder.id,
                "acknowledgement_sent": True,
            })

        # Activate the assistant only for registered patients.
        if is_activation:
            session, created = WhatsAppAssistantSession.objects.get_or_create(
                patient=patient,
            )

            session.is_active = True
            session.activated_at = timezone.now()
            session.save(
                update_fields=["is_active", "activated_at", "updated_at"]
            )

            try:
                send_openwa_message(
                    chat_id=sender,
                    text=(
                        "Hello! I'm PrepBuddy, your preparation-instructions "
                        "assistant.\n\n"
                        "You can ask me questions about your stored preparation "
                        "instructions, and I'll help when a reliable answer is "
                        "available.\n\n"
                        "For medical concerns or anything unclear, please contact "
                        "your clinical team.\n\n"
                        "You can still reply DONE to confirm a preparation step."
                    ),
                    dedupe_key=f"inbound:{message_record.message_id}:activation",
                    purpose="assistant_activation",
                )
            except Exception:
                logger.exception("PrepBuddy activation message send failed.")
                release_whatsapp_message_claim(message_record)
                return JsonResponse({
                    "received": True,
                    "assistant_activated": False,
                    "error": "Activation message delivery failed; retry permitted.",
                }, status=500)

            mark_whatsapp_message_processed(message_record)

            return JsonResponse({
                "received": True,
                "assistant_activated": True,
                "session_created": created,
            })

        # Preserve DONE confirmation, even when the assistant is active.
        if is_done:
            pass
        else:
            # Only answer ordinary questions after activation.
            session = WhatsAppAssistantSession.objects.filter(
                patient=patient,
                is_active=True,
            ).first()

            if session is None:
                try:
                    send_openwa_message(
                        chat_id=sender,
                        text=(
                            "To chat with PrepBuddy, reply TALK TO ASSISTANT. "
                            "You can also reply DONE to confirm a preparation step."
                        ),
                        dedupe_key=f"inbound:{message_record.message_id}:inactive_notice",
                        purpose="inactive_notice",
                    )
                except Exception:
                    logger.exception("Inactive-session notice send failed.")
                    release_whatsapp_message_claim(message_record)
                    return JsonResponse({
                        "received": True,
                        "assistant_activated": False,
                        "error": "Notice delivery failed; retry permitted.",
                    }, status=500)

                mark_whatsapp_message_processed(message_record)

                return JsonResponse({
                    "received": True,
                    "assistant_activated": False,
                })

            # Load prior messages before saving the current question.
            history = get_recent_conversation(session)

            # Save the incoming question for this activated session.
            patient_message = save_conversation_message(
                session=session,
                role="patient",
                content=message,
            )

            # Tone/intent analysis is best-effort and must never interrupt
            # the established clinical-safety and RAG response path.
            communication_style = "neutral"
            requires_human = False
            try:
                analysis = analyze_patient_message(message)
                analysis_record, _created = (
                    WhatsAppMessageAnalysis.objects.update_or_create(
                        message=patient_message,
                        defaults=analysis,
                    )
                )
                communication_style = select_communication_style(
                    sentiment=getattr(analysis_record, "sentiment", "neutral"),
                    emotion=getattr(analysis_record, "emotion", "calm"),
                )
                requires_human = bool(
                    getattr(analysis_record, "requires_human", False)
                    or getattr(analysis_record, "intent", "") == "clinical_concern"
                )
            except Exception:
                logger.exception(
                    "Patient message analysis failed; continuing with normal "
                    "PrepBuddy response."
                )

            normalized_for_help = " ".join(
                message.lower().strip().split()
            )

            is_general_help = (
                normalized_for_help in {
                    "hi",
                    "hello",
                    "hey",
                    "hi prepbuddy",
                    "hello prepbuddy",
                    "hey prepbuddy",
                    "what can you help me with",
                    "what can you help me with?",
                    "what can you do",
                    "what do you do",
                    "help",
                    "help me",
                }
                or "what can you help me with" in normalized_for_help
                or "what can you do" in normalized_for_help
                or "what do you do" in normalized_for_help
            )

            reply_send_started = False
            try:
                procedure = (
                    Procedure.objects
                    .filter(
                        patient=patient,
                        status__in=[
                            "prep_in_progress",
                            "attention_needed",
                        ],
                    )
                    .select_related("protocol")
                    .order_by("scheduled_at")
                    .first()
                )

                if procedure is None:
                    procedure = (
                        Procedure.objects
                        .filter(
                            patient=patient,
                            status="scheduled",
                            scheduled_at__gte=timezone.now(),
                        )
                        .select_related("protocol")
                        .order_by("scheduled_at")
                        .first()
                    )

                escalation = safety_response(
                    message,
                    requires_human=requires_human,
                )
                from django.conf import settings as assistant_settings

                if (
                    escalation is None
                    and getattr(
                        assistant_settings,
                        "CHATBOT_BACKEND",
                        "rag",
                    ) in ("ann", "remote_ann")
                ):
                    from chatbot.ann.multilingual_safety import (
                        multilingual_safety_response,
                    )

                    escalation = multilingual_safety_response(message)

                if escalation is not None:
                    result = escalation
                elif procedure is None and not is_general_help:
                    result = {
                        "answer": (    "I couldn't identify an upcoming procedure linked to your "    "patient record. Please contact your care team to confirm "    "your procedure details before relying on preparation advice."),
                        "sources": [],
                        "needs_clinical_team": True,
                    }
                elif is_general_help:
                    result = answer_question(
                        message,
                        communication_style=communication_style,
                        requires_human=requires_human,
                    )
                else:
                    resolved_question = resolve_followup_question(
                        message,
                        history,
                    )

                    clarification_question = (
                        resolved_question
                        if resolved_question is not None
                        else message
                    )

                    clarification = assess_clarification(
                        clarification_question,
                        history=history,
                        active_protocol_id=procedure.protocol_id,
                    )

                    if clarification["required"]:
                        result = {
                            "answer": clarification["message"],
                            "sources": [],
                            "needs_clinical_team": (
                                clarification["kind"] == "procedure_mismatch"
                            ),
                        }

                    elif resolved_question is not None:
                        result = answer_question(
                            resolved_question,
                            protocol_id=procedure.protocol_id,
                            communication_style=communication_style,
                            requires_human=requires_human,
                        )

                    elif is_context_dependent_followup(message):
                        result = {
                            "answer": (
                                "I'm not sure which preparation instruction you're "
                                "referring to. Please check your official preparation "
                                "instructions or contact your clinical team for "
                                "clarification."
                            ),
                            "sources": [],
                            "needs_clinical_team": True,
                        }

                    else:
                        result = answer_question(
                            message,
                            protocol_id=procedure.protocol_id,
                            communication_style=communication_style,
                            requires_human=requires_human,
                        )
                from .assistant_formatting import format_assistant_reply

                answer = format_assistant_reply(result)

                reply_send_started = True

                send_openwa_message(
                    chat_id=sender,
                    text=answer,
                    dedupe_key=f"inbound:{message_record.message_id}:assistant_answer",
                    purpose="assistant_answer",
                )

                # Persist the reply after OpenWA accepts the send operation.
                try:
                    save_conversation_message(
                        session=session,
                        role="assistant",
                        content=answer,
                    )
                except Exception as history_error:
                    # A history-write failure should not cause a second reply to be sent.
                    logger.warning(
                        "Assistant reply history persistence failed after send."
                    )

                mark_whatsapp_message_processed(message_record)

                return JsonResponse({
                    "received": True,
                    "answered": True,
                    "needs_clinical_team": result.get(
                        "needs_clinical_team", False
                    ),
                })

            except Exception:
                logger.exception("Inbound WhatsApp question processing failed.")

                if reply_send_started:
                    # Delivery may already have occurred. Never send a
                    # second message with a different deduplication key.
                    release_whatsapp_message_claim(message_record)

                    return JsonResponse({
                        "received": True,
                        "answered": False,
                        "delivery_uncertain": True,
                        "fallback": False,
                    }, status=503)

                try:
                    send_openwa_message(
                        chat_id=sender,
                        text=(
                            "I'm having trouble checking the stored preparation "
                            "instructions right now. Please consult your official "
                            "instructions or contact your clinical team."
                        ),
                        dedupe_key=f"inbound:{message_record.message_id}:assistant_fallback",
                        purpose="assistant_fallback",
                    )
                    mark_whatsapp_message_processed(message_record)

                    return JsonResponse({
                        "received": True,
                        "answered": False,
                        "fallback": True,
                    })

                except Exception as send_error:
                    logger.error("WhatsApp fallback response could not be sent.")
                    release_whatsapp_message_claim(message_record)

                    return JsonResponse({
                        "received": True,
                        "answered": False,
                        "fallback": False,
                        "error": "Could not send fallback message",
                    }, status=500)

        # --------------------------------------------------
        # Find the patient's latest sent reminder
        # --------------------------------------------------

        reminder = (
            Reminder.objects
            .filter(
                status="sent",
                procedure__patient=patient,
                confirmed_at__isnull=True,
            )
            .select_related(
                "procedure",
                "procedure__patient",
                "prep_step",
            )
            .order_by("-sent_at", "-scheduled_at")
            .first()
        )

        if not reminder:
            logger.info("No unconfirmed sent reminder matched an inbound DONE reply.")

            mark_whatsapp_message_processed(message_record)

            return JsonResponse({
                "received": True,
                "confirmed": False,
                "message": "No pending reminder found",
            })

        # --------------------------------------------------
        # Confirm reminder
        # --------------------------------------------------

        with transaction.atomic():
            confirmed_at = timezone.now()

            updated = Reminder.objects.filter(
                pk=reminder.pk,
                status="sent",
                confirmed_at__isnull=True,
            ).update(
                status="confirmed",
                confirmed_at=confirmed_at,
            )

            if updated == 1:
                message_record.confirmed_reminder = reminder
                message_record.save(update_fields=["confirmed_reminder"])

        if updated != 1:
            logger.info(
                "Reminder %s was no longer eligible when DONE confirmation was applied.",
                reminder.id,
            )
            mark_whatsapp_message_processed(message_record)

            return JsonResponse({
                "received": True,
                "confirmed": False,
                "message": "No pending reminder found",
            })

        reminder.status = "confirmed"
        reminder.confirmed_at = confirmed_at
        confirmation_message = (
            "\u2705 Your preparation step has been confirmed!\n\n"
            "Thank you. PrepBuddy has recorded your confirmation."
        )

        # Send confirmation back to the actual WhatsApp chat.
        # The reminder is already confirmed in the database.
        try:
            send_openwa_message(
                chat_id=sender,
                text=confirmation_message,
                dedupe_key=f"inbound:{message_record.message_id}:done_ack",
                purpose="done_ack",
            )
        except Exception:
            release_whatsapp_message_claim(message_record)

            return JsonResponse({
                "received": True,
                "confirmed": True,
                "reminder_id": reminder.id,
                "acknowledgement_sent": False,
            }, status=500)

        logger.info("Reminder %s was confirmed by an inbound DONE reply.", reminder.id)
        mark_whatsapp_message_processed(message_record)

        return JsonResponse({
            "received": True,
            "confirmed": True,
            "reminder_id": reminder.id,
        })

    except json.JSONDecodeError:

        return JsonResponse({
            "error": "Invalid JSON"
        }, status=400)

    except Exception:
        # Release an unfinished inbound claim so OpenWA can safely retry.
        release_whatsapp_message_claim(message_record)

        # Do not return provider/database exception text to the public caller.
        logger.exception("OpenWA webhook processing failed.")
        return JsonResponse({
            "error": "Webhook processing failed"
        }, status=500)

@csrf_exempt
def openwa_relay_send_text(request):
    """Authenticated local relay from Render to the local OpenWA instance."""

    if getattr(settings, "STAGING_MODE", False):
        return JsonResponse(
            {"error": "Not found"},
            status=404,
        )


    if request.method != "POST":
        return JsonResponse(
            {"error": "POST request required"},
            status=405,
        )

    proxy_token = settings.OPENWA_PROXY_TOKEN
    if not proxy_token:
        logger.error("OpenWA relay proxy token is not configured.")
        return JsonResponse(
            {"error": "Relay authentication is not configured"},
            status=503,
        )

    received_token = request.headers.get("X-Proxy-Token", "")
    if not hmac.compare_digest(received_token, proxy_token):
        logger.warning("OpenWA relay rejected: invalid proxy token.")
        return JsonResponse(
            {"error": "Invalid relay authentication"},
            status=401,
        )

    max_body_size = 64 * 1024

    content_length = request.META.get("CONTENT_LENGTH")
    if content_length:
        try:
            if int(content_length) > max_body_size:
                return JsonResponse(
                    {"error": "Request body too large"},
                    status=413,
                )
        except ValueError:
            return JsonResponse(
                {"error": "Invalid Content-Length"},
                status=400,
            )

    if request.content_type != "application/json":
        return JsonResponse(
            {"error": "Content-Type must be application/json"},
            status=415,
        )

    body = request.body
    if len(body) > max_body_size:
        return JsonResponse(
            {"error": "Request body too large"},
            status=413,
        )

    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"error": "Invalid JSON"},
            status=400,
        )

    if not isinstance(payload, dict) or set(payload) != {"chatId", "text"}:
        return JsonResponse(
            {"error": "Expected exactly chatId and text fields"},
            status=400,
        )

    chat_id = payload["chatId"]
    message_text = payload["text"]

    if (
        not isinstance(chat_id, str)
        or not chat_id.strip()
        or len(chat_id) > 256
    ):
        return JsonResponse(
            {"error": "Invalid chatId"},
            status=400,
        )

    if (
        not isinstance(message_text, str)
        or not message_text.strip()
        or len(message_text) > 16000
    ):
        return JsonResponse(
            {"error": "Invalid text"},
            status=400,
        )

    idempotency_key = request.headers.get("Idempotency-Key", "")
    try:
        from uuid import UUID

        idempotency_key = str(UUID(idempotency_key))
    except (ValueError, AttributeError, TypeError):
        return JsonResponse(
            {"error": "A valid UUID Idempotency-Key is required"},
            status=400,
        )

    api_key = settings.OPENWA_API_KEY
    if not api_key:
        logger.error("Local OpenWA API key is not configured.")
        return JsonResponse(
            {"error": "OpenWA authentication is not configured"},
            status=503,
        )

    session_id = str(settings.OPENWA_SESSION_ID)
    if not session_id:
        logger.error("Local OpenWA session ID is not configured.")
        return JsonResponse(
            {"error": "OpenWA session is not configured"},
            status=503,
        )

    from urllib.parse import quote

    url = (
        f"{settings.OPENWA_BASE_URL}"
        f"/api/sessions/{quote(session_id, safe='')}"
        f"/messages/send-text"
    )

    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
        "Idempotency-Key": idempotency_key,
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json={
                "chatId": chat_id,
                "text": message_text,
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        logger.warning(
            "OpenWA relay upstream request failed (%s).",
            type(exc).__name__,
        )
        return JsonResponse(
            {"error": "OpenWA temporarily unavailable"},
            status=502,
        )

    return HttpResponse(
        response.content,
        status=response.status_code,
        content_type="application/json",
    )
