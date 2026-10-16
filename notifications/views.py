import json
import requests

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from reminders.models import Reminder
from .whatsapp import send_openwa_message


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

        if not isinstance(data, dict):
            return JsonResponse(
                {"error": "Invalid event data"},
                status=400,
            )

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
                print(
                    "No reminder matches OpenWA message ID:",
                    message_id,
                )
                return JsonResponse({
                    "received": True,
                    "updated": False,
                    "reason": "Message ID not found",
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

        # Only process DONE
        if message.upper() != "DONE":
            return JsonResponse({
                "received": True,
                "message": "Message ignored"
            })

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

        # --------------------------------------------------
        # Find the patient's latest sent reminder
        # --------------------------------------------------

        reminder = (
            Reminder.objects
            .filter(
                status="sent",
                procedure__patient__phone_number__in=[
                    phone_number,
                    f"+{phone_number}",
                ],
            )
            .select_related(
                "procedure",
                "procedure__patient",
                "prep_step",
            )
            .order_by("-scheduled_at")
            .first()
        )

        if not reminder:

            print(
                f"⚠️ No sent reminder found for "
                f"phone {phone_number}"
            )

            return JsonResponse({
                "received": True,
                "confirmed": False,
                "message": "No pending reminder found"
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

        # Send confirmation back to the actual WhatsApp chat
        send_openwa_message(
            sender,
            confirmation_message
        )

        print(
            f"✅ Reminder #{reminder.id} confirmed!"
        )

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
