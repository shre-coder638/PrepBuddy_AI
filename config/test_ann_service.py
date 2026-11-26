import json
from unittest.mock import patch

from django.test import Client, SimpleTestCase, override_settings


TOKEN = "synthetic-ann-service-token-" * 3
URL = "/internal/ann/v1/answer/"

ANSWER = {
    "answer": "Synthetic preparation instruction.",
    "sources": [],
    "needs_clinical_team": False,
}


@override_settings(
    ROOT_URLCONF="config.ann_service_urls",
    MIDDLEWARE=[],
    ANN_SERVICE_TOKEN=TOKEN,
    ALLOWED_HOSTS=["testserver"],
)
class ANNServiceTests(SimpleTestCase):

    def setUp(self):
        self.client = Client()
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {TOKEN}"}

    def post(self, payload, authenticated=True):
        headers = self.auth if authenticated else {}

        return self.client.post(
            URL,
            data=json.dumps(payload),
            content_type="application/json",
            **headers,
        )

    @patch(
        "chatbot.ann.remote_service.invoke_ann",
        return_value=ANSWER,
    )
    def test_valid_request(self, inference):
        result = self.post({
            "question": "Synthetic question",
            "protocol_id": 1,
        })

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json(), ANSWER)
        self.assertEqual(result["Cache-Control"], "no-store")

        inference.assert_called_once_with(
            question="Synthetic question",
            protocol_id=1,
            communication_style="neutral",
            requires_human=False,
        )

    @patch("chatbot.ann.remote_service.invoke_ann")
    def test_missing_authentication(self, inference):
        result = self.post(
            {"question": "Synthetic question"},
            authenticated=False,
        )
        self.assertEqual(result.status_code, 401)
        inference.assert_not_called()

    def test_invalid_token(self):
        result = self.client.post(
            URL,
            data="{}",
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer incorrect",
        )
        self.assertEqual(result.status_code, 401)

    def test_get_not_allowed(self):
        result = self.client.get(URL, **self.auth)
        self.assertEqual(result.status_code, 405)

    def test_invalid_content_type(self):
        result = self.client.post(
            URL,
            data="question",
            content_type="text/plain",
            **self.auth,
        )
        self.assertEqual(result.status_code, 415)

    def test_malformed_json(self):
        result = self.client.post(
            URL,
            data="{invalid",
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(result.status_code, 400)

    def test_unknown_fields(self):
        result = self.post({
            "question": "Synthetic question",
            "unexpected": True,
        })
        self.assertEqual(result.status_code, 400)

    def test_blank_question(self):
        self.assertEqual(
            self.post({"question": " "}).status_code,
            400,
        )

    def test_question_length_limit(self):
        self.assertEqual(
            self.post({"question": "x" * 2001}).status_code,
            400,
        )

    def test_invalid_protocol_ids(self):
        for value in (True, -1, 0, "1", 1.5):
            with self.subTest(value=value):
                result = self.post({
                    "question": "Synthetic question",
                    "protocol_id": value,
                })
                self.assertEqual(result.status_code, 400)

    def test_invalid_escalation_flag(self):
        result = self.post({
            "question": "Synthetic question",
            "requires_human": "false",
        })
        self.assertEqual(result.status_code, 400)

    def test_duplicate_fields(self):
        result = self.client.post(
            URL,
            data='{"question":"first","question":"second"}',
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(result.status_code, 400)

    def test_oversized_request(self):
        result = self.post({
            "question": "x" * 17000,
        })
        self.assertEqual(result.status_code, 413)

    @patch(
        "chatbot.ann.remote_service.invoke_ann",
        side_effect=RuntimeError("Synthetic failure"),
    )
    def test_inference_failure(self, inference):
        result = self.post({
            "question": "Synthetic question",
        })

        self.assertEqual(result.status_code, 503)
        self.assertEqual(
            result.json(),
            {"error": "Inference unavailable"},
        )

    def test_admin_not_exposed(self):
        self.assertEqual(
            self.client.get("/admin/", **self.auth).status_code,
            404,
        )

    def test_patient_api_not_exposed(self):
        self.assertEqual(
            self.client.get(
                "/api/patients/",
                **self.auth,
            ).status_code,
            404,
        )

    def test_webhook_not_exposed(self):
        self.assertEqual(
            self.client.post(
                "/api/notifications/openwa/webhook/",
                **self.auth,
            ).status_code,
            404,
        )
