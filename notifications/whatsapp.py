import requests

from django.conf import settings


def send_openwa_message(chat_id, text):
    """
    Send a WhatsApp text message through OpenWA.
    """

    if not settings.WHATSAPP_SEND_ENABLED:
        raise RuntimeError(
            "WhatsApp sending is disabled by configuration."
        )

    url = (
        f"{settings.OPENWA_BASE_URL}"
        f"/api/sessions/{settings.OPENWA_SESSION_ID}"
        f"/messages/send-text"
    )

    headers = {
        "X-API-Key": settings.OPENWA_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "chatId": chat_id,
        "text": text,
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=15,
    )

    print(
        "OpenWA send response:",
        response.status_code,
        response.text,
    )

    response.raise_for_status()

    return response.json()



def send_whatsapp_template(
    phone_number,
    patient_name,
    procedure_name,
    preparation_step,
    instructions,
):
    """Send a PrepBuddy reminder through OpenWA."""

    phone = str(phone_number).strip()

    if phone.startswith("+"):
        phone = phone[1:]

    chat_id = f"{phone}@c.us"

    message = (
        f"👋 Hello {patient_name}!\n\n"
        f"🔔 PrepBuddy Reminder\n\n"
        f"Procedure: {procedure_name}\n\n"
        f"Preparation step:\n"
        f"{preparation_step}\n\n"
        f"Instructions:\n"
        f"{instructions}\n\n"
        f"Please complete this step and reply DONE when finished."
    )

    result = send_openwa_message(
        chat_id=chat_id,
        text=message,
    )

    if not isinstance(result, dict):
        raise RuntimeError(
            "OpenWA returned an unexpected response format."
        )

    # Check explicit failure indicators if the API provides them.
    if result.get("success") is False or result.get("sent") is False:
        raise RuntimeError(f"OpenWA reported delivery failure: {result}")

    return result
