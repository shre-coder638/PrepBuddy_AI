"""Conservative natural-language aliases for approved preparation steps."""

import re


QUESTION_TOPICS = {
    "clothing": (
        r"what should i wear",
        r"what clothes should i wear",
        r"what clothing should i wear",
        r"what can i wear",
        r"how should i dress",
    ),
    "documents": (
        r"what should i bring",
        r"what do i need to bring",
        r"what documents should i bring",
        r"what documents do i need",
        r"what should i carry",
    ),
    "arrival": (
        r"when should i arrive",
        r"what time should i arrive",
        r"when do i need to arrive",
        r"when should i check in",
        r"how early should i arrive",
    ),
    "procedure": (
        r"what happens during (?:my|the) (?:procedure|scan|test)",
        r"what will happen during (?:my|the) (?:procedure|scan|test)",
        r"what should i expect during (?:my|the) (?:procedure|scan|test)",
    ),
}


TOPIC_TITLES = {
    "clothing": {
        "Choose Suitable Clothing",
        "Choose Suitable Clothing and Remove Metal Items",
        "Wear Comfortable Clothing",
        "Prepare Clothing and Personal Belongings",
    },
    "documents": {
        "Bring Your Documents and Arrive for Check-In",
    },
    "arrival": {
        "Arrive and Check In",
        "Bring Your Documents and Arrive for Check-In",
        "Arrive and Complete the Final Safety Check",
        "Arrive and Prepare for the Colonoscopy",
    },
    "procedure": {
        "Know What Happens During the ECG",
        "Understand What Happens During the CT Scan",
        "Understand What Happens During the X-ray",
        "Understand What Happens During the MRI",
    },
}


OPTIONAL_SUFFIX = (
    r"(?: (?:before|for) (?:my|the) "
    r"(?:procedure|scan|test|appointment))?"
)


def normalize_preview_question(question, records):
    """Resolve only complete, recognized questions to one stored step."""

    if not isinstance(question, str):
        return question

    normalized = " ".join(question.casefold().split())
    normalized = normalized.rstrip("?.!").strip()

    for topic, patterns in QUESTION_TOPICS.items():

        suffix = "" if topic == "procedure" else OPTIONAL_SUFFIX

        if not any(
            re.fullmatch(pattern + suffix, normalized)
            for pattern in patterns
        ):
            continue

        matches = [
            record["step"]
            for record in records
            if record["step"] in TOPIC_TITLES[topic]
        ]

        if len(matches) == 1:
            return f"Repeat {matches[0]}"

        # Missing or ambiguous evidence: preserve the original question.
        return question

    return question
