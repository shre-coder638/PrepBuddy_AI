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


def format_assistant_reply(result):

    answer = result.get("answer", "")

    if not isinstance(answer, str) or not answer.strip():
        return EMPTY_ANSWER

    sources = result.get("sources", [])

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
