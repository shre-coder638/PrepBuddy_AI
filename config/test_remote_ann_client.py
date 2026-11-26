import json
from unittest.mock import patch

import requests

from django.test import SimpleTestCase

from chatbot.ann.remote_client import (
    RemoteANNError,
    request_remote_ann,
    MAX_RESPONSE_BYTES,
)


URL = "https://ann.example.test/internal/ann/v1/answer/"
TOKEN = "synthetic_ann_token_" * 3

ANSWER = {
    "answer": "Synthetic response.",
    "sources": [],
    "needs_clinical_team": True,
}


class RemoteANNClientTests(SimpleTestCase):

    def setUp(self):
        patcher = patch(
            "chatbot.ann.remote_client.requests.Session"
        )

        self.mock_session = patcher.start()
        self.addCleanup(patcher.stop)

        self.session = (
            self.mock_session.return_value
            .__enter__.return_value
        )

        self.response = (
            self.session.post.return_value
            .__enter__.return_value
        )

        self.response.status_code = 200

        self.response.headers = {
            "Content-Type": "application/json"
        }

        self.response.iter_content.return_value = [
            json.dumps(ANSWER).encode("utf-8")
        ]

    def invoke(self, **kwargs):
        arguments = {
            "url": URL,
            "token": TOKEN,
            "question": "Synthetic question",
            "protocol_id": 1,
        }

        arguments.update(kwargs)

        return request_remote_ann(**arguments)

    def test_valid_response(self):
        self.assertEqual(self.invoke(), ANSWER)

        self.session.post.assert_called_once()

        args, kwargs = self.session.post.call_args

        self.assertEqual(args[0], URL)
        self.assertTrue(kwargs["verify"])
        self.assertFalse(kwargs["allow_redirects"])
        self.assertTrue(kwargs["stream"])
        self.assertFalse(self.session.trust_env)

        self.assertEqual(
            kwargs["headers"]["Authorization"],
            f"Bearer {TOKEN}",
        )

        sent = json.loads(kwargs["data"])
        self.assertEqual(sent["protocol_id"], 1)

    def test_reject_http(self):
        with self.assertRaises(RemoteANNError):
            self.invoke(url=URL.replace("https:", "http:"))

        self.session.post.assert_not_called()

    def test_reject_wrong_endpoint(self):
        with self.assertRaises(RemoteANNError):
            self.invoke(url="https://ann.example.test/admin/")

        self.session.post.assert_not_called()

    def test_reject_short_token(self):
        with self.assertRaises(RemoteANNError):
            self.invoke(token="short")

        self.session.post.assert_not_called()

    def test_reject_redirect(self):
        self.response.status_code = 302

        with self.assertRaises(RemoteANNError):
            self.invoke()

        self.session.post.assert_called_once()

    def test_service_unavailable(self):
        self.response.status_code = 503

        with self.assertRaises(RemoteANNError):
            self.invoke()

    def test_connection_failure(self):
        self.session.post.side_effect = (
            requests.ConnectionError("Synthetic failure")
        )

        with self.assertRaises(RemoteANNError):
            self.invoke()

    def test_read_timeout(self):
        self.session.post.side_effect = requests.Timeout()

        with self.assertRaises(RemoteANNError):
            self.invoke()

    def test_invalid_content_type(self):
        self.response.headers = {
            "Content-Type": "text/html"
        }

        with self.assertRaises(RemoteANNError):
            self.invoke()

    def test_invalid_json(self):
        self.response.iter_content.return_value = [
            b"{invalid"
        ]

        with self.assertRaises(RemoteANNError):
            self.invoke()

    def test_duplicate_json_fields(self):
        self.response.iter_content.return_value = [
            b'{"answer":"first","answer":"second"}'
        ]

        with self.assertRaises(RemoteANNError):
            self.invoke()

    def test_oversized_response(self):
        self.response.iter_content.return_value = [
            b"x" * (MAX_RESPONSE_BYTES + 1)
        ]

        with self.assertRaises(RemoteANNError):
            self.invoke()

    def test_invalid_request(self):
        with self.assertRaises(RemoteANNError):
            self.invoke(protocol_id=True)

        self.session.post.assert_not_called()

    def test_unicode_request(self):
        self.invoke(question="तैयारी कैसे करूँ?")

        sent = json.loads(
            self.session.post.call_args.kwargs["data"]
        )

        self.assertEqual(
            sent["question"],
            "तैयारी कैसे करूँ?",
        )
