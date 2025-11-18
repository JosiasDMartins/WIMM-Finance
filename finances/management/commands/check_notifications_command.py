# finances/management/commands/check_notifications.py

from django.core.management.base import BaseCommand
from finances.models import Family, FamilyMember
from finances.notification_utils import check_and_create_notifications


class Command(BaseCommand):
    help = 'Check and create notifications for all family members'

    def add_arguments(self, parser):
        parser.add_argument(
            '--family-id',
            type=int,
            help='Check notifications only for a specific family ID',
        )

    def handle(self, *args, **options):
        family_id = options.get('family_id')
        
        if family_id:
            families = Family.objects.filter(id=family_id)
            if not families.exists():
                self.stdout.write(self.style.ERROR(f'Family with ID {family_id} not found'))
                return
        else:
            families = Family.objects.all()
        
        total_overdue = 0
        total_overbudget = 0
        
        for family in families:
            self.stdout.write(f'Checking notifications for family: {family.name}')
            
            for member in family.members.all():
                results = check_and_create_notifications(family, member)
                
                overdue = results['overdue']
                overbudget = results['overbudget']
                
                total_overdue += overdue
                total_overbudget += overbudget
                
                if overdue > 0 or overbudget > 0:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  {member.user.username}: {overdue} overdue, {overbudget} overbudget'
                        )
                    )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nTotal notifications created: {total_overdue} overdue, {total_overbudget} overbudget'
            )
        )
