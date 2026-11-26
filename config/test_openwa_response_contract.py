import pytest

from deploy.hybrid_gateway import valid_send_acceptance


@pytest.mark.parametrize("status,data,expected", [
    (201, {"messageId": "demo-id", "timestamp": 1706868000}, True),
    (200, {"messageId": "demo-id", "success": True}, True),
    (201, {"messageId": "demo-id", "sent": True}, True),
    (201, {"messageId": "demo-id"}, False),
    (200, {"messageId": "demo-id", "timestamp": 1706868000}, False),
    (201, {"messageId": "", "timestamp": 1706868000}, False),
    (201, {"messageId": "demo-id", "timestamp": True}, False),
    (201, {"messageId": "demo-id", "timestamp": -1}, False),
    (201, {"messageId": "demo-id", "success": False}, False),
    (201, {"messageId": "demo-id", "success": True, "sent": False}, False),
    (502, {"messageId": "demo-id", "success": True}, False),
    (409, {"messageId": "demo-id", "success": True}, False),
    (201, {"success": True}, False),
    (201, {"messageId": "x" * 256, "success": True}, False),
    (201, None, False),
])
def test_openwa_response_contract(status, data, expected):
    assert valid_send_acceptance(status, data) is expected


def test_gateway_normalizes_native_openwa_acceptance(monkeypatch):
    import io
    import json

    from uuid import uuid4
    from unittest.mock import Mock
    from wsgiref.util import setup_testing_defaults
    from deploy import hybrid_gateway

    phone = "910000000001"
    proxy_token = "P" * 64
    idempotency_key = str(uuid4())

    upstream = Mock(return_value=(
        201,
        json.dumps({
            "messageId": "synthetic-native-message",
            "timestamp": 1706868000,
        }).encode("utf-8"),
    ))

    monkeypatch.setattr(
        hybrid_gateway,
        "upstream",
        upstream,
    )

    app = hybrid_gateway.create_app(
        ann_token="A" * 64,
        proxy_token=proxy_token,
        openwa_key="K" * 64,
        session_id=str(uuid4()),
        allowed_phone=phone,
        allow_send=True,
    )

    body = json.dumps({
        "chatId": phone + "@c.us",
        "text": "Synthetic gateway regression test.",
    }).encode("utf-8")

    environ = {}
    setup_testing_defaults(environ)

    environ.update({
        "REQUEST_METHOD": "POST",
        "PATH_INFO": "/api/notifications/openwa/relay/send-text/",
        "CONTENT_TYPE": "application/json",
        "CONTENT_LENGTH": str(len(body)),
        "HTTP_X_PROXY_TOKEN": proxy_token,
        "HTTP_IDEMPOTENCY_KEY": idempotency_key,
        "wsgi.input": io.BytesIO(body),
    })

    captured = {}

    def start_response(status, headers):
        captured["status"] = status

    response = b"".join(app(environ, start_response))

    assert captured["status"].startswith("200 ")

    assert json.loads(response) == {
        "success": True,
        "messageId": "synthetic-native-message",
    }

    upstream.assert_called_once()

    assert (
        upstream.call_args.args[2]["Idempotency-Key"]
        == idempotency_key
    )
