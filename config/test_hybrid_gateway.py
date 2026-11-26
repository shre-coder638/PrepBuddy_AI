"""Offline security tests for the hybrid gateway."""

import json
from io import BytesIO
from unittest.mock import patch
from wsgiref.util import setup_testing_defaults

import pytest

from deploy import hybrid_gateway as gateway


ANN_TOKEN = "a" * 64
PROXY_TOKEN = "p" * 64
PHONE = "15550100101"
KEY = "12345678-1234-4234-8234-123456789abc"


@pytest.fixture
def app():
    return gateway.create_app(
        ann_token=ANN_TOKEN,
        proxy_token=PROXY_TOKEN,
        openwa_key="synthetic-api-key",
        session_id="synthetic-session",
        allowed_phone=PHONE,
        allow_send=True,
    )


def call(app, path, payload=None, **overrides):
    body = json.dumps(
        payload if payload is not None else {}
    ).encode()

    env = {}
    setup_testing_defaults(env)

    env.update({
        "PATH_INFO": path,
        "REQUEST_METHOD": "POST",
        "CONTENT_TYPE": "application/json",
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": BytesIO(body),
        "HTTP_X_PROXY_TOKEN": PROXY_TOKEN,
        "HTTP_AUTHORIZATION": "Bearer " + ANN_TOKEN,
        "HTTP_IDEMPOTENCY_KEY": KEY,
    })

    env.update(overrides)

    statuses = []

    result = b"".join(app(
        env,
        lambda status, headers: statuses.append(status),
    ))

    return int(statuses[0].split()[0]), json.loads(result)


@pytest.mark.parametrize("path", [
    "/",
    "/admin/",
    "/api/patients/",
    "/internal/ann/v1/answer/",
    gateway.SEND_PATH + "extra/",
])
def test_unknown_routes(app, path):
    with patch.object(gateway, "upstream") as upstream:
        assert call(app, path)[0] == 404
        upstream.assert_not_called()


def test_wrong_method(app):
    with patch.object(gateway, "upstream") as upstream:
        assert call(
            app, gateway.CONTACT_PATH,
            REQUEST_METHOD="GET",
        )[0] == 405

        upstream.assert_not_called()


def test_ann_token_separation(app):
    with patch.object(gateway, "upstream") as upstream:
        assert call(
            app, gateway.ANN_PATH,
            HTTP_AUTHORIZATION="Bearer " + PROXY_TOKEN,
        )[0] == 401

        upstream.assert_not_called()


def test_proxy_token_separation(app):
    with patch.object(gateway, "upstream") as upstream:
        assert call(
            app, gateway.SEND_PATH,
            HTTP_X_PROXY_TOKEN=ANN_TOKEN,
        )[0] == 401

        upstream.assert_not_called()


def test_ann_forwarding(app):
    with patch.object(
        gateway, "upstream",
        return_value=(200, b'{"synthetic":true}'),
    ) as upstream:

        assert call(app, gateway.ANN_PATH) == (
            200, {"synthetic": True}
        )

        args = upstream.call_args.args

        assert args[1] == (
            gateway.ANN_BASE + gateway.ANN_PATH
        )

        assert args[2]["Authorization"] == (
            "Bearer " + ANN_TOKEN
        )


def test_allowed_contact(app):
    with patch.object(
        gateway, "upstream",
        return_value=(
            200,
            json.dumps({"phone": "+" + PHONE}).encode(),
        ),
    ):
        assert call(
            app, gateway.CONTACT_PATH,
            {"chatId": "123@lid"},
        ) == (200, {"phone": PHONE})


def test_unapproved_contact(app):
    with patch.object(
        gateway, "upstream",
        return_value=(
            200, b'{"phone":"15550100102"}'
        ),
    ):
        assert call(
            app, gateway.CONTACT_PATH,
            {"chatId": "123@lid"},
        )[0] == 403


def test_unapproved_recipient(app):
    with patch.object(gateway, "upstream") as upstream:
        assert call(
            app, gateway.SEND_PATH,
            {
                "chatId": "15550100102@c.us",
                "text": "Synthetic test",
            },
        )[0] == 403

        upstream.assert_not_called()


def test_invalid_idempotency_key(app):
    with patch.object(gateway, "upstream") as upstream:
        assert call(
            app, gateway.SEND_PATH,
            {
                "chatId": PHONE + "@c.us",
                "text": "Synthetic test",
            },
            HTTP_IDEMPOTENCY_KEY="invalid",
        )[0] == 400

        upstream.assert_not_called()


def test_allowed_send_preserves_idempotency(app):
    with patch.object(
        gateway, "upstream",
        return_value=(
            201,
            b'{"success":true,"messageId":"synthetic-id"}',
        ),
    ) as upstream:

        status, result = call(
            app, gateway.SEND_PATH,
            {
                "chatId": PHONE + "@c.us",
                "text": "Synthetic test",
            },
        )

        assert status == 200
        assert result["messageId"] == "synthetic-id"
        assert upstream.call_args.args[2]["Idempotency-Key"] == KEY


def test_uncertain_send_not_accepted(app):
    with patch.object(
        gateway, "upstream",
        return_value=(200, b"{}"),
    ):
        assert call(
            app, gateway.SEND_PATH,
            {
                "chatId": PHONE + "@c.us",
                "text": "Synthetic test",
            },
        )[0] == 502


def test_unapproved_lid_cannot_send(app):
    with patch.object(
        gateway, "upstream",
        return_value=(
            200, b'{"phone":"15550100102"}'
        ),
    ) as upstream:

        assert call(
            app, gateway.SEND_PATH,
            {
                "chatId": "123@lid",
                "text": "Synthetic test",
            },
        )[0] == 403

        assert upstream.call_count == 1
        assert upstream.call_args.args[0] == "GET"


def test_oversized_request(app):
    with patch.object(gateway, "upstream") as upstream:
        assert call(
            app, gateway.SEND_PATH,
            CONTENT_LENGTH="65537",
        )[0] == 413

        upstream.assert_not_called()


def test_query_parameters_rejected(app):
    with patch.object(gateway, "upstream") as upstream:
        assert call(
            app, gateway.ANN_PATH,
            QUERY_STRING="unexpected=1",
        )[0] == 400

        upstream.assert_not_called()


def test_shared_gateway_tokens_rejected():
    with pytest.raises(ValueError):
        gateway.create_app(
            ann_token=ANN_TOKEN,
            proxy_token=ANN_TOKEN,
            openwa_key="synthetic-key",
            session_id="synthetic-session",
            allowed_phone=PHONE,
        )



def test_delivery_disabled_by_default():
    app = gateway.create_app(
        ann_token=ANN_TOKEN,
        proxy_token=PROXY_TOKEN,
        openwa_key="synthetic-key",
        session_id="synthetic-session",
        allowed_phone=PHONE,
    )

    with patch.object(gateway, "upstream") as upstream:
        status, result = call(
            app,
            gateway.SEND_PATH,
            {
                "chatId": PHONE + "@c.us",
                "text": "Synthetic test",
            },
        )

        assert status == 503
        upstream.assert_not_called()



def test_waitress_http_transport():
    import subprocess
    import sys

    from queue import Queue
    from threading import Thread

    import requests

    pytest.importorskip("waitress")

    script = """
from waitress import create_server
from deploy import hybrid_gateway as gateway

def fake_upstream(method, url, headers, *args, **kwargs):
    if url == gateway.ANN_BASE + gateway.ANN_PATH:
        return 200, b'{"synthetic":true}'

    if method == "GET" and url.endswith("/phone"):
        return 200, b'{"phone":"15550100101"}'

    raise RuntimeError("Unexpected upstream operation")

gateway.upstream = fake_upstream

app = gateway.create_app(
    ann_token="a" * 64,
    proxy_token="p" * 64,
    openwa_key="synthetic-key",
    session_id="synthetic-session",
    allowed_phone="15550100101",
)

server = create_server(
    app,
    host="127.0.0.1",
    port=0,
    threads=4,
    channel_timeout=30,
    max_request_body_size=131072,
    max_request_header_size=16384,
    expose_tracebacks=False,
)

print(server.effective_port, flush=True)
server.run()
"""

    process = subprocess.Popen(
        [sys.executable, "-u", "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )

    ready = Queue()

    reader = Thread(
        target=lambda: ready.put(process.stdout.readline()),
        daemon=True,
    )
    reader.start()

    try:
        port = int(ready.get(timeout=15).strip())
        base = f"http://127.0.0.1:{port}"

        with requests.Session() as session:
            session.trust_env = False

            response = session.post(
                base + gateway.ANN_PATH,
                json={"synthetic": True},
                headers={
                    "Authorization": "Bearer " + ANN_TOKEN,
                },
                timeout=5,
            )

            assert response.status_code == 200
            assert response.json() == {"synthetic": True}
            assert response.headers["Cache-Control"] == "no-store"

            response = session.post(
                base + gateway.CONTACT_PATH,
                json={"chatId": "123@lid"},
                headers={"X-Proxy-Token": PROXY_TOKEN},
                timeout=5,
            )

            assert response.status_code == 200
            assert response.json() == {"phone": PHONE}

            response = session.post(
                base + gateway.SEND_PATH,
                json={
                    "chatId": PHONE + "@c.us",
                    "text": "Synthetic test",
                },
                headers={
                    "X-Proxy-Token": PROXY_TOKEN,
                    "Idempotency-Key": KEY,
                },
                timeout=5,
            )

            assert response.status_code == 503

            response = session.post(
                base + gateway.CONTACT_PATH,
                json={"chatId": "123@lid"},
                timeout=5,
            )

            assert response.status_code == 401

            response = session.get(
                base + "/admin/",
                timeout=5,
            )

            assert response.status_code == 404

    finally:
        if process.poll() is None:
            process.terminate()

            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

        reader.join(timeout=5)
        process.stdout.close()
