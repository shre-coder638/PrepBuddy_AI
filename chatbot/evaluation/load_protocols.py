"""Read-only loader for the multilingual retrieval evaluation."""

from __future__ import annotations


def load_active_protocols() -> list[dict[str, object]]:
    """Load active protocol steps without modifying database records."""
    from protocols.models import PrepProtocol

    protocols = (
        PrepProtocol.objects
        .filter(is_active=True)
        .prefetch_related("steps")
        .order_by("name")
    )

    records: list[dict[str, object]] = []

    for protocol in protocols:
        for step in protocol.steps.all():
            instruction = (step.instruction or "").strip()

            if instruction.lower() in {"", ".", "-", "n/a"}:
                continue

            content = (
                f"Protocol ID: {protocol.pk}\n"
                f"Procedure: {protocol.name}\n"
                f"Protocol description: {protocol.description}\n"
                f"Step: {step.title}\n"
                f"Instruction: {instruction}"
            )

            records.append({
                "protocol_id": protocol.pk,
                "protocol": protocol.name,
                "protocol_description": protocol.description,
                "step_id": step.pk,
                "step": step.title,
                "instruction": instruction,
                "minutes_before_procedure": step.minutes_before_procedure,
                "is_critical": step.is_critical,
                "requires_confirmation": step.requires_confirmation,
                "text": content,
            })

    return records
