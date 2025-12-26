"""
Database Backup and Restore Views

This module handles all backup and restore operations for both SQLite and PostgreSQL.
"""

import logging
import tempfile
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse, FileResponse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST, require_http_methods

logger = logging.getLogger(__name__)


@require_http_methods(["POST"])
def create_backup(request):
    """Create a backup of the database.

    Automatically detects database backend (SQLite or PostgreSQL)
    and uses the appropriate backup strategy.

    IMPORTANT: This creates a FAMILY-ISOLATED backup containing ONLY the current user's family data.
    This allows families to export their data and import it into their own self-hosted instance.
    """
    # Block backups in demo mode
    if getattr(settings, 'DEMO_MODE', False):
        return JsonResponse({'success': False, 'error': _('Database backups are disabled in demo mode.')}, status=403)

    try:
        # Get current user's family ID
        from finances.models import FamilyMember

        user = request.user
        logger.info(f"[CREATE_BACKUP] Backup requested by user: {user.username}")

        # Get the user's family (assuming user belongs to one family)
        try:
            family_member = FamilyMember.objects.filter(user=user).first()
            if not family_member:
                logger.error(f"[CREATE_BACKUP] User {user.username} is not a member of any family")
                return JsonResponse({
                    'success': False,
                    'error': _('You are not a member of any family. Cannot create backup.')
                }, status=400)

            family_id = family_member.family_id
            family_name = family_member.family.name
            logger.info(f"[CREATE_BACKUP] Creating FAMILY-ISOLATED backup for family: {family_name} (ID: {family_id})")

        except Exception as e:
            logger.error(f"[CREATE_BACKUP] Error getting user's family: {e}")
            return JsonResponse({
                'success': False,
                'error': _('Error determining your family. Please contact an administrator.')
            }, status=500)

        # Use centralized backup function that handles both SQLite and PostgreSQL
        from finances.utils.db_backup import create_database_backup as create_db_backup

        # Create FAMILY-ISOLATED backup
        result = create_db_backup(family_id=family_id)

        if result['success']:
            backup_path = Path(result['backup_path'])
            filename = result['filename']

            logger.info(f"[CREATE_BACKUP] Family-isolated backup created successfully: {filename}")
            logger.info(f"[CREATE_BACKUP] Family: {result.get('family_name')}")
            logger.info(f"[CREATE_BACKUP] Users: {result.get('users_count')}")
            logger.info(f"[CREATE_BACKUP] Rows: {result.get('rows_copied')}")

            return JsonResponse({
                'success': True,
                'message': _('Family backup created successfully for %(family)s') % {'family': family_name},
                'filename': filename,
                'download_url': f'/download-backup/{filename}/',
                'size': result.get('size', 0),
                'family_name': result.get('family_name'),
                'users_count': result.get('users_count'),
                'rows_copied': result.get('rows_copied')
            })
        else:
            error_msg = result.get('error', 'Unknown error creating backup')
            logger.error(f"[CREATE_BACKUP] Failed: {error_msg}")
            return JsonResponse({'success': False, 'error': error_msg}, status=500)

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"[CREATE_BACKUP] Exception: {error_detail}")
        return JsonResponse({'success': False, 'error': f'Server error: {str(e)}'}, status=500)


@require_http_methods(["GET"])
def download_backup(request, filename):
    """Provides a downloadable backup file."""
    # Block backup downloads in demo mode
    if getattr(settings, 'DEMO_MODE', False):
        return JsonResponse({'error': _('Backup downloads are disabled in demo mode.')}, status=403)

    try:
        # Try both possible backup locations
        # Location 1: db/backups (PostgreSQL backups and SQLite backups)
        backup_path = Path(settings.BASE_DIR) / 'db' / 'backups' / filename

        # Location 2: Old location for backwards compatibility
        if not backup_path.exists():
            backup_path = Path(settings.BASE_DIR) / 'backups' / filename

        if not backup_path.exists():
            logger.error(f"[DOWNLOAD_BACKUP] File not found: {filename}")
            logger.error(f"[DOWNLOAD_BACKUP] Tried paths:")
            logger.error(f"  - {Path(settings.BASE_DIR) / 'db' / 'backups' / filename}")
            logger.error(f"  - {Path(settings.BASE_DIR) / 'backups' / filename}")
            return JsonResponse({'error': _('Backup file not found')}, status=404)

        # Security check: ensure file is within allowed backup directories
        allowed_dirs = [
            str(Path(settings.BASE_DIR) / 'db' / 'backups'),
            str(Path(settings.BASE_DIR) / 'backups')
        ]

        resolved_path = str(backup_path.resolve())
        if not any(resolved_path.startswith(allowed_dir) for allowed_dir in allowed_dirs):
            logger.error(f"[DOWNLOAD_BACKUP] Security violation: {resolved_path} not in allowed dirs")
            return JsonResponse({'error': _('Invalid file path')}, status=403)

        logger.info(f"[DOWNLOAD_BACKUP] Serving file: {backup_path}")

        response = FileResponse(open(backup_path, 'rb'), as_attachment=True)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

    except Exception as e:
        logger.error(f"[DOWNLOAD_BACKUP] Error: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["POST"])
def restore_backup(request):
    """Restores the database from a backup file.

    Supports all restore scenarios:
    - SQLite → SQLite (transactional restore)
    - SQLite → PostgreSQL (migration with confirmation)
    - PostgreSQL → PostgreSQL (transactional restore with backup)
    - PostgreSQL → SQLite (blocked with error message)
    """
    # Block database restore in demo mode
    if getattr(settings, 'DEMO_MODE', False):
        return JsonResponse({'success': False, 'error': _('Database restore is disabled in demo mode.')}, status=403)

    # Validate file upload
    if 'backup_file' not in request.FILES:
        return JsonResponse({'success': False, 'error': _('No backup file provided')}, status=400)

    backup_file = request.FILES['backup_file']

    # STEP 1: Detect current database engine
    db_engine = settings.DATABASES['default']['ENGINE']

    if 'sqlite3' in db_engine:
        current_db_type = 'sqlite'
    elif 'postgresql' in db_engine:
        current_db_type = 'postgresql'
    else:
        return JsonResponse({
            'success': False,
            'error': _('Unsupported database engine: %(engine)s') % {'engine': db_engine}
        }, status=400)

    logger.info(f"[RESTORE_BACKUP] Current database type: {current_db_type}")

    # STEP 2: Save uploaded file to temporary location to detect type
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.backup')
    temp_path = Path(temp_file.name)
    temp_file.close()

    try:
        with open(temp_path, 'wb') as f:
            for chunk in backup_file.chunks():
                f.write(chunk)

        logger.info(f"[RESTORE_BACKUP] Backup file saved to temp: {temp_path}")

        # STEP 3: Detect backup file type
        from finances.utils.db_utils_common import detect_backup_type
        backup_file_type = detect_backup_type(temp_path)

        logger.info(f"[RESTORE_BACKUP] Backup file type: {backup_file_type}")

        if backup_file_type == 'unknown':
            return JsonResponse({
                'success': False,
                'error': _('Could not determine backup file type. Please ensure this is a valid SQLite or PostgreSQL backup file.')
            }, status=400)

        # STEP 4: Check if migration is needed and if confirmation was provided
        migration_needed = (backup_file_type == 'sqlite' and current_db_type == 'postgresql')
        migration_confirmed = request.POST.get('confirm_migration') == 'true'

        logger.info(f"[RESTORE_BACKUP] Migration needed: {migration_needed}, Confirmed: {migration_confirmed}")

        # STEP 5: Handle different restore scenarios

        # SCENARIO 1: PostgreSQL → SQLite (BLOCKED)
        if backup_file_type == 'postgresql' and current_db_type == 'sqlite':
            logger.error(f"[RESTORE_BACKUP] Attempted to restore PostgreSQL backup to SQLite system")
            return JsonResponse({
                'success': False,
                'error': _('Cannot restore PostgreSQL backup to SQLite database'),
                'details': _('Your system is currently running with SQLite database, but you are trying to restore a PostgreSQL backup. This operation is not supported. Please restore a SQLite backup file instead.')
            }, status=400)

        # SCENARIO 2: SQLite → PostgreSQL (MIGRATION - needs confirmation)
        elif backup_file_type == 'sqlite' and current_db_type == 'postgresql':
            if not migration_confirmed:
                # Return special response asking for confirmation
                logger.info(f"[RESTORE_BACKUP] Migration required, asking for confirmation")
                return JsonResponse({
                    'success': False,
                    'needs_migration_confirmation': True,
                    'backup_type': 'sqlite',
                    'current_db_type': 'postgresql',
                    'error': _('Migration Required'),
                    'message': _('The backup file is from SQLite, but your system is running PostgreSQL. The data will be migrated from SQLite to PostgreSQL. This operation will drop all current data in PostgreSQL. Do you want to proceed?')
                }, status=200)  # Not an error, just asking for confirmation
            else:
                # Confirmation received, proceed with migration
                logger.info(f"[RESTORE_BACKUP] Migration confirmed, proceeding")

                # Reopen file for migration function
                with open(temp_path, 'rb') as f:
                    from django.core.files.uploadedfile import InMemoryUploadedFile
                    from io import BytesIO

                    file_content = f.read()
                    backup_file_for_migration = InMemoryUploadedFile(
                        BytesIO(file_content),
                        'backup_file',
                        'backup.sqlite3',
                        'application/octet-stream',
                        len(file_content),
                        None
                    )

                from finances.utils.db_restore_migration import restore_sqlite_backup_to_postgres
                result = restore_sqlite_backup_to_postgres(backup_file_for_migration)

        # SCENARIO 3: SQLite → SQLite (TRANSACTIONAL RESTORE)
        elif backup_file_type == 'sqlite' and current_db_type == 'sqlite':
            logger.info(f"[RESTORE_BACKUP] SQLite to SQLite restore")

            # Reopen file for restore function
            with open(temp_path, 'rb') as f:
                from django.core.files.uploadedfile import InMemoryUploadedFile
                from io import BytesIO

                file_content = f.read()
                backup_file_for_restore = InMemoryUploadedFile(
                    BytesIO(file_content),
                    'backup_file',
                    'backup.sqlite3',
                    'application/octet-stream',
                    len(file_content),
                    None
                )

            from finances.utils.db_utils_sqlite import restore_sqlite_from_file
            result = restore_sqlite_from_file(backup_file_for_restore)

        # SCENARIO 4: PostgreSQL → PostgreSQL (TRANSACTIONAL RESTORE)
        elif backup_file_type == 'postgresql' and current_db_type == 'postgresql':
            logger.info(f"[RESTORE_BACKUP] PostgreSQL to PostgreSQL restore")

            # Reopen file for restore function
            with open(temp_path, 'rb') as f:
                from django.core.files.uploadedfile import InMemoryUploadedFile
                from io import BytesIO

                file_content = f.read()
                backup_file_for_restore = InMemoryUploadedFile(
                    BytesIO(file_content),
                    'backup_file',
                    'backup.dump',
                    'application/octet-stream',
                    len(file_content),
                    None
                )

            from finances.utils.db_utils_pgsql import restore_postgres_from_file
            result = restore_postgres_from_file(backup_file_for_restore)

        else:
            # Should never reach here
            logger.error(f"[RESTORE_BACKUP] Unexpected scenario: {backup_file_type} → {current_db_type}")
            return JsonResponse({
                'success': False,
                'error': _('Unexpected restore scenario')
            }, status=500)

    finally:
        # Clean up temporary file
        try:
            if temp_path.exists():
                temp_path.unlink()
                logger.info(f"[RESTORE_BACKUP] Temporary file deleted")
        except Exception as e:
            logger.warning(f"[RESTORE_BACKUP] Could not delete temp file: {e}")

    # Handle result
    if not result['success']:
        return JsonResponse(result, status=400 if 'corrupted' in result.get('error', '') else 500)

    # Create JSON response
    response = JsonResponse(result)

    # CRITICAL: Delete the session cookie to prevent loops
    # The old session from the previous DB no longer exists in the restored DB
    session_cookie_name = settings.SESSION_COOKIE_NAME
    response.delete_cookie(
        session_cookie_name,
        path=settings.SESSION_COOKIE_PATH,
        domain=settings.SESSION_COOKIE_DOMAIN,
    )

    return response
