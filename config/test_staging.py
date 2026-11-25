import base64

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import resolve

from config.staging import StagingAccessMiddleware, healthz


@override_settings(
    STAGING_ACCESS_TOKEN="synthetic-test-token-" * 3,
)
class StagingSecurityTests(SimpleTestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = StagingAccessMiddleware(
            lambda request: HttpResponse("Protected content")
        )

    def authorization(self, username, password):
        raw = f"{username}:{password}".encode("utf-8")
        encoded = base64.b64encode(raw).decode("ascii")
        return f"Basic {encoded}"

    def test_health_route(self):
        self.assertEqual(
            resolve("/healthz/").func,
            healthz,
        )

    def test_health_response(self):
        response = healthz(self.factory.get("/healthz/"))
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {"status": "ok"},
        )

    def test_health_bypasses_access_gate(self):
        response = self.middleware(
            self.factory.get("/healthz/")
        )
        self.assertEqual(response.status_code, 200)

    def test_health_post_does_not_bypass_gate(self):
        response = self.middleware(
            self.factory.post("/healthz/")
        )
        self.assertEqual(response.status_code, 401)

    def test_missing_credentials(self):
        response = self.middleware(
            self.factory.get("/admin/")
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("WWW-Authenticate", response)

    def test_wrong_password(self):
        response = self.middleware(
            self.factory.get(
                "/",
                HTTP_AUTHORIZATION=self.authorization(
                    "staging", "incorrect"
                ),
            )
        )
        self.assertEqual(response.status_code, 401)

    def test_malformed_credentials(self):
        response = self.middleware(
            self.factory.get(
                "/",
                HTTP_AUTHORIZATION="Basic !!!",
            )
        )
        self.assertEqual(response.status_code, 401)

    def test_wrong_username(self):
        response = self.middleware(
            self.factory.get(
                "/",
                HTTP_AUTHORIZATION=self.authorization(
                    "other", "synthetic-test-token-" * 3
                ),
            )
        )
        self.assertEqual(response.status_code, 401)

    def test_valid_credentials(self):
        response = self.middleware(
            self.factory.get(
                "/",
                HTTP_AUTHORIZATION=self.authorization(
                    "staging", "synthetic-test-token-" * 3
                ),
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Cache-Control"],
            "private, no-store",
        )

    def test_webhook_is_protected(self):
        response = self.middleware(
            self.factory.post(
                "/api/notifications/openwa/webhook/"
            )
        )
        self.assertEqual(response.status_code, 401)

    def test_static_files_are_protected(self):
        response = self.middleware(
            self.factory.get("/static/react/app.js")
        )
        self.assertEqual(response.status_code, 401)

    def test_similar_health_path_is_protected(self):
        response = self.middleware(
            self.factory.get("/healthz/private/")
        )
        self.assertEqual(response.status_code, 401)
