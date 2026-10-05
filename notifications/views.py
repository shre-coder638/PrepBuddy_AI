import json

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from reminders.models import Reminder
from .whatsapp import send_whatsapp_message
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from reminders.models import Reminder


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

        if event != "message.received":
            return JsonResponse({
                "received": True,
                "ignored": True
            })

        sender = data.get("from")
        message = data.get("body", "").strip()

        print(f"Sender: {sender}")
        print(f"Message: {message}")

        # Only process DONE
        if message.upper() != "DONE":
            return JsonResponse({
                "received": True,
                "message": "Message ignored"
            })

        # Find the latest reminder that is waiting for confirmation
        reminder = (
            Reminder.objects
            .filter(status="sent")
            .order_by("-scheduled_at")
            .first()
        )

        if not reminder:
            print("⚠️ No sent reminder found.")

            return JsonResponse({
                "received": True,
                "confirmed": False,
                "message": "No pending reminder found"
            })

        # Confirm the reminder
        reminder.status = "confirmed"
        reminder.confirmed_at = timezone.now()
        reminder.save(
            update_fields=[
                "status",
                "confirmed_at"
            ]
        )

        print(
            f"✅ Reminder #{reminder.id} confirmed!"
        )

        return JsonResponse({
            "received": True,
            "confirmed": True,
            "reminder_id": reminder.id
        })

    except json.JSONDecodeError:

        return JsonResponse({
            "error": "Invalid JSON"
        }, status=400)

    except Exception as e:

        print(f"❌ OpenWA webhook error: {e}")

        return JsonResponse({
            "error": str(e)
        }, status=500)