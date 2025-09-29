from django.contrib.auth import get_user_model
from django.core.management import BaseCommand, call_command

DEFAULT_USERNAME = "admin"
DEFAULT_EMAIL = "admin@example.com"
DEFAULT_PASSWORD = "admin"


class Command(BaseCommand):
    help = "Apply migrations and ensure a default admin user exists."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE("Applying database migrations"))
        call_command("migrate", interactive=False)

        user_model = get_user_model()
        if user_model.objects.filter(username=DEFAULT_USERNAME).exists():
            self.stdout.write(
                self.style.WARNING(
                    f"Superuser '{DEFAULT_USERNAME}' already exists; skipping creation."
                )
            )
            return

        self.stdout.write(self.style.NOTICE(f"Creating superuser '{DEFAULT_USERNAME}'"))
        user_model.objects.create_superuser(
            username=DEFAULT_USERNAME,
            email=DEFAULT_EMAIL,
            password=DEFAULT_PASSWORD,
        )
        self.stdout.write(self.style.SUCCESS("Bootstrap complete."))
