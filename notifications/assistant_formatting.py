"""Safe formatting of preparation assistant WhatsApp responses."""

MAX_ASSISTANT_MESSAGE_UNITS = 3500

EMPTY_ANSWER = (
    "I couldn't find a reliable answer in your stored "
    "preparation instructions. Please check your official "
    "instructions or contact your clinical team."
)

LONG_ANSWER = (
    "Your stored preparation information is too long to "
    "include safely in one WhatsApp message. Please refer "
    "to your complete official preparation instructions. "
    "You can also ask me about a specific preparation step. "
    "If anything is unclear, contact your clinical team."
)


def message_units(text):
    return len(text.encode("utf-16-le")) // 2


def humanize_grounded_reply(answer, sources, needs_clinical_team):
    """Improve presentation without rewriting approved instructions."""

    if needs_clinical_team is not False:
        return answer

    if not isinstance(sources, list) or len(sources) != 1:
        return answer

    source = sources[0]

    if not isinstance(source, dict):
        return answer

    step = source.get("step")

    if not isinstance(step, str) or not step.strip():
        return answer

    marker = f"Stored instruction - {step}: "

    if answer.startswith(marker):
        instruction = answer[len(marker):]

        return (
            "Here's what your preparation instructions say:"
            f"\n\n{step}\n\n{instruction}"
        )

    # Preserve existing empathetic communication framing.
    from chatbot.response_generator import COMMUNICATION_PREFIXES

    for prefix in COMMUNICATION_PREFIXES.values():
        framed_marker = f"{prefix}\n\n{marker}"

        if answer.startswith(framed_marker):
            instruction = answer[len(framed_marker):]

            return f"{prefix}\n\n{step}\n\n{instruction}"

    return answer


def format_assistant_reply(result):

    answer = result.get("answer", "")

    if not isinstance(answer, str) or not answer.strip():
        return EMPTY_ANSWER

    sources = result.get("sources", [])

    answer = humanize_grounded_reply(
        answer,
        sources,
        result.get("needs_clinical_team"),
    )

    if isinstance(sources, list) and sources:

        source = sources[0]

        if isinstance(source, dict):

            step = source.get("step")

            if (
                isinstance(step, str)
                and step.strip()
                and step not in answer
            ):
                answer = f"{answer}\n\nPreparation step: {step}"

    if message_units(answer) > MAX_ASSISTANT_MESSAGE_UNITS:
        return LONG_ANSWER

    return answer
