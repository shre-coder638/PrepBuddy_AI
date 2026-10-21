
import json

from django.test import TestCase
from django.urls import reverse

from .models import PrepProtocol, PrepStep


class ProtocolAPITests(TestCase):
    def setUp(self):
        self.url = reverse("protocol-list")

    def test_get_returns_protocols_and_steps(self):
        protocol = PrepProtocol.objects.create(
            name="Test protocol",
            description="Demo only",
        )
        PrepStep.objects.create(
            protocol=protocol,
            title="First step",
            instruction="Demo instruction",
            minutes_before_procedure=120,
            requires_confirmation=True,
            is_critical=False,
            order=0,
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = response.json()["protocols"]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "Test protocol")
        self.assertEqual(data[0]["step_count"], 1)
        self.assertEqual(data[0]["steps"][0]["title"], "First step")

    def test_post_creates_protocol_and_steps(self):
        payload = {
            "name": "Demo protocol",
            "description": "For interface testing only",
            "is_active": True,
            "steps": [
                {
                    "title": "First demo step",
                    "instruction": "Demo instruction one",
                    "minutes_before_procedure": 120,
                    "requires_confirmation": True,
                    "is_critical": False,
                    "order": 0,
                },
                {
                    "title": "Second demo step",
                    "instruction": "Demo instruction two",
                    "minutes_before_procedure": 60,
                    "requires_confirmation": False,
                    "is_critical": True,
                    "order": 1,
                },
            ],
        }

        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(PrepProtocol.objects.count(), 1)
        self.assertEqual(PrepStep.objects.count(), 2)

        result = response.json()["protocol"]
        self.assertEqual(result["name"], "Demo protocol")
        self.assertEqual(result["step_count"], 2)
        self.assertTrue(result["steps"][1]["is_critical"])

    def test_post_rejects_missing_name(self):
        payload = {
            "name": " ",
            "steps": [
                {
                    "title": "Demo step",
                    "instruction": "Demo instruction",
                    "minutes_before_procedure": 60,
                }
            ],
        }

        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.json()["errors"])
        self.assertEqual(PrepProtocol.objects.count(), 0)

    def test_post_rejects_empty_steps(self):
        response = self.client.post(
            self.url,
            data=json.dumps({
                "name": "Demo protocol",
                "steps": [],
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("steps", response.json()["errors"])
        self.assertEqual(PrepProtocol.objects.count(), 0)

    def test_get_endpoint_rejects_put(self):
        response = self.client.put(self.url)

        self.assertEqual(response.status_code, 405)
