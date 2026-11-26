"""Build source-grounded overviews of assigned preparation protocols."""

from __future__ import annotations

from chatbot.response_generator import apply_communication_style

from .protocol_records import load_protocol_records


def build_protocol_overview(
    protocol_id,
    communication_style="neutral",
    *,
    corpus_records=None,
):
    """Return a complete stored protocol overview or None."""

    if corpus_records is None:
        records = load_protocol_records(protocol_id)
    else:
        records = corpus_records

    if not records:
        return None

    if any(
        record["protocol_id"] != protocol_id
        for record in records
    ):
        return None

    protocol_names = {
        record["protocol"]
        for record in records
    }

    if len(protocol_names) != 1:
        return None

    protocol_name = records[0]["protocol"]

    # Temporary safeguard for the existing non-clinical QA protocol.
    # Replace with explicit clinical publication metadata before deployment.
    normalized_name = protocol_name.casefold()

    if (
        protocol_id == 16
        or "non-clinical" in normalized_name
        or "qa - " in normalized_name
    ):
        return None

    sections = [
        f"Stored protocol overview: {protocol_name}",
        (
            "These are the complete stored instructions for your "
            "assigned protocol. They may include information about "
            "preparation, the procedure and recovery."
        ),
        (
            "Follow the timing and conditions stated in each "
            "instruction and any personalized instructions provided "
            "by your clinical team."
        ),
    ]

    sources = []
    seen = set()

    for index, record in enumerate(records, start=1):

        if record["step_id"] in seen:
            return None

        seen.add(record["step_id"])

        title = record["step"].strip()
        instruction = record["instruction"].strip()

        if not title or not instruction:
            return None

        if instruction.casefold() in {".", "-", "n/a"}:
            return None

        sections.append(
            f"{index}. {title}\n{instruction}"
        )

        sources.append({
            "protocol_id": record["protocol_id"],
            "protocol": record["protocol"],
            "step_id": record["step_id"],
            "step": record["step"],
            "minutes_before_procedure": record[
                "minutes_before_procedure"
            ],
            "is_critical": record["is_critical"],
            "requires_confirmation": record[
                "requires_confirmation"
            ],
        })

    sections.append(
        "If any instruction is unclear or conflicts with "
        "personalized advice, confirm it with your clinical team."
    )

    answer = "\n\n".join(sections)

    return {
        "answer": apply_communication_style(
            answer,
            communication_style,
        ),
        "sources": sources,
        "needs_clinical_team": False,
    }
