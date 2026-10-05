from django.conf import settings
from twilio.rest import Client

from .whatsapp import normalize_phone_number


def send_sms(phone_number, message):
    phone_number = normalize_phone_number(phone_number)

    if not settings.TWILIO_SMS_FROM:
        raise ValueError(
            "TWILIO_SMS_FROM is not configured."
        )

    client = Client(
        settings.TWILIO_ACCOUNT_SID,
        settings.TWILIO_AUTH_TOKEN,
    )

    result = client.messages.create(
        from_=settings.TWILIO_SMS_FROM,
        to=phone_number,
        body=message,
    )

    print("SMS message SID:", result.sid)
    print("SMS message status:", result.status)

    return result