import logging
from django.db.utils import OperationalError, ProgrammingError
from django.conf import settings
from .models import SystemVersion
from .models import Notification

logger = logging.getLogger(__name__)

#Files version
VERSION = "1.2.3"

#General contect for the entire system
def database_version(request):
    """
    Context processor that provides the current database version.
    This is called on every request, ensuring the version is always up-to-date.
    """
    try:
        db_version = SystemVersion.get_current_version()
        return {'db_version': db_version or '0.0.0'}
    except (OperationalError, ProgrammingError) as e:
        logger.warning(f"Could not fetch database version: {e}")
        return {'db_version': '0.0.0'}

def app_version(request):
    """Context processor that provides the application version."""
    return {'app_version': VERSION}

def demo_mode_processor(request):
    """
    Context processor that provides demo mode settings to all templates.
    """
    return {
        'DEMO_MODE': getattr(settings, 'DEMO_MODE', False),
        'DEMO_REPO_URL': getattr(settings, 'DEMO_REPO_URL', '')
    }


def user_role_processor(request):
    """
    Context processor that provides user role information.
    Adds 'is_admin', 'is_parent', 'is_child' booleans and 'admin_warning_seen' to all templates.
    """
    if not request.user.is_authenticated:
        return {
            'is_admin': False,
            'is_parent': False,
            'is_child': False,
            'admin_warning_seen': True
        }

    from .models import FamilyMember

    try:
        member = FamilyMember.objects.filter(user=request.user).first()
        if not member:
            logger.debug(f"FamilyMember not found for user {request.user.username}")
            return {
                'is_admin': False,
                'is_parent': False,
                'is_child': False,
                'admin_warning_seen': True
            }

        admin_warning_seen = request.session.get('admin_warning_seen', False)
        return {
            'is_admin': member.role == 'ADMIN',
            'is_parent': member.role == 'PARENT',
            'is_child': member.role == 'CHILD',
            'admin_warning_seen': admin_warning_seen
        }
    except FamilyMember.DoesNotExist:
        logger.debug(f"FamilyMember.DoesNotExist for user {request.user.username}")
        return {
            'is_admin': False,
            'is_parent': False,
            'is_child': False,
            'admin_warning_seen': True
        }
    except Exception as e:
        logger.error(f"Unexpected error in user_role_processor for user {request.user.username}: {e}")
        return {
            'is_admin': False,
            'is_parent': False,
            'is_child': False,
            'admin_warning_seen': True
        }


def notifications_processor(request):
    """
    Context processor that adds unread notifications to all templates.
    """
    if not request.user.is_authenticated:
        logger.debug("notifications_processor: User not authenticated")
        return {
            'unread_notifications_count': 0,
            'unread_notifications': []
        }

    # Search for the current user's FamilyMember
    from .models import FamilyMember

    try:
        member = FamilyMember.objects.filter(user=request.user).first()
        if not member:
            logger.debug(f"notifications_processor: Member not found for user {request.user.username}")
            return {
                'unread_notifications_count': 0,
                'unread_notifications': []
            }

        logger.debug(f"notifications_processor: Loading notifications for {member.user.username} (ID: {member.id})")

        # Search for unrecognized notifications
        unread = Notification.objects.filter(
            member=member,
            is_acknowledged=False
        ).select_related('transaction', 'flow_group').order_by('-created_at')[:99]

        count = unread.count()
        logger.debug(f"notifications_processor: User {request.user.username} has {count} unread notifications")

        return {
            'unread_notifications_count': min(count, 99),
            'unread_notifications': list(unread)
        }

    except Exception as e:
        logger.error(f"Error loading notifications for user {request.user.username}: {e}", exc_info=True)
        return {
            'unread_notifications_count': 0,
            'unread_notifications': []
        }