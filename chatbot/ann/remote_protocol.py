"""Validated protocol payloads for database-independent ANN inference."""

from .remote_service import validate_payload
from .protocol_records import build_retrieval_corpus


MAX_SCOPED_BODY_BYTES = 131072
MAX_PROTOCOL_RECORDS = 64
MAX_ID = 9223372036854775807

SCOPED_ENDPOINT_PATH = "/internal/ann/v2/answer/"

RECORD_FIELDS = {
    "protocol_id",
    "protocol",
    "protocol_description",
    "step_id",
    "step",
    "instruction",
    "minutes_before_procedure",
    "order",
    "is_critical",
    "requires_confirmation",
}


def validate_text(value, limit, *, allow_blank=False):
    if not isinstance(value, str):
        raise ValueError("Invalid record text type")

    if len(value) > limit or chr(0) in value:
        raise ValueError("Invalid record text")

    if not allow_blank and not value.strip():
        raise ValueError("Empty record text")

    # Reject malformed Unicode, including lone surrogates.
    value.encode("utf-8", errors="strict")

    return value


def validate_integer(value, minimum, maximum):
    if (
        type(value) is not int
        or not minimum <= value <= maximum
    ):
        raise ValueError("Invalid record integer")

    return value


def validate_protocol_records(records, protocol_id):
    validate_integer(protocol_id, 1, MAX_ID)

    if (
        not isinstance(records, list)
        or len(records) > MAX_PROTOCOL_RECORDS
    ):
        raise ValueError("Invalid protocol record collection")

    validated = []
    seen = set()
    expected_metadata = None

    for record in records:
        if (
            not isinstance(record, dict)
            or set(record) != RECORD_FIELDS
        ):
            raise ValueError("Invalid protocol record fields")

        record_protocol = validate_integer(
            record["protocol_id"], 1, MAX_ID
        )

        if record_protocol != protocol_id:
            raise ValueError("Protocol scope mismatch")

        step_id = validate_integer(
            record["step_id"], 1, MAX_ID
        )

        if step_id in seen:
            raise ValueError("Duplicate protocol step")

        seen.add(step_id)

        name = validate_text(record["protocol"], 256)

        description = validate_text(
            record["protocol_description"],
            4096,
            allow_blank=True,
        )

        title = validate_text(record["step"], 256)

        instruction = validate_text(
            record["instruction"], 8192
        )

        if instruction.strip().casefold() in {
            "", ".", "-", "n/a"
        }:
            raise ValueError("Placeholder instruction")

        metadata = (name, description)

        if expected_metadata is None:
            expected_metadata = metadata
        elif metadata != expected_metadata:
            raise ValueError("Inconsistent protocol metadata")

        validate_integer(
            record["minutes_before_procedure"],
            0,
            2147483647,
        )

        validate_integer(
            record["order"], 0, 2147483647
        )

        for field in (
            "is_critical",
            "requires_confirmation",
        ):
            if type(record[field]) is not bool:
                raise ValueError("Invalid record boolean")

        validated.append(dict(record))

    return validated


def validate_scoped_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("Invalid scoped payload")

    if "protocol_records" not in payload:
        raise ValueError("Protocol records are required")

    arguments = validate_payload({
        key: value
        for key, value in payload.items()
        if key != "protocol_records"
    })

    protocol_id = validate_integer(
        arguments["protocol_id"], 1, MAX_ID
    )

    validate_text(arguments["question"], 2000)
    validate_text(arguments["communication_style"], 64)

    arguments["protocol_records"] = (
        validate_protocol_records(
            payload["protocol_records"],
            protocol_id,
        )
    )

    return arguments


def invoke_scoped_ann(*, protocol_records, **arguments):
    """Invoke ANN using explicitly supplied, validated records."""

    from .backend import answer_configured_ann

    corpus = build_retrieval_corpus(protocol_records)

    return answer_configured_ann(
        **arguments,
        corpus_records=corpus,
    )
