from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import json


@csrf_exempt
def whatsapp_webhook(request):
    # Meta webhook verification
    if request.method == "GET":
        verify_token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        if verify_token == settings.WHATSAPP_VERIFY_TOKEN:
            return JsonResponse(
                int(challenge),
                safe=False
            )

        return JsonResponse(
            {"error": "Invalid verify token"},
            status=403
        )

    # Incoming WhatsApp messages
    if request.method == "POST":
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse(
                {"error": "Invalid JSON"},
                status=400
            )

        print("📩 WhatsApp webhook received:")
        print(json.dumps(data, indent=2))

        return JsonResponse({"status": "received"})

    return JsonResponse(
        {"error": "Method not allowed"},
        status=405
    )