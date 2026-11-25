
import hashlib
import json
from datetime import timedelta

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import F, Q, Case, When, Value, DateTimeField
from django.utils import timezone

from .models import WhatsAppOutboundMessage


OUTBOUND_LEASE_SECONDS = 45
OPENWA_IDEMPOTENCY_WINDOW = timedelta(hours=23, minutes=50)


class WhatsAppOutboundError(RuntimeError):
    """Base exception for durable outbound WhatsApp sends."""


class WhatsAppSendInProgress(WhatsAppOutboundError):
    """Another worker currently owns the outbound send lease."""


class WhatsAppPayloadConflict(WhatsAppOutboundError):
    """A deduplication key was reused for a different recipient or purpose."""


class WhatsAppIdempotencyExpired(WhatsAppOutboundError):
    """The safe OpenWA idempotency retry window has expired."""


def _payload_hash(session_id, chat_id, text):
    canonical = json.dumps(
        {
            "session_id": session_id,
            "chat_id": chat_id,
            "text": text,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _get_or_create_outbound(*, dedupe_key, purpose, chat_id, text):
    session_id = str(settings.OPENWA_SESSION_ID)
    digest = _payload_hash(session_id, chat_id, text)

    outbound, created = WhatsAppOutboundMessage.objects.get_or_create(
        dedupe_key=dedupe_key,
        defaults={
            "purpose": purpose,
            "openwa_session_id": session_id,
            "chat_id": chat_id,
            "message_text": text,
            "payload_sha256": digest,
        },
    )

    if (
        outbound.purpose != purpose
        or outbound.openwa_session_id != session_id
        or outbound.chat_id != chat_id
    ):
        raise WhatsAppPayloadConflict(
            "The outbound deduplication key belongs to a different send."
        )

    stored_digest = _payload_hash(
        outbound.openwa_session_id,
        outbound.chat_id,
        outbound.message_text,
    )
    if stored_digest != outbound.payload_sha256:
        raise WhatsAppOutboundError(
            "The stored outbound message failed its integrity check."
        )

    # Deliberately do not compare or replace the caller's text here.
    # A retry must use the original persisted message, not regenerated text.
    return outbound


def _claim_outbound(outbound_id):
    now = timezone.now()
    lease_until = now + timedelta(seconds=OUTBOUND_LEASE_SECONDS)

    outbound = WhatsAppOutboundMessage.objects.get(pk=outbound_id)

    if outbound.status == "accepted":
        return "accepted", None

    if outbound.status in {"failed", "expired"}:
        raise WhatsAppOutboundError(
            f"Outbound message is not retryable (status={outbound.status})."
        )

    if (
        outbound.first_attempt_at
        and now - outbound.first_attempt_at >= OPENWA_IDEMPOTENCY_WINDOW
    ):
        expired = WhatsAppOutboundMessage.objects.filter(
            pk=outbound_id,
            status__in=["pending", "sending", "unknown"],
            first_attempt_at=outbound.first_attempt_at,
        ).filter(
            Q(lease_until__isnull=True) | Q(lease_until__lte=now)
        ).update(
            status="expired",
            lease_until=None,
            last_error="OpenWA idempotency retry window expired.",
        )

        if expired == 1:
            raise WhatsAppIdempotencyExpired(
                "The safe OpenWA idempotency retry window has expired."
            )

        outbound.refresh_from_db()

        if outbound.status == "accepted":
            return "accepted", None

        if outbound.status in {"failed", "expired"}:
            raise WhatsAppOutboundError(
                f"Outbound message is not retryable (status={outbound.status})."
            )

    if (
        outbound.status == "sending"
        and outbound.lease_until
        and outbound.lease_until > now
    ):
        raise WhatsAppSendInProgress(
            "This outbound message is already being sent."
        )

    updated = WhatsAppOutboundMessage.objects.filter(
        pk=outbound_id,
        status__in=["pending", "sending", "unknown"],
    ).filter(
        Q(lease_until__isnull=True) | Q(lease_until__lte=now)
    ).update(
        status="sending",
        lease_until=lease_until,
        attempts=F("attempts") + 1,
        first_attempt_at=Case(
            When(first_attempt_at__isnull=True, then=Value(now)),
            default=F("first_attempt_at"),
            output_field=DateTimeField(),
        ),
        last_attempt_at=now,
        last_error="",
    )

    if updated != 1:
        outbound.refresh_from_db()

        if outbound.status == "accepted":
            return "accepted", None

        raise WhatsAppSendInProgress(
            "This outbound message could not be claimed."
        )

    # The lease timestamp is this worker's fencing token.
    return "claimed", lease_until


def _mark_outbound_unknown(outbound_id, claim_lease, error):
    retry_after = timezone.now() + timedelta(
        seconds=OUTBOUND_LEASE_SECONDS
    )

    updated = WhatsAppOutboundMessage.objects.filter(
        pk=outbound_id,
        status="sending",
        lease_until=claim_lease,
    ).update(
        status="unknown",
        lease_until=retry_after,
        last_error=str(error)[:2000],
    )

    return updated == 1


def _mark_outbound_failed(outbound_id, claim_lease, error):
    updated = WhatsAppOutboundMessage.objects.filter(
        pk=outbound_id,
        status="sending",
        lease_until=claim_lease,
    ).update(
        status="failed",
        lease_until=None,
        last_error=str(error)[:2000],
    )

    return updated == 1


def send_openwa_message(*, chat_id, text, dedupe_key, purpose):
    """Send one durable, idempotent WhatsApp message through OpenWA."""

    if not settings.WHATSAPP_SEND_ENABLED:
        raise RuntimeError(
            "WhatsApp sending is disabled by configuration."
        )

    if not dedupe_key or not purpose:
        raise ValueError("dedupe_key and purpose are required.")

    outbound = _get_or_create_outbound(
        dedupe_key=dedupe_key,
        purpose=purpose,
        chat_id=chat_id,
        text=text,
    )

    claim_result, claim_lease = _claim_outbound(outbound.pk)

    if claim_result == "accepted":
        return {
            "success": True,
            "sent": True,
            "messageId": outbound.openwa_message_id or None,
            "outbox_id": str(outbound.pk),
            "replayed": True,
        }

    relay_url = getattr(settings, "OPENWA_RELAY_URL", "").strip()

    if relay_url:
        proxy_token = getattr(settings, "OPENWA_PROXY_TOKEN", "")
        if not proxy_token:
            _mark_outbound_failed(
                outbound.pk,
                claim_lease,
                "OpenWA relay is configured but its proxy token is missing.",
            )
            raise WhatsAppOutboundError(
                "OpenWA relay authentication is not configured."
            )

        url = relay_url
        headers = {
            "X-Proxy-Token": proxy_token,
            "Content-Type": "application/json",
            "Idempotency-Key": str(outbound.pk),
        }
    else:
        url = (
            f"{settings.OPENWA_BASE_URL}"
            f"/api/sessions/{outbound.openwa_session_id}"
            f"/messages/send-text"
        )

        headers = {
            "X-API-Key": settings.OPENWA_API_KEY,
            "Content-Type": "application/json",
            "Idempotency-Key": str(outbound.pk),
        }

    payload = {
        "chatId": outbound.chat_id,
        "text": outbound.message_text,
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=15,
        )
    except requests.RequestException as exc:
        _mark_outbound_unknown(
            outbound.pk,
            claim_lease,
            exc.__class__.__name__,
        )
        raise WhatsAppOutboundError(
            "OpenWA send outcome is unknown; retry with the same dedupe key."
        ) from exc

    status_code = response.status_code

    if status_code == 409 or status_code >= 500:
        _mark_outbound_unknown(
            outbound.pk,
            claim_lease,
            f"Ambiguous OpenWA HTTP status {status_code}.",
        )
        raise WhatsAppOutboundError(
            f"OpenWA returned an ambiguous HTTP status ({status_code})."
        )

    if status_code >= 400:
        _mark_outbound_failed(
            outbound.pk,
            claim_lease,
            f"OpenWA rejected the request with HTTP {status_code}.",
        )
        response.raise_for_status()

    try:
        result = response.json()
    except ValueError as exc:
        _mark_outbound_unknown(
            outbound.pk,
            claim_lease,
            "OpenWA returned a non-JSON response.",
        )
        raise WhatsAppOutboundError(
            "OpenWA returned a non-JSON response; send outcome is unknown."
        ) from exc

    if not isinstance(result, dict):
        _mark_outbound_unknown(
            outbound.pk,
            claim_lease,
            "OpenWA returned an unexpected response format.",
        )
        raise WhatsAppOutboundError(
            "OpenWA returned an unexpected response format."
        )

    if result.get("success") is False or result.get("sent") is False:
        _mark_outbound_failed(
            outbound.pk,
            claim_lease,
            "OpenWA explicitly reported that the send failed.",
        )
        raise WhatsAppOutboundError("OpenWA reported a delivery failure.")

    message_id = result.get("messageId") or ""

    accepted = WhatsAppOutboundMessage.objects.filter(
        pk=outbound.pk,
        status="sending",
        lease_until=claim_lease,
    ).update(
        status="accepted",
        lease_until=None,
        accepted_at=timezone.now(),
        openwa_message_id=str(message_id)[:255],
        last_error="",
    )

    if accepted != 1:
        outbound.refresh_from_db()

        if outbound.status == "accepted":
            result["messageId"] = outbound.openwa_message_id or None
            result["outbox_id"] = str(outbound.pk)
            result["replayed"] = True
            return result

        raise WhatsAppSendInProgress(
            "The send response arrived after this worker lost its lease."
        )

    result["outbox_id"] = str(outbound.pk)
    return result


def send_whatsapp_template(
    phone_number,
    patient_name,
    procedure_name,
    preparation_step,
    instructions,
    *,
    dedupe_key,
    purpose,
):
    """Send a PrepBuddy reminder through OpenWA."""

    phone = str(phone_number).strip()

    if phone.startswith("+"):
        phone = phone[1:]

    chat_id = f"{phone}@c.us"

    message = (
        f"Hello {patient_name}!\n\n"
        f"PrepBuddy Reminder\n\n"
        f"Procedure: {procedure_name}\n\n"
        f"Preparation step:\n"
        f"{preparation_step}\n\n"
        f"Instructions:\n"
        f"{instructions}\n\n"
        f"Please complete this step and reply DONE when finished.\n\n"
        f"Have a question about your preparation instructions?\n"
        f"Reply TALK TO ASSISTANT to chat with PrepBuddy."
    )

    result = send_openwa_message(
        chat_id=chat_id,
        text=message,
        dedupe_key=dedupe_key,
        purpose=purpose,
    )

    if not isinstance(result, dict):
        raise RuntimeError(
            "OpenWA returned an unexpected response format."
        )

    if result.get("success") is False or result.get("sent") is False:
        raise RuntimeError("OpenWA reported a delivery failure.")

    return result
