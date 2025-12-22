"""
Django management command to manually initialize the database.

Usage:
    python manage.py initdb

This is useful for Docker containers or situations where apps.py
hasn't run yet but database initialization is needed.
"""
from django.core.management.base import BaseCommand
from finances.utils.db_startup import initialize_database


class Command(BaseCommand):
    help = 'Initialize database (create if needed, run migrations, migrate SQLite data if applicable)'

    def handle(self, *args, **options):
        """Execute database initialization."""
        self.stdout.write("[INITDB] Starting manual database initialization...")

        result = initialize_database()

        if result.get('success'):
            self.stdout.write(self.style.SUCCESS(f"[OK] {result['message']}"))
            if result.get('details'):
                for detail in result['details']:
                    self.stdout.write(f"   - {detail}")
            # Return success (Django expects None or 0)
        else:
            self.stdout.write(self.style.ERROR(f"[ERROR] {result['message']}"))
            # Raise exception to indicate failure
            raise Exception(result['message'])
