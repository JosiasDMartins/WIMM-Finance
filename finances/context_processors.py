from django.db.utils import OperationalError, ProgrammingError
from .models import SystemVersion
from .models import Notification

#Files version
VERSION = "1.0.0-alpha5"


#Legacy - This is the var name used at views_updater
db_version = None
try:
    db_version = SystemVersion.get_current_version()
except (OperationalError, ProgrammingError):
    pass
    
if db_version is None or db_version == '' or db_version.strip() == '':
    db_version = "0.0.0"

#General contect for the entire system
def database_version(request):
    
    try:        
        return {'db_version': db_version or '0.0.0'}
    except:
        return {'db_version': '0.0.0'}

def app_version(request):
    return {'app_version': VERSION}


def notifications_processor(request):
    """
    Context processor que adiciona notificações não reconhecidas a todos os templates.
    """
    print(f"[DEBUG CONTEXT] notifications_processor called for user: {request.user}")
    
    if not request.user.is_authenticated:
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
            print(f"[DEBUG CONTEXT] Member not found for user: {request.user.username}")
            return {
                'unread_notifications_count': 0,
                'unread_notifications': []
            }
        
        print(f"[DEBUG CONTEXT] Member found: {member.user.username} (ID: {member.id})")
        
        # Search for unrecognized notifications
        unread = Notification.objects.filter(
            member=member,
            is_acknowledged=False
        ).select_related('transaction', 'flow_group').order_by('-created_at')[:99]
        
        count = unread.count()
        print(f"[DEBUG CONTEXT] Unread notifications count: {count}")
        
        for notif in unread[:5]:  # Log only the first 5
            print(f"[DEBUG CONTEXT]   - ID: {notif.id}, Type: {notif.notification_type}, Message: {notif.message}")
        
        return {
            'unread_notifications_count': min(count, 99),
            'unread_notifications': list(unread)
        }
    
    except Exception as e:
        print(f"[ERROR CONTEXT] Exception: {e}")
        import traceback
        traceback.print_exc()
        return {
            'unread_notifications_count': 0,
            'unread_notifications': []
        }