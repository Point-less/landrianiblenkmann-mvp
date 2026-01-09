import os
from typing import Any

from django.core.management import BaseCommand, call_command
from utils.services import S

DEFAULT_USERNAME = "admin"
DEFAULT_EMAIL = "admin@example.com"

# Allow operator to override the password (and username/email if desired) via env vars.
ENV_USERNAME = "BOOTSTRAP_ADMIN_USERNAME"
ENV_EMAIL = "BOOTSTRAP_ADMIN_EMAIL"
ENV_PASSWORD = "BOOTSTRAP_ADMIN_PASSWORD"


class Command(BaseCommand):
    help = "Apply migrations and ensure a default admin user exists."

    def handle(self, *args: Any, **options: Any) -> None:
        self.stdout.write("Applying database migrations...")
        call_command("migrate", interactive=False)

        username = os.environ.get(ENV_USERNAME, DEFAULT_USERNAME)
        email = os.environ.get(ENV_EMAIL, DEFAULT_EMAIL)
        password = os.environ.get(ENV_PASSWORD)

        try:
            S.users.BootstrapSuperuserService(username=username, email=email, password=password)
            self.stdout.write(self.style.SUCCESS("Bootstrap complete."))
        except ValueError as exc:
            self.stdout.write(self.style.ERROR(str(exc)))
            self.stdout.write(
                "Set BOOTSTRAP_ADMIN_PASSWORD and re-run `docker compose exec frontend python manage.py bootstrap`."
            )
