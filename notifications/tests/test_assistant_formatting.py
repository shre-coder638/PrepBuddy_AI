import pytest

from notifications.assistant_formatting import (
    format_assistant_reply,
    message_units,
    MAX_ASSISTANT_MESSAGE_UNITS,
    EMPTY_ANSWER,
    LONG_ANSWER,
)


def test_short_answer_preserved():

    answer = "Synthetic preparation instruction."

    assert format_assistant_reply({
        "answer": answer,
        "sources": [],
    }) == answer


def test_source_appended():

    result = format_assistant_reply({
        "answer": "Synthetic instruction.",
        "sources": [{"step": "Preparation title"}],
    })

    assert result == (
        "Synthetic instruction.\n\n"
        "Preparation step: Preparation title"
    )


def test_duplicate_source_not_appended():

    answer = "Preparation title: Synthetic instruction."

    assert format_assistant_reply({
        "answer": answer,
        "sources": [{"step": "Preparation title"}],
    }) == answer


@pytest.mark.parametrize("answer", [None, "", "   ", 123])
def test_invalid_answer(answer):

    assert format_assistant_reply({
        "answer": answer,
    }) == EMPTY_ANSWER


def test_long_answer_not_truncated():

    answer = "A" * 6554

    assert format_assistant_reply({
        "answer": answer,
        "sources": [{"step": "Preparation title"}],
    }) == LONG_ANSWER


def test_exact_length_limit():

    answer = "A" * MAX_ASSISTANT_MESSAGE_UNITS

    assert format_assistant_reply({
        "answer": answer,
    }) == answer


def test_source_append_exceeding_limit():

    answer = "A" * MAX_ASSISTANT_MESSAGE_UNITS

    assert format_assistant_reply({
        "answer": answer,
        "sources": [{"step": "Extra source"}],
    }) == LONG_ANSWER


def test_unicode_message_measurement():

    emoji = "\U0001F600"

    assert message_units(emoji) == 2

    answer = emoji * 2000

    assert format_assistant_reply({
        "answer": answer,
    }) == LONG_ANSWER


def test_hindi_text_preserved():

    answer = "\u0924\u0948\u092f\u093e\u0930\u0940"

    assert format_assistant_reply({
        "answer": answer,
    }) == answer
