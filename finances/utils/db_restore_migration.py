"""
Database Restore with Migration Support

This module handles restoring SQLite backups into PostgreSQL database.
It prepares the uploaded file and delegates to the main migration function.
"""

import logging
import tempfile
import sqlite3
from pathlib import Path
from django.utils.translation import gettext as _
import time

logger = logging.getLogger(__name__)


def restore_sqlite_backup_to_postgres(uploaded_file):
    """
    Restore a SQLite backup file into PostgreSQL database.

    This function saves the uploaded file and delegates to the main
    migrate_sqlite_to_postgres function from db_migration.py.

    Args:
        uploaded_file: Django UploadedFile object containing SQLite backup

    Returns:
        dict: {
            'success': bool,
            'family': dict (if success),
            'users': list (if success),
            'message': str,
            'error': str (if failure),
            'details': str (if failure)
        }
    """
    temp_sqlite_path = None

    try:
        logger.info(f"[RESTORE_MIGRATION] ========== STARTING SQLITE BACKUP RESTORE TO POSTGRESQL ==========")

        # STEP 1: Save uploaded SQLite file to temporary location
        temp_sqlite_path = Path(tempfile.gettempdir()) / f"restore_sqlite_{int(time.time())}.sqlite3"

        logger.info(f"[RESTORE_MIGRATION] Saving uploaded SQLite file to: {temp_sqlite_path}")
        with open(temp_sqlite_path, 'wb') as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)

        logger.info(f"[RESTORE_MIGRATION] SQLite file saved ({temp_sqlite_path.stat().st_size} bytes)")

        # STEP 2: Validate SQLite file integrity and read metadata
        logger.info(f"[RESTORE_MIGRATION] Validating SQLite database integrity")
        try:
            conn = sqlite3.connect(str(temp_sqlite_path))
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()

            if integrity_result[0] != 'ok':
                cursor.close()
                conn.close()
                logger.error(f"[RESTORE_MIGRATION] Integrity check failed: {integrity_result[0]}")
                return {
                    'success': False,
                    'error': _('SQLite backup file is corrupted and cannot be restored.'),
                    'details': f'Integrity check failed: {integrity_result[0]}'
                }

            logger.info(f"[RESTORE_MIGRATION] Integrity check PASSED")

            # Read metadata from SQLite backup
            family_info = None
            users_info = []

            try:
                cursor.execute("SELECT id, name FROM finances_family LIMIT 1")
                family_row = cursor.fetchone()

                if family_row:
                    family_id, family_name = family_row
                    family_info = {'id': family_id, 'name': family_name}
                    logger.info(f"[RESTORE_MIGRATION] Found family: '{family_name}' (ID: {family_id})")

                    cursor.execute("""
                        SELECT u.username, u.email, fm.role
                        FROM finances_familymember fm
                        JOIN finances_customuser u ON fm.user_id = u.id
                        WHERE fm.family_id = ?
                        ORDER BY fm.role, u.username
                    """, (family_id,))

                    for row in cursor.fetchall():
                        users_info.append({
                            'username': row[0],
                            'email': row[1] or '',
                            'role': row[2]
                        })
                    logger.info(f"[RESTORE_MIGRATION] Found {len(users_info)} users: {[u['username'] for u in users_info]}")
                else:
                    logger.warning(f"[RESTORE_MIGRATION] No family found in SQLite backup!")
            except Exception as meta_error:
                logger.warning(f"[RESTORE_MIGRATION] Could not read metadata: {meta_error}")

            cursor.close()
            conn.close()

        except sqlite3.DatabaseError as db_error:
            logger.error(f"[RESTORE_MIGRATION] SQLite error: {db_error}")
            return {
                'success': False,
                'error': _('SQLite backup file is corrupted: %(error)s') % {'error': str(db_error)},
                'details': str(db_error)
            }

        # STEP 3: Create backup of current PostgreSQL database
        logger.info(f"[RESTORE_MIGRATION] Creating backup of current PostgreSQL database")
        try:
            from finances.utils.db_backup import create_database_backup
            backup_result = create_database_backup()

            if backup_result['success']:
                logger.info(f"[RESTORE_MIGRATION] PostgreSQL backup created: {backup_result['filename']}")
            else:
                logger.warning(f"[RESTORE_MIGRATION] Could not create PostgreSQL backup: {backup_result.get('error')}")
                # Not fatal, continue with migration
        except Exception as backup_error:
            logger.warning(f"[RESTORE_MIGRATION] Could not create PostgreSQL backup: {backup_error}")
            # Not fatal, continue with migration

        # STEP 4: Delegate to main migration function
        logger.info(f"[RESTORE_MIGRATION] Delegating to main migration function...")

        from finances.utils.db_data_migration import migrate_sqlite_to_postgres
        migration_result = migrate_sqlite_to_postgres(temp_sqlite_path)

        if migration_result['success']:
            logger.info(f"[RESTORE_MIGRATION] ========== MIGRATION COMPLETED SUCCESSFULLY ==========")
            logger.info(f"[RESTORE_MIGRATION] Migrated: {family_info['name'] if family_info else 'Unknown'}")
            logger.info(f"[RESTORE_MIGRATION] Users: {len(users_info)}")

            # Create reload flag
            try:
                from finances.views.views_updater import create_reload_flag
                create_reload_flag()
                logger.info(f"[RESTORE_MIGRATION] Reload flag created")
            except Exception as e:
                logger.warning(f"[RESTORE_MIGRATION] Could not create reload flag: {e}")

            return {
                'success': True,
                'family': family_info if family_info else {'name': 'Unknown'},
                'users': users_info,
                'message': _('SQLite backup successfully migrated to PostgreSQL')
            }
        else:
            logger.error(f"[RESTORE_MIGRATION] Migration failed: {migration_result['message']}")
            return {
                'success': False,
                'error': _('Failed to migrate SQLite backup to PostgreSQL'),
                'details': migration_result.get('details', migration_result['message'])
            }

    except Exception as e:
        logger.error(f"[RESTORE_MIGRATION] Unexpected error during migration: {e}", exc_info=True)

        import traceback
        full_traceback = traceback.format_exc()
        logger.error(f"[RESTORE_MIGRATION] Full traceback:\n{full_traceback}")

        return {
            'success': False,
            'error': _('Migration failed: %(error)s') % {'error': str(e)},
            'details': full_traceback
        }

    finally:
        # Clean up temporary SQLite file
        if temp_sqlite_path and temp_sqlite_path.exists():
            try:
                temp_sqlite_path.unlink()
                logger.info(f"[RESTORE_MIGRATION] Temporary SQLite file deleted")
            except Exception as e:
                logger.warning(f"[RESTORE_MIGRATION] Could not delete temp SQLite file: {e}")
