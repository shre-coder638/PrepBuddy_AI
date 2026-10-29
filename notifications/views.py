import json
import requests

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from chatbot.views import answer_question
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

from .whatsapp import send_openwa_message
from .models import WhatsAppAssistantSession, ProcessedWhatsAppMessage

def mark_whatsapp_message_processed(message_record):
    if message_record is not None:
        message_record.is_processed = True
        message_record.processed_at = timezone.now()
        message_record.processing_started_at = None
        message_record.save(
            update_fields=[
                "is_processed",
                "processed_at",
                "processing_started_at",
            ]
        )

def release_whatsapp_message_claim(message_record):
    if message_record is not None and not message_record.is_processed:
        message_record.processing_started_at = None
        message_record.save(
            update_fields=["processing_started_at"]
        )

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

def claim_whatsapp_message(message_id):
    """
    Claim a message once. Claims older than five minutes can be retried.
    Returns (record, claimed).
    """
    lease_timeout = timedelta(minutes=5)
    current_time = timezone.now()

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

    try:
        payload = json.loads(request.body)

        print("\n📩 OpenWA webhook received:")
        print(json.dumps(payload, indent=2))

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
                print("Incoming OpenWA message has no message ID.")
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
            message_id = (
                data.get("messageId")
                or data.get("id")
            )

            raw_status = (
                "failed"
                if event == "message.failed"
                else data.get("status", data.get("ack"))
            )

            if not message_id:
                print("OpenWA acknowledgement has no message ID.")
                return JsonResponse({
                    "received": True,
                    "updated": False,
                    "reason": "Missing message ID",
                })

            if isinstance(raw_status, str):
                delivery_status = raw_status.strip().lower()
            else:
                delivery_status = None

            allowed_statuses = {
                "sent",
                "delivered",
                "read",
                "failed",
            }

            if delivery_status not in allowed_statuses:
                print(
                    "Unrecognized OpenWA acknowledgement status:",
                    raw_status,
                )
                return JsonResponse({
                    "received": True,
                    "updated": False,
                    "reason": "Unrecognized delivery status",
                })

            reminder = Reminder.objects.filter(
                openwa_message_id=str(message_id),
            ).first()

            if reminder is None:
                return JsonResponse({
                    "received": True,
                    "updated": False,
                    "ignored": True,
                    "reason": "Not a scheduled reminder message",
                })

            # Avoid regressing a known delivery state if events arrive
            # out of order. A late failure must not undo delivery/read.
            status_rank = {
                "pending": 0,
                "accepted": 1,
                "sent": 2,
                "delivered": 3,
                "read": 4,
            }

            current_status = reminder.delivery_status

            if (
                current_status in ("delivered", "read")
                and delivery_status == "failed"
            ):
                print(
                    "Ignoring late failure for already delivered/read "
                    f"reminder #{reminder.id}."
                )
                return JsonResponse({
                    "received": True,
                    "updated": False,
                    "reason": "Existing delivery state takes precedence",
                })

            if (
                delivery_status in status_rank
                and current_status in status_rank
                and status_rank[delivery_status] < status_rank[current_status]
            ):
                return JsonResponse({
                    "received": True,
                    "updated": False,
                    "reason": "Stale acknowledgement",
                })

            if reminder.delivery_status != delivery_status:
                reminder.delivery_status = delivery_status
                reminder.save(update_fields=["delivery_status"])

            print(
                f"Reminder #{reminder.id} delivery status: "
                f"{delivery_status}"
            )

            return JsonResponse({
                "received": True,
                "updated": True,
                "reminder_id": reminder.id,
                "delivery_status": delivery_status,
            })

        # Keep the existing inbound DONE handler unchanged.
        if event != "message.received":
            return JsonResponse({
                "received": True,
                "ignored": True,
            })

        sender = data.get("from", "").strip()
        message = data.get("body", "").strip()

        print(f"Sender: {sender}")
        print(f"Message: {message}")

        # Accept DONE confirmations and ordinary patient questions.
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

        phone_response = requests.get(
            phone_url,
            headers=headers,
            timeout=15,
        )

        print(
            "OpenWA phone lookup:",
            phone_response.status_code,
            phone_response.text
        )

        phone_response.raise_for_status()

        phone_data = phone_response.json()

        phone_number = str(
            phone_data.get("phone", "")
        ).strip()

        # Remove + if OpenWA ever returns it
        phone_number = phone_number.lstrip("+")

        print(
            f"Resolved patient phone: {phone_number}"
        )

        if not phone_number:
            return JsonResponse({
                "received": True,
                "confirmed": False,
                "message": "Could not resolve WhatsApp phone number"
            })

        # Only registered patients may interact with PrepBuddy.
        patient = Patient.objects.filter(
            phone_number__in=[
                phone_number,
                f"+{phone_number}",
            ]
        ).first()

        if patient is None:
            print(
                "Ignoring WhatsApp message from an unregistered number."
            )
            mark_whatsapp_message_processed(message_record)
            return JsonResponse({
                "received": True,
                "authorized": False,
                "message": "Sender is not a registered patient",
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

            send_openwa_message(
                sender,
                "Hello! I'm PrepBuddy, your preparation-instructions "
                "assistant.\n\n"
                "You can ask me questions about your stored preparation "
                "instructions, and I'll help when a reliable answer is "
                "available.\n\n"
                "For medical concerns or anything unclear, please contact "
                "your clinical team.\n\n"
                "You can still reply DONE to confirm a preparation step."
            )
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
                send_openwa_message(
                    sender,
                    "To chat with PrepBuddy, reply TALK TO ASSISTANT. "
                    "You can also reply DONE to confirm a preparation step."
                )
                mark_whatsapp_message_processed(message_record)

                return JsonResponse({
                    "received": True,
                    "assistant_activated": False,
                })

            # Load prior messages before saving the current question.
            history = get_recent_conversation(session)

            # Save the incoming question for this activated session.
            save_conversation_message(
                session=session,
                role="patient",
                content=message,
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

                if procedure is None and not is_general_help:
                    result = {
                        "answer": (    "I couldn't identify an upcoming procedure linked to your "    "patient record. Please contact your care team to confirm "    "your procedure details before relying on preparation advice."),
                        "sources": [],
                        "needs_clinical_team": True,
                    }
                elif is_general_help:
                    result = answer_question(message)
                else:
                    resolved_question = resolve_followup_question(
                        message,
                        history,
                    )

                    if resolved_question is not None:
                        result = answer_question(
                            resolved_question,
                            protocol_id=procedure.protocol_id,
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
                        )
                answer = result.get("answer", "")
                if not isinstance(answer, str) or not answer.strip():
                    answer = (
                        "I couldn't find a reliable answer in your stored "
                        "preparation instructions. Please check your official "
                        "instructions or contact your clinical team."
                    )

                sources = result.get("sources", [])
                if sources:
                    source = sources[0]
                    step = source.get("step")
                    if step and step not in answer:
                        answer = f"{answer}\n\nPreparation step: {step}"

                send_openwa_message(sender, answer)

                # Persist the reply after OpenWA accepts the send operation.
                try:
                    save_conversation_message(
                        session=session,
                        role="assistant",
                        content=answer,
                    )
                except Exception as history_error:
                    # A history-write failure should not cause a second reply to be sent.
                    print(
                        "Could not save PrepBuddy assistant reply to conversation history: "
                        f"{history_error}"
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
                print("Could not answer inbound WhatsApp question.")

                try:
                    send_openwa_message(
                        sender,
                        "I'm having trouble checking the stored preparation "
                        "instructions right now. Please consult your official "
                        "instructions or contact your clinical team.",
                    )
                    mark_whatsapp_message_processed(message_record)

                    return JsonResponse({
                        "received": True,
                        "answered": False,
                        "fallback": True,
                    })

                except Exception as send_error:
                    print(
                        f"Could not send WhatsApp fallback: {send_error}"
                    )
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
            print(
                f"No sent reminder found for phone {phone_number}"
            )

            mark_whatsapp_message_processed(message_record)

            return JsonResponse({
                "received": True,
                "confirmed": False,
                "message": "No pending reminder found",
            })

        # --------------------------------------------------
        # Confirm reminder
        # --------------------------------------------------

        reminder.status = "confirmed"
        reminder.confirmed_at = timezone.now()

        reminder.save(
            update_fields=[
                "status",
                "confirmed_at",
            ]
        )

        confirmation_message = (
            "✅ Your preparation step has been confirmed!\n\n"
            "Thank you. PrepBuddy has recorded your confirmation."
        )

        # Send confirmation back to the actual WhatsApp chat.
        # The reminder is already confirmed in the database.
        try:
            send_openwa_message(
                sender,
                confirmation_message,
            )
        except Exception as send_error:
            print(
                f"Could not send confirmation for reminder "
                f"#{reminder.id}: {send_error}"
            )

            return JsonResponse({
                "received": True,
                "confirmed": True,
                "reminder_id": reminder.id,
                "acknowledgement_sent": False,
            }, status=500)

        print(
            f"✅ Reminder #{reminder.id} confirmed!"
        )
        mark_whatsapp_message_processed(message_record)

        return JsonResponse({
            "received": True,
            "confirmed": True,
            "reminder_id": reminder.id,
            "patient_phone": phone_number,
        })

    except json.JSONDecodeError:

        return JsonResponse({
            "error": "Invalid JSON"
        }, status=400)

    except Exception as e:

        print(
            f"❌ OpenWA webhook error: {e}"
        )

        return JsonResponse({
            "error": str(e)
        }, status=500)
