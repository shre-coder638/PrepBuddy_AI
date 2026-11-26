"""Runtime configuration for the isolated ANN service."""

bind = "0.0.0.0:8000"
workers = 1
threads = 1
timeout = 120

accesslog = None
errorlog = "-"
loglevel = "info"


def post_worker_init(worker):
    """Initialize neural inference before processing requests."""

    from chatbot.ann.remote_protocol import (
        validate_scoped_payload,
        invoke_scoped_ann,
    )

    payload = {
        "question": "Repeat the Synthetic instruction",
        "protocol_id": 1,
        "communication_style": "neutral",
        "requires_human": False,
        "protocol_records": [{
            "protocol_id": 1,
            "protocol": "Synthetic Staging Protocol",
            "protocol_description": "Software testing only.",
            "step_id": 1,
            "step": "Synthetic instruction",
            "instruction": "This is a synthetic test record.",
            "minutes_before_procedure": 60,
            "order": 1,
            "is_critical": False,
            "requires_confirmation": False,
        }],
    }

    result = invoke_scoped_ann(
        **validate_scoped_payload(payload)
    )

    if (
        result.get("needs_clinical_team") is not False
        or len(result.get("sources", [])) != 1
        or result["sources"][0]["step_id"] != 1
        or payload["protocol_records"][0]["instruction"]
            not in result.get("answer", "")
    ):
        raise RuntimeError("ANN startup warm-up failed.")

    worker.log.info("SCOPED ANN WARMUP PASSED")
