from django.conf import settings
from twilio.rest import Client


def normalize_phone_number(phone_number):
    phone_number = "".join(
        character for character in str(phone_number)
        if character.isdigit() or character == "+"
    )

    if not phone_number.startswith("+"):
        phone_number = "+" + phone_number

    return phone_number


def get_twilio_client():
    return Client(
        settings.TWILIO_ACCOUNT_SID,
        settings.TWILIO_AUTH_TOKEN,
    )


def send_whatsapp_message(phone_number, message):
    phone_number = normalize_phone_number(phone_number)

    client = get_twilio_client()

    result = client.messages.create(
        from_=settings.TWILIO_WHATSAPP_FROM,
        to=f"whatsapp:{phone_number}",
        body=message,
    )

    print("WhatsApp message SID:", result.sid)
    print("WhatsApp message status:", result.status)

    return result


def send_whatsapp_template(
    phone_number,
    patient_name,
    procedure_name,
    preparation_step,
    instructions,
):
    message = (
        f"Hi {patient_name},\n\n"
        f"This is a PrepBuddy reminder for your "
        f"{procedure_name}.\n\n"
        f"Preparation step:\n"
        f"{preparation_step}\n\n"
        f"Instructions:\n"
        f"{instructions}\n\n"
        f"Please complete this step and reply DONE when "
        f"you are finished."
    )

    return send_whatsapp_message(
        phone_number,
        message,
    )