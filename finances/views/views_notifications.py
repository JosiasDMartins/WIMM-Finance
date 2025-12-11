# finances/views/views_notifications.py

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.conf import settings
from ..models import Notification, FamilyMember
from ..notification_utils import check_and_create_notifications


@login_required
@require_http_methods(["GET"])
def get_notifications_ajax(request):
    """
    Returns unacknowledged user notifications in JSON format.
    """
    debug_enabled = getattr(settings, 'DEBUG', False)


    try:
        member = FamilyMember.objects.filter(user=request.user).first()
        if not member:

#        new_notifs = check_and_create_notifications(member.family, member)

        # Search for unrecognized notifications - NO TYPE FILTER
        notifications = Notification.objects.filter(
            member=member,
            is_acknowledged=False
        ).select_related('transaction', 'flow_group').order_by('-created_at')[:99]


        notifications_data = []
        for notif in notifications:
            notifications_data.append({
                'id': notif.id,
                'type': notif.notification_type,
                'message': notif.message,
                'target_url': notif.target_url,
                'created_at': notif.created_at.strftime('%Y-%m-%d %H:%M'),
            })

        return JsonResponse({
            'success': True,
            'count': len(notifications_data),
            'notifications': notifications_data
        })

    except Exception as e:
        if debug_enabled:
            print(f"[ERROR NOTIF API] Exception: {e}")
            import traceback
            traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def acknowledge_notification_ajax(request):
    """
    Mark a notification as acknowledged.
    """
    debug_enabled = getattr(settings, 'DEBUG', False)

    if debug_enabled:
        print(f"[DEBUG NOTIF ACK] acknowledge_notification_ajax called")

    try:
        notification_id = request.POST.get('notification_id')

        if debug_enabled:
            print(f"[DEBUG NOTIF ACK] Notification ID: {notification_id}")

        if not notification_id:
            return JsonResponse({'success': False, 'error': _('Notification ID required')}, status=400)

        member = FamilyMember.objects.filter(user=request.user).first()
        if not member:
            return JsonResponse({'success': False, 'error': _('Member not found')}, status=404)

        notification = Notification.objects.filter(
            id=notification_id,
            member=member
        ).first()

        if not notification:
            if debug_enabled:
                print(f"[ERROR NOTIF ACK] Notification {notification_id} not found for member {member.id}")
            return JsonResponse({'success': False, 'error': _('Notification not found')}, status=404)

        if debug_enabled:
            print(f"[DEBUG NOTIF ACK] Acknowledging notification {notification_id} (type: {notification.notification_type})")
        notification.acknowledge()

        # Returns updated count
        remaining_count = Notification.objects.filter(
            member=member,
            is_acknowledged=False
        ).count()

        if debug_enabled:
            print(f"[DEBUG NOTIF ACK] Remaining notifications: {remaining_count}")

        return JsonResponse({
            'success': True,
            'remaining_count': min(remaining_count, 99)
        })

    except Exception as e:
        if debug_enabled:
            print(f"[ERROR NOTIF ACK] Exception: {e}")
            import traceback
            traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def acknowledge_all_notifications_ajax(request):
    """
    It marks all user notifications as acknowledged.
    """
    debug_enabled = getattr(settings, 'DEBUG', False)

    if debug_enabled:
        print(f"[DEBUG NOTIF ACK ALL] acknowledge_all_notifications_ajax called")

    try:
        member = FamilyMember.objects.filter(user=request.user).first()
        if not member:
            return JsonResponse({'success': False, 'error': _('Member not found')}, status=404)

        # Atualiza todas as notificações não reconhecidas
        updated_count = Notification.objects.filter(
            member=member,
            is_acknowledged=False
        ).update(
            is_acknowledged=True,
            acknowledged_at=timezone.now()
        )

        if debug_enabled:
            print(f"[DEBUG NOTIF ACK ALL] Acknowledged {updated_count} notifications")

        return JsonResponse({
            'success': True,
            'acknowledged_count': updated_count,
            'remaining_count': 0
        })

    except Exception as e:
        if debug_enabled:
            print(f"[ERROR NOTIF ACK ALL] Exception: {e}")
            import traceback
            traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)