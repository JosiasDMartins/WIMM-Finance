"""
Role history utility functions for tracking member role changes.

This module handles role history operations including:
- Getting member role for a specific period
- Saving role history when roles change
"""

import logging
from ..models import FamilyMemberRoleHistory

logger = logging.getLogger(__name__)


def get_member_role_for_period(member, period_start_date):
    """
    Gets the role a member had during a specific period.
    Uses FamilyMemberRoleHistory to track historical roles.
    Falls back to current role if no history exists.
    """
    try:
        role_history = FamilyMemberRoleHistory.objects.filter(
            member=member,
            period_start_date__lte=period_start_date
        ).order_by('-period_start_date').first()

        if role_history:
            return role_history.role
    except FamilyMemberRoleHistory.DoesNotExist:
        pass
    except Exception:
        # Unexpected error - fallback to current role
        pass

    return member.role


def save_role_history_if_changed(member, new_role, period_start_date):
    """
    Saves role history if the role changed.
    Should be called when updating a member's role.
    """
    current_role = get_member_role_for_period(member, period_start_date)

    if current_role != new_role:
        FamilyMemberRoleHistory.objects.update_or_create(
            member=member,
            period_start_date=period_start_date,
            defaults={'role': new_role}
        )

        member.role = new_role
        member.save()
