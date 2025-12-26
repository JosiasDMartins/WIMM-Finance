from django.contrib import admin

# Django admin is DISABLED for SweetMoney
#
# SweetMoney uses a custom family-based permission system instead of Django's
# built-in admin/superuser system. See finances/permissions.py for details.
#
# User roles (ADMIN/PARENT/CHILD) are managed through the FamilyMember model,
# not through Django's is_superuser/is_staff flags.
#
# To create users:
# - First user: Access /setup/ page (creates family + admin user)
# - Additional users: Use the user management interface (requires ADMIN or PARENT role)
#
# The Django admin interface (django.contrib.admin) is disabled in settings.py
# and the /admin/ URL is not registered in urls.py.
#
# If you need to re-enable Django admin for debugging:
# 1. Uncomment 'django.contrib.admin' in INSTALLED_APPS (settings.py)
# 2. Uncomment path('admin/', admin.site.urls) in urls.py
# 3. Register models here using @admin.register() decorators
#
# Register your models here (if admin is re-enabled):
