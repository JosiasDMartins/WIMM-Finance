# finances/permissions.py

"""
User permission helpers for the WIMM Finance application.

Permission hierarchy:
- ADMIN: Full access to all user management functions
  - Can create, edit, delete, and change passwords for all user types (ADMIN, PARENT, CHILD)

- PARENT: Limited user management
  - Can only edit own profile and change own password
  - Can create, edit, delete, and change passwords for CHILD users

- CHILD: Self-management only
  - Can only edit own profile and change own password
"""

from django.contrib import messages
from django.shortcuts import redirect


def can_create_user(requesting_member, target_role):
    """
    Check if a member can create a user with the specified role.

    Args:
        requesting_member: FamilyMember instance of the user making the request
        target_role: Role of the user to be created ('ADMIN', 'PARENT', or 'CHILD')

    Returns:
        bool: True if the user has permission, False otherwise
    """
    if requesting_member.role == 'ADMIN':
        # Admin can create any type of user
        return True
    elif requesting_member.role == 'PARENT':
        # Parent can only create CHILD users
        return target_role == 'CHILD'
    else:
        # CHILD users cannot create other users
        return False


def can_edit_user(requesting_member, target_member):
    """
    Check if a member can edit another member's information.

    Args:
        requesting_member: FamilyMember instance of the user making the request
        target_member: FamilyMember instance of the user to be edited

    Returns:
        bool: True if the user has permission, False otherwise
    """
    # Users can always edit themselves
    if requesting_member.id == target_member.id:
        return True

    # Admin can edit anyone
    if requesting_member.role == 'ADMIN':
        return True

    # Parent can edit CHILD users
    if requesting_member.role == 'PARENT' and target_member.role == 'CHILD':
        return True

    # All other cases: no permission
    return False


def can_change_password(requesting_member, target_member):
    """
    Check if a member can change another member's password.

    Args:
        requesting_member: FamilyMember instance of the user making the request
        target_member: FamilyMember instance of the user whose password will be changed

    Returns:
        bool: True if the user has permission, False otherwise
    """
    # Users can always change their own password
    if requesting_member.id == target_member.id:
        return True

    # Admin can change anyone's password
    if requesting_member.role == 'ADMIN':
        return True

    # Parent can change CHILD users' passwords
    if requesting_member.role == 'PARENT' and target_member.role == 'CHILD':
        return True

    # All other cases: no permission
    return False


def can_delete_user(requesting_member, target_member):
    """
    Check if a member can delete another member.

    Args:
        requesting_member: FamilyMember instance of the user making the request
        target_member: FamilyMember instance of the user to be deleted

    Returns:
        bool: True if the user has permission, False otherwise
    """
    # Users cannot delete themselves
    if requesting_member.id == target_member.id:
        return False

    # Admin can delete anyone (except themselves, checked above)
    if requesting_member.role == 'ADMIN':
        return True

    # Parent can delete CHILD users
    if requesting_member.role == 'PARENT' and target_member.role == 'CHILD':
        return True

    # All other cases: no permission
    return False


def require_user_creation_permission(view_func):
    """
    Decorator to ensure user has permission to create users.
    Checks form data to determine target role.
    """
    def wrapper(request, *args, **kwargs):
        from .views.views_utils import get_family_context

        family, current_member, _ = get_family_context(request.user)
        if not family:
            messages.error(request, 'User is not associated with a family.')
            return redirect('dashboard')

        # Get target role from POST data
        target_role = request.POST.get('role', 'CHILD')

        if not can_create_user(current_member, target_role):
            messages.error(request, 'You do not have permission to create this type of user.')
            return redirect('configuration')

        return view_func(request, *args, **kwargs)

    return wrapper


def require_user_edit_permission(view_func):
    """
    Decorator to ensure user has permission to edit a specific member.
    """
    def wrapper(request, member_id, *args, **kwargs):
        from .views.views_utils import get_family_context
        from .models import FamilyMember
        from django.shortcuts import get_object_or_404

        family, current_member, _ = get_family_context(request.user)
        if not family:
            messages.error(request, 'User is not associated with a family.')
            return redirect('dashboard')

        target_member = get_object_or_404(FamilyMember, id=member_id, family=family)

        if not can_edit_user(current_member, target_member):
            messages.error(request, 'You do not have permission to edit this user.')
            return redirect('configuration')

        return view_func(request, member_id, *args, **kwargs)

    return wrapper


def require_user_delete_permission(view_func):
    """
    Decorator to ensure user has permission to delete a specific member.
    """
    def wrapper(request, member_id, *args, **kwargs):
        from .views.views_utils import get_family_context
        from .models import FamilyMember
        from django.shortcuts import get_object_or_404

        family, current_member, _ = get_family_context(request.user)
        if not family:
            messages.error(request, 'User is not associated with a family.')
            return redirect('dashboard')

        target_member = get_object_or_404(FamilyMember, id=member_id, family=family)

        if not can_delete_user(current_member, target_member):
            messages.error(request, 'You do not have permission to delete this user.')
            return redirect('configuration')

        return view_func(request, member_id, *args, **kwargs)

    return wrapper
