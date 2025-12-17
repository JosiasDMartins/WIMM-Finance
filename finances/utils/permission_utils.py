"""
Permission utility functions for access control.

This module handles permission-related operations including:
- Checking if a user can access a FlowGroup
"""

import logging
from ..models import FamilyMember

logger = logging.getLogger(__name__)


def user_can_access_flow_group(user, flow_group):
    """
    Checks if the user has access to the FlowGroup.
    This is a wrapper for can_access_flow_group that accepts User instead of FamilyMember.
    Uses the complete access logic including role checks, shared groups, and kids groups.
    """
    from ..views.views_utils import can_access_flow_group

    try:
        member = user.memberships.get(family=flow_group.family)
        return can_access_flow_group(flow_group, member)
    except FamilyMember.DoesNotExist:
        return False
    except Exception:
        # Catch any other unexpected errors
        return False
