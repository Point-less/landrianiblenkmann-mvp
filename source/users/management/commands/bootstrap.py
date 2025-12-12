import os

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand, call_command

DEFAULT_USERNAME = "admin"
DEFAULT_EMAIL = "admin@example.com"

# Allow operator to override the password (and username/email if desired) via env vars.
ENV_USERNAME = "BOOTSTRAP_ADMIN_USERNAME"
ENV_EMAIL = "BOOTSTRAP_ADMIN_EMAIL"
ENV_PASSWORD = "BOOTSTRAP_ADMIN_PASSWORD"


class Command(BaseCommand):
    help = "Apply migrations and ensure a default admin user exists."

    def handle(self, *args, **options):
        self.stdout.write("Applying database migrations...")
        call_command("migrate", interactive=False)

        user_model = get_user_model()

        username = os.environ.get(ENV_USERNAME, DEFAULT_USERNAME)
        email = os.environ.get(ENV_EMAIL, DEFAULT_EMAIL)
        password = os.environ.get(ENV_PASSWORD)

        existing = user_model.objects.filter(username=username).first()

        if existing:
            if password:
                existing.set_password(password)
                existing.email = email
                existing.save(update_fields=["password", "email", "updated_at" if hasattr(existing, "updated_at") else "email"])
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Superuser '{username}' already existed; password updated from {ENV_PASSWORD}."
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Superuser '{username}' already exists; set {ENV_PASSWORD} to update its password."
                    )
                )
            return

        if not password:
            # Avoid creating a predictable password if operator forgot to set one.
            self.stdout.write(
                self.style.ERROR(
                    f"Environment variable {ENV_PASSWORD} is required to create superuser '{username}'."
                )
            )
            self.stdout.write(
                "Set it and re-run `docker compose exec frontend python manage.py bootstrap`."
            )
            return

        self.stdout.write(f"Creating superuser '{username}'")
        user_model.objects.create_superuser(
            username=username,
            email=email,
            password=password,
        )
        self.stdout.write(self.style.SUCCESS("Bootstrap complete."))
