# finances/management/commands/init_system_version.py
"""
Django management command to initialize system version in database.
Run this after migrations if the update modal is not appearing.

Usage:
    python manage.py init_system_version
    python manage.py init_system_version --version 0.0.0
"""

from django.core.management.base import BaseCommand
from finances.models import SystemVersion


class Command(BaseCommand):
    help = 'Initializes system version in database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--version',
            type=str,
            default='0.0.0',
            help='Version to set (default: 0.0.0, which will trigger updates)'
        )

    def handle(self, *args, **options):
        version = options['version']
        
        self.stdout.write(self.style.WARNING('Initializing system version...'))
        
        try:
            # Check if version already exists
            current = SystemVersion.get_current_version()
            
            if current:
                self.stdout.write(self.style.WARNING(f'Current version in DB: {current}'))
                confirm = input(f'Do you want to change it to {version}? (yes/no): ')
                if confirm.lower() != 'yes':
                    self.stdout.write(self.style.WARNING('Operation cancelled.'))
                    return
            
            # Set version
            SystemVersion.set_version(version)
            
            self.stdout.write(self.style.SUCCESS(f'✓ System version set to: {version}'))
            
            if version == '0.0.0':
                self.stdout.write(self.style.WARNING('\nℹ️  Version set to 0.0.0'))
                self.stdout.write(self.style.WARNING('   This will trigger the update modal on next page load.'))
                self.stdout.write(self.style.WARNING('   All update scripts will be available to apply.'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error: {str(e)}'))
            raise
