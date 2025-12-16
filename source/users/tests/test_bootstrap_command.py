import os
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings


class BootstrapCommandTests(TestCase):
    def setUp(self):
        self.User = get_user_model()

    @override_settings(AUTH_PASSWORD_VALIDATORS=[])
    def test_creates_superuser_when_missing_and_password_provided(self):
        out = StringIO()
        os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "pass1234"
        call_command("bootstrap", stdout=out)

        self.assertTrue(self.User.objects.filter(username="admin", is_superuser=True).exists())
        self.assertIn("Bootstrap complete", out.getvalue())

    @override_settings(AUTH_PASSWORD_VALIDATORS=[])
    def test_updates_password_when_user_exists(self):
        self.User.objects.create_superuser("admin", "a@example.com", "oldpass")
        out = StringIO()
        os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "newpass"
        call_command("bootstrap", stdout=out)

        user = self.User.objects.get(username="admin")
        self.assertTrue(user.check_password("newpass"))
        self.assertIn("password updated", out.getvalue())

    def tearDown(self):
        os.environ.pop("BOOTSTRAP_ADMIN_PASSWORD", None)
