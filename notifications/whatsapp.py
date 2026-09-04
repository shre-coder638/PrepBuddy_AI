import re

import requests
from django.conf import settings


def normalize_phone_number(phone_number):
    return re.sub(r"\D", "", phone_number)


def send_whatsapp_template(
    phone_number,
    patient_name,
    procedure_name,
    preparation_step,
    instructions,
):
    phone_number = normalize_phone_number(phone_number)

    url = (
        f"https://graph.facebook.com/"
        f"{settings.WHATSAPP_API_VERSION}/"
        f"{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    )

    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "template",
        "template": {
            "name": "prepbuddy_reminder",
            "language": {
                "code": "en_IN"
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {
                            "type": "text",
                            "text": patient_name,
                        },
                        {
                            "type": "text",
                            "text": procedure_name,
                        },
                        {
                            "type": "text",
                            "text": preparation_step,
                        },
                        {
                            "type": "text",
                            "text": instructions,
                        },
                    ],
                }
            ],
        },
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=15,
    )

    print("WhatsApp status:", response.status_code)
    print("WhatsApp response:", response.text)

    response.raise_for_status()

    return response.json()