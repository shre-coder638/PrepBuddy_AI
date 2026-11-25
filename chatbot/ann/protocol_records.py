"""Production loader for assigned preparation protocol instructions."""

from __future__ import annotations


def load_protocol_records(protocol_id: int) -> list[dict]:
    """Load usable instructions from one active assigned protocol."""

    if (
        not isinstance(protocol_id, int)
        or isinstance(protocol_id, bool)
        or protocol_id < 1
    ):
        raise ValueError("protocol_id must be a positive integer")

    from protocols.models import PrepStep

    steps = (
        PrepStep.objects
        .filter(
            protocol_id=protocol_id,
            protocol__is_active=True,
        )
        .select_related("protocol")
        .order_by(
            "-minutes_before_procedure",
            "order",
            "pk",
        )
    )

    records = []

    for step in steps:
        instruction = (step.instruction or "").strip()

        if instruction.casefold() in {
            "", ".", "-", "n/a"
        }:
            continue

        records.append({
            "protocol_id": step.protocol_id,
            "protocol": step.protocol.name,
            "protocol_description": step.protocol.description,
            "step_id": step.pk,
            "step": step.title,
            "instruction": instruction,
            "minutes_before_procedure": (
                step.minutes_before_procedure
            ),
            "order": step.order,
            "is_critical": step.is_critical,
            "requires_confirmation": (
                step.requires_confirmation
            ),
        })

    return records
