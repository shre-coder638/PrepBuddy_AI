"""Offline tests for the standalone HTTPS scheduler."""

import json
from unittest.mock import MagicMock

import pytest

from deploy.https_scheduler import (
    SCHEDULER_URL,
    SchedulerError,
    SchedulerConfigurationError,
    run_tick,
)


TOKEN = "s" * 64


def fake_session(status=200, body=b"{}"):
    session = MagicMock()

    response = session.post.return_value.__enter__.return_value
    response.status_code = status
    response.iter_content.return_value = [body]

    return session


@pytest.mark.parametrize("status,mode", [
    ("ok", "heartbeat-only"),
    ("ok", "reconciliation"),
    ("busy", "reconciliation"),
    ("ok", "reconciliation-and-delivery"),
    ("busy", "reconciliation-and-delivery"),
])
def test_valid_tick(status, mode):
    expected = {"status": status, "mode": mode}

    session = fake_session(
        body=json.dumps(expected).encode()
    )

    assert run_tick(session, TOKEN) == expected

    args = session.post.call_args.args
    kwargs = session.post.call_args.kwargs

    assert args == (SCHEDULER_URL,)
    assert kwargs["data"] == b"{}"
    assert kwargs["verify"] is True
    assert kwargs["allow_redirects"] is False
    assert kwargs["stream"] is True

    assert kwargs["headers"]["Authorization"] == (
        "Bearer " + TOKEN
    )


@pytest.mark.parametrize("status", [
    301, 302, 401, 403, 404, 405,
])
def test_configuration_failure(status):
    session = fake_session(status=status)

    with pytest.raises(SchedulerConfigurationError):
        run_tick(session, TOKEN)


@pytest.mark.parametrize("status", [429, 500, 503])
def test_temporary_failure(status):
    session = fake_session(status=status)

    with pytest.raises(SchedulerError):
        run_tick(session, TOKEN)


@pytest.mark.parametrize("body", [
    b"invalid JSON",
    b"[]",
    b"{}",
    b"x" * 5000,
    b'{"status":"ok","mode":"unexpected"}',
])
def test_invalid_response(body):
    session = fake_session(body=body)

    with pytest.raises(SchedulerError):
        run_tick(session, TOKEN)


def test_invalid_token_prevents_request():
    session = fake_session()

    with pytest.raises(SchedulerConfigurationError):
        run_tick(session, "invalid")

    session.post.assert_not_called()
