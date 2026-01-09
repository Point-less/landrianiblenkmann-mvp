from django.core.management.base import BaseCommand
from django.core.management import call_command
from utils.services import S


class Command(BaseCommand):
    help = "Create demo users with roles/memberships to exercise permissions. Safe to re-run."

    def handle(self, *args, **options):
        call_command("seed_permissions")
        S.users.SeedDemoUsersService()
        self.stdout.write(self.style.SUCCESS("Demo users created/updated. Passwords: admin123 / manager123 / agent123 / viewer123"))
