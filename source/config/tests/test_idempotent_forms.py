from __future__ import annotations

import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Agent, Contact


class IdempotentFormTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser("admin", "admin@example.com", "pass")
        self.client.login(username="admin", password="pass")
        self.agent = Agent.objects.create(first_name="Idem", last_name="Potent")

    def _extract_token(self, response_content: bytes) -> str:
        match = re.search(rb'name="_idempotency_token" value="([a-f0-9]+)"', response_content)
        assert match, "idempotency token not found in form"
        return match.group(1).decode()

    def test_contact_create_is_idempotent(self):
        # GET form to obtain token
        resp = self.client.get(reverse("contact-create"))
        token = self._extract_token(resp.content)

        payload = {
            "first_name": "One",
            "last_name": "Shot",
            "email": "one@example.com",
            "agent": self.agent.pk,
            "_idempotency_token": token,
        }

        # First POST creates
        resp1 = self.client.post(reverse("contact-create"), data=payload, follow=False)
        self.assertEqual(resp1.status_code, 302)
        self.assertEqual(Contact.objects.filter(email="one@example.com").count(), 1)

        # Second POST with same token is treated as duplicate and does not create another
        resp2 = self.client.post(reverse("contact-create"), data=payload, follow=False)
        self.assertEqual(resp2.status_code, 302)
        self.assertEqual(Contact.objects.filter(email="one@example.com").count(), 1)
