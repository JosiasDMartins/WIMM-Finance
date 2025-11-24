from django.db.utils import OperationalError, ProgrammingError
from django.conf import settings
from .models import SystemVersion
from .models import Notification

#Files version
VERSION = "1.1.1"

#General contect for the entire system
def database_version(request):
    """
    Context processor that provides the current database version.
    This is called on every request, ensuring the version is always up-to-date.
    """
    try:
        db_version = SystemVersion.get_current_version()
        if db_version is None or db_version == '' or db_version.strip() == '':
            db_version = "0.0.0"
        return {'db_version': db_version}
    except (OperationalError, ProgrammingError):
        return {'db_version': '0.0.0'}

def app_version(request):
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
    Adds 'is_admin' boolean to all templates.
    """
    if not request.user.is_authenticated:
        return {'is_admin': False}

    from .models import FamilyMember

    try:
        member = FamilyMember.objects.filter(user=request.user).first()
        if member and member.role == 'ADMIN':
            return {'is_admin': True}
        return {'is_admin': False}
    except Exception:
        return {'is_admin': False}


def notifications_processor(request):
    """
    Context processor que adiciona notificações não reconhecidas a todos os templates.
    """
    # Only show debug messages if DEBUG is enabled
    debug_enabled = getattr(settings, 'DEBUG', False)

    if debug_enabled:
        print(f"[DEBUG CONTEXT] notifications_processor called for user: {request.user}")

    if not request.user.is_authenticated:
        if debug_enabled:
            print(f"[DEBUG CONTEXT] User not authenticated")
        return {
            'unread_notifications_count': 0,
            'unread_notifications': []
        }

    # Search for the current user's FamilyMember
    from .models import FamilyMember

    try:
        member = FamilyMember.objects.filter(user=request.user).first()
        if not member:
            if debug_enabled:
                print(f"[DEBUG CONTEXT] Member not found for user: {request.user.username}")
            return {
                'unread_notifications_count': 0,
                'unread_notifications': []
            }

        if debug_enabled:
            print(f"[DEBUG CONTEXT] Member found: {member.user.username} (ID: {member.id})")

        # Search for unrecognized notifications
        unread = Notification.objects.filter(
            member=member,
            is_acknowledged=False
        ).select_related('transaction', 'flow_group').order_by('-created_at')[:99]

        count = unread.count()

        if debug_enabled:
            print(f"[DEBUG CONTEXT] Unread notifications count: {count}")
            for notif in unread[:5]:  # Log only the first 5
                print(f"[DEBUG CONTEXT]   - ID: {notif.id}, Type: {notif.notification_type}, Message: {notif.message}")

        return {
            'unread_notifications_count': min(count, 99),
            'unread_notifications': list(unread)
        }

    except Exception as e:
        if debug_enabled:
            print(f"[ERROR CONTEXT] Exception: {e}")
            import traceback
            traceback.print_exc()
        return {
            'unread_notifications_count': 0,
            'unread_notifications': []
        }