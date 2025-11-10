# finances/management/commands/initial_deploy.py

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.utils import OperationalError

class Command(BaseCommand):
    help = 'Performs initial deployment setup for SweetMoney application'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-migrations',
            action='store_true',
            help='Skip running migrations',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('SweetMoney - Initial Deployment'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('')

        # Step 1: Run migrations
        if not options['skip_migrations']:
            self.stdout.write(self.style.WARNING('Step 1: Running database migrations...'))
            try:
                call_command('migrate', '--noinput', verbosity=1)
                self.stdout.write(self.style.SUCCESS('✓ Migrations completed successfully'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Migration failed: {str(e)}'))
                return
        else:
            self.stdout.write(self.style.WARNING('Step 1: Skipping migrations (--skip-migrations flag)'))
        
        self.stdout.write('')

        # Step 2: Check if users exist
        self.stdout.write(self.style.WARNING('Step 2: Checking for existing users...'))
        try:
            UserModel = get_user_model()
            user_count = UserModel.objects.count()
            
            if user_count > 0:
                self.stdout.write(self.style.SUCCESS(f'✓ Found {user_count} existing user(s)'))
                self.stdout.write(self.style.WARNING('  → Setup already complete'))
                self.stdout.write('')
                self.stdout.write(self.style.SUCCESS('Deployment check complete!'))
                self.stdout.write(self.style.SUCCESS('You can now start the server with: python manage.py runserver'))
            else:
                self.stdout.write(self.style.WARNING('✓ No users found - First time setup required'))
                self.stdout.write('')
                self.stdout.write(self.style.SUCCESS('=' * 70))
                self.stdout.write(self.style.SUCCESS('NEXT STEPS:'))
                self.stdout.write(self.style.SUCCESS('=' * 70))
                self.stdout.write('')
                self.stdout.write('1. Start the development server:')
                self.stdout.write(self.style.WARNING('   python manage.py runserver'))
                self.stdout.write('')
                self.stdout.write('2. Open your browser and navigate to:')
                self.stdout.write(self.style.WARNING('   http://localhost:8000/'))
                self.stdout.write('')
                self.stdout.write('3. You will be redirected to the setup page automatically')
                self.stdout.write('')
                self.stdout.write('4. Fill in the setup form to create your admin account')
                self.stdout.write('')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error checking users: {str(e)}'))
            return

        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('')
