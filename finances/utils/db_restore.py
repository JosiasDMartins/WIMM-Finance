"""
Database Restore Utility

Provides a centralized function for restoring database backups.
Used by both Setup and Settings pages.

This implementation uses SQLite's native backup API which:
- Works transactionally (all-or-nothing)
- Handles file locks correctly
- Preserves all data integrity, foreign keys, and constraints
- Is portable and will work with any database backend in the future
"""

import sqlite3
import logging
import tempfile
from pathlib import Path
from datetime import datetime
from django.conf import settings
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


def restore_database_from_file(uploaded_file):
    """
    Restore database from an uploaded backup file using SQLite's native backup API.

    This function:
    1. Creates a lock file to prevent WebSocket connections
    2. Validates the uploaded database file
    3. Backs up the current database
    4. Uses SQLite's backup API to copy data from backup to current DB
    5. Verifies integrity
    6. Returns information about the restored database

    The backup API is superior to file copying because:
    - It works transactionally (atomic operation)
    - Handles file locks automatically
    - Preserves all constraints, indexes, and triggers
    - Works while database is in use
    - Will translate to PostgreSQL pg_restore in the future

    Args:
        uploaded_file: Django UploadedFile object containing the backup

    Returns:
        dict: {
            'success': bool,
            'family': dict or None,
            'users': list,
            'message': str,
            'error': str (only if success=False),
            'details': str (only if success=False)
        }
    """
    lock_file = Path(settings.BASE_DIR) / '.restore_lock'
    temp_backup_path = None
    backup_old = None

    try:
        # STEP 1: Create lock file to block new WebSocket connections
        lock_file.touch()
        logger.info(f"[DB_RESTORE] ========== RESTORE STARTED ==========")
        logger.info(f"[DB_RESTORE] Lock file created")

        # STEP 2: Close ALL database connections to prepare for restore
        from django.db import connections
        import gc
        import time

        logger.info(f"[DB_RESTORE] Closing {len(connections.all())} database connections")

        # Close all Django ORM connections
        for conn in connections.all():
            try:
                conn.close()
            except Exception as e:
                logger.warning(f"[DB_RESTORE] Error closing connection: {e}")

        # Close Channels layer if available
        try:
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            if channel_layer and hasattr(channel_layer, 'close'):
                logger.info(f"[DB_RESTORE] Closing channel layer")
                channel_layer.close()
        except Exception as e:
            logger.warning(f"[DB_RESTORE] No channel layer to close: {e}")

        # Force garbage collection
        gc.collect()
        time.sleep(1.0)
        logger.info(f"[DB_RESTORE] All connections closed")

        # Get database path
        db_path = Path(settings.DATABASES['default']['NAME'])
        logger.info(f"[DB_RESTORE] Target DB: {db_path}")

        # STEP 3: Save uploaded file to temporary location
        temp_backup_file = tempfile.NamedTemporaryFile(delete=False, suffix='.sqlite3')
        temp_backup_path = Path(temp_backup_file.name)
        temp_backup_file.close()

        logger.info(f"[DB_RESTORE] Saving uploaded file to: {temp_backup_path}")
        with open(temp_backup_path, 'wb') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        uploaded_size = temp_backup_path.stat().st_size
        logger.info(f"[DB_RESTORE] Upload complete, size: {uploaded_size} bytes")

        # STEP 4: Verify uploaded database integrity
        logger.info(f"[DB_RESTORE] Verifying uploaded database integrity")
        try:
            backup_conn = sqlite3.connect(str(temp_backup_path))
            cursor = backup_conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()

            if integrity_result[0] != 'ok':
                cursor.close()
                backup_conn.close()
                logger.error(f"[DB_RESTORE] Integrity check failed: {integrity_result[0]}")
                temp_backup_path.unlink()
                return {
                    'success': False,
                    'error': _('Uploaded database file is corrupted and cannot be restored.'),
                    'details': f'Integrity check failed: {integrity_result[0]}'
                }

            logger.info(f"[DB_RESTORE] Integrity check PASSED")

        except sqlite3.DatabaseError as db_error:
            logger.error(f"[DB_RESTORE] Database error: {db_error}")
            if temp_backup_path.exists():
                temp_backup_path.unlink()
            return {
                'success': False,
                'error': _('Uploaded database file is corrupted: %(error)s') % {'error': str(db_error)},
                'details': str(db_error)
            }

        # STEP 5: Read family and user info from backup BEFORE restore
        logger.info(f"[DB_RESTORE] Reading family and user info from backup")
        cursor.execute("SELECT id, name FROM finances_family LIMIT 1")
        family_row = cursor.fetchone()

        family_info = None
        users_info = []

        if family_row:
            family_id, family_name = family_row
            family_info = {'id': family_id, 'name': family_name}
            logger.info(f"[DB_RESTORE] Found family: '{family_name}' (ID: {family_id})")

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
            logger.info(f"[DB_RESTORE] Found {len(users_info)} users: {[u['username'] for u in users_info]}")
        else:
            logger.warning(f"[DB_RESTORE] No family found in uploaded database!")

        # CRITICAL: Close backup connection NOW to release file lock on temp file
        cursor.close()
        backup_conn.close()
        del cursor
        del backup_conn
        gc.collect()
        time.sleep(0.3)
        logger.info(f"[DB_RESTORE] Backup DB analysis complete, connection closed")

        # STEP 6: Create backup of current database (if exists)
        if db_path.exists():
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_old = db_path.parent / f'{db_path.stem}_pre_restore_{timestamp}{db_path.suffix}'
            try:
                logger.info(f"[DB_RESTORE] Creating safety backup: {backup_old.name}")

                # Use SQLite backup API for safety backup too
                current_conn = sqlite3.connect(str(db_path))
                backup_safety_conn = sqlite3.connect(str(backup_old))

                with backup_safety_conn:
                    current_conn.backup(backup_safety_conn)

                backup_safety_conn.close()
                current_conn.close()

                logger.info(f"[DB_RESTORE] Safety backup created ({backup_old.stat().st_size} bytes)")
            except Exception as backup_error:
                logger.error(f"[DB_RESTORE] Could not create safety backup: {backup_error}")
                # Not fatal, continue with restore

        # STEP 7: WIPE current database using SQLite commands
        # CRITICAL: Instead of deleting the file (which causes locks on Windows),
        # we WIPE all data using SQLite's own commands. This is transactional and
        # doesn't require file deletion, avoiding ALL file lock issues.
        logger.info(f"[DB_RESTORE] Wiping current database using SQLite DROP commands")

        if db_path.exists():
            try:
                # Close Django connections
                for conn in connections.all():
                    try:
                        conn.close()
                    except Exception:
                        pass
                gc.collect()
                time.sleep(0.5)

                # Connect to current DB and drop ALL tables
                logger.info(f"[DB_RESTORE] Opening current DB to drop all tables")
                wipe_conn = sqlite3.connect(str(db_path))
                wipe_cursor = wipe_conn.cursor()

                # Get list of all tables
                wipe_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
                tables = [row[0] for row in wipe_cursor.fetchall()]
                logger.info(f"[DB_RESTORE] Found {len(tables)} tables to drop: {tables[:10]}...")

                # Drop all tables
                wipe_cursor.execute("PRAGMA foreign_keys = OFF")  # Disable FK constraints
                for table in tables:
                    try:
                        wipe_cursor.execute(f"DROP TABLE IF EXISTS {table}")
                        logger.debug(f"[DB_RESTORE] Dropped table: {table}")
                    except Exception as drop_error:
                        logger.warning(f"[DB_RESTORE] Could not drop table {table}: {drop_error}")

                # Drop all indexes, views, triggers
                wipe_cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'")
                indexes = [row[0] for row in wipe_cursor.fetchall()]
                for index in indexes:
                    try:
                        wipe_cursor.execute(f"DROP INDEX IF EXISTS {index}")
                    except Exception:
                        pass

                wipe_cursor.execute("SELECT name FROM sqlite_master WHERE type='view'")
                views = [row[0] for row in wipe_cursor.fetchall()]
                for view in views:
                    try:
                        wipe_cursor.execute(f"DROP VIEW IF EXISTS {view}")
                    except Exception:
                        pass

                wipe_cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
                triggers = [row[0] for row in wipe_cursor.fetchall()]
                for trigger in triggers:
                    try:
                        wipe_cursor.execute(f"DROP TRIGGER IF EXISTS {trigger}")
                    except Exception:
                        pass

                # Commit all drops
                wipe_conn.commit()

                # VACUUM to reclaim space and reset file
                logger.info(f"[DB_RESTORE] Running VACUUM to reset database file")
                wipe_cursor.execute("VACUUM")

                # Close and cleanup
                wipe_cursor.close()
                wipe_conn.close()
                del wipe_cursor
                del wipe_conn
                gc.collect()

                logger.info(f"[DB_RESTORE] Database wiped successfully - all tables, indexes, views, triggers dropped")

            except Exception as wipe_error:
                logger.error(f"[DB_RESTORE] Error wiping database: {wipe_error}")

                # Try to restore safety backup
                if backup_old and backup_old.exists():
                    try:
                        # Use backup API to restore
                        restore_conn = sqlite3.connect(str(db_path))
                        safety_conn = sqlite3.connect(str(backup_old))
                        with restore_conn:
                            safety_conn.backup(restore_conn)
                        restore_conn.close()
                        safety_conn.close()
                        logger.info(f"[DB_RESTORE] Safety backup restored after wipe failure")
                    except Exception:
                        pass

                return {
                    'success': False,
                    'error': _('Could not wipe current database. Previous database may have been restored.'),
                    'details': str(wipe_error)
                }
        else:
            # Database doesn't exist, create empty one
            logger.info(f"[DB_RESTORE] Database doesn't exist, will create new one")
            db_path.parent.mkdir(parents=True, exist_ok=True)

        # STEP 8: Perform the actual restore using SQLite backup API
        logger.info(f"[DB_RESTORE] Starting database restore using SQLite backup API")

        try:
            # Open connections for backup operation
            # Source: backup file we uploaded
            # Target: NEW empty database file (will be created)
            logger.info(f"[DB_RESTORE] Opening source DB: {temp_backup_path}")
            source_conn = sqlite3.connect(str(temp_backup_path))

            logger.info(f"[DB_RESTORE] Creating new empty target DB: {db_path}")
            # Ensure target DB directory exists
            db_path.parent.mkdir(parents=True, exist_ok=True)
            # This will create a NEW empty database file
            target_conn = sqlite3.connect(str(db_path))

            # Use SQLite's backup API to copy from source to target
            # This is a transactional operation that handles everything correctly
            logger.info(f"[DB_RESTORE] Executing SQLite backup API (source -> new empty target)")

            def progress_callback(_status, remaining, total):
                """Callback to log progress during backup"""
                if total > 0:
                    percent = ((total - remaining) / total) * 100
                    logger.info(f"[DB_RESTORE] Progress: {percent:.1f}% ({total - remaining}/{total} pages)")

            # Perform the backup (copy from source to target)
            # backup() method signature: source.backup(target, pages=-1, progress=None)
            # We want to copy FROM uploaded file TO current database
            with target_conn:
                source_conn.backup(target_conn, pages=100, progress=progress_callback)

            logger.info(f"[DB_RESTORE] Backup API completed successfully")

            # Close connections
            source_conn.close()
            target_conn.close()

            del source_conn
            del target_conn
            gc.collect()
            time.sleep(0.3)

            logger.info(f"[DB_RESTORE] All restore connections closed")

        except sqlite3.Error as backup_error:
            logger.error(f"[DB_RESTORE] CRITICAL: SQLite backup failed: {backup_error}")

            # Try to restore safety backup
            if backup_old and backup_old.exists():
                try:
                    logger.info(f"[DB_RESTORE] Restoring safety backup due to error")
                    restore_conn = sqlite3.connect(str(db_path))
                    safety_conn = sqlite3.connect(str(backup_old))

                    with restore_conn:
                        safety_conn.backup(restore_conn)

                    restore_conn.close()
                    safety_conn.close()
                    logger.info(f"[DB_RESTORE] Safety backup restored")
                except Exception as restore_error:
                    logger.error(f"[DB_RESTORE] Failed to restore safety backup: {restore_error}")

            return {
                'success': False,
                'error': _('Database restore failed: %(error)s') % {'error': str(backup_error)},
                'details': str(backup_error)
            }

        except Exception as unexpected_error:
            logger.error(f"[DB_RESTORE] Unexpected error during backup: {unexpected_error}")

            # Try to restore safety backup
            if backup_old and backup_old.exists():
                try:
                    logger.info(f"[DB_RESTORE] Restoring safety backup due to error")
                    restore_conn = sqlite3.connect(str(db_path))
                    safety_conn = sqlite3.connect(str(backup_old))

                    with restore_conn:
                        safety_conn.backup(restore_conn)

                    restore_conn.close()
                    safety_conn.close()
                    logger.info(f"[DB_RESTORE] Safety backup restored")
                except Exception as restore_error:
                    logger.error(f"[DB_RESTORE] Failed to restore safety backup: {restore_error}")

            return {
                'success': False,
                'error': _('Unexpected error during restore: %(error)s') % {'error': str(unexpected_error)},
                'details': str(unexpected_error)
            }

        # STEP 8: Verify integrity of restored database
        try:
            logger.info(f"[DB_RESTORE] Verifying restored database integrity")
            verify_conn = sqlite3.connect(str(db_path))
            verify_cursor = verify_conn.cursor()
            verify_cursor.execute("PRAGMA integrity_check")
            verify_result = verify_cursor.fetchone()
            verify_cursor.close()
            verify_conn.close()
            del verify_cursor
            del verify_conn
            gc.collect()

            if verify_result[0] != 'ok':
                logger.error(f"[DB_RESTORE] Restored DB failed integrity check: {verify_result[0]}")

                # Restore safety backup
                if backup_old and backup_old.exists():
                    restore_conn = sqlite3.connect(str(db_path))
                    safety_conn = sqlite3.connect(str(backup_old))
                    with restore_conn:
                        safety_conn.backup(restore_conn)
                    restore_conn.close()
                    safety_conn.close()
                    logger.info(f"[DB_RESTORE] Safety backup restored")

                return {
                    'success': False,
                    'error': _('Restored database failed integrity check. Safety backup restored.'),
                    'details': f'Integrity check: {verify_result[0]}'
                }

            logger.info(f"[DB_RESTORE] Integrity check PASSED")

        except Exception as verify_error:
            logger.error(f"[DB_RESTORE] Error verifying restored DB: {verify_error}")

            # Restore safety backup
            if backup_old and backup_old.exists():
                try:
                    restore_conn = sqlite3.connect(str(db_path))
                    safety_conn = sqlite3.connect(str(backup_old))
                    with restore_conn:
                        safety_conn.backup(restore_conn)
                    restore_conn.close()
                    safety_conn.close()
                    logger.info(f"[DB_RESTORE] Safety backup restored")
                except Exception:
                    pass

            return {
                'success': False,
                'error': _('Error verifying restored database. Safety backup may have been restored.'),
                'details': str(verify_error)
            }

        # STEP 9: Close all Django connections to force reconnect
        logger.info(f"[DB_RESTORE] Forcing Django to reconnect to restored database")
        for conn in connections.all():
            conn.close()
        gc.collect()
        time.sleep(0.5)

        # STEP 10: Verify Django can read the restored database
        try:
            from django.contrib.auth import get_user_model
            UserModel = get_user_model()
            user_count = UserModel.objects.count()
            logger.info(f"[DB_RESTORE] SUCCESS! Django can read restored DB, found {user_count} users")

            if user_count == 0:
                logger.warning(f"[DB_RESTORE] WARNING: Restored database has 0 users!")

            # Verify the user count matches what we read from backup
            if user_count != len(users_info):
                logger.warning(f"[DB_RESTORE] User count mismatch! Backup had {len(users_info)}, DB has {user_count}")

        except Exception as db_read_error:
            logger.error(f"[DB_RESTORE] ERROR: Django cannot read restored database: {db_read_error}")

            # Restore safety backup
            if backup_old and backup_old.exists():
                try:
                    restore_conn = sqlite3.connect(str(db_path))
                    safety_conn = sqlite3.connect(str(backup_old))
                    with restore_conn:
                        safety_conn.backup(restore_conn)
                    restore_conn.close()
                    safety_conn.close()
                    logger.info(f"[DB_RESTORE] Safety backup restored")
                except Exception:
                    pass

            return {
                'success': False,
                'error': _('Restored database cannot be read by Django. Safety backup restored.'),
                'details': str(db_read_error)
            }

        # STEP 11: Create reload flag to signal server restart needed
        from finances.views.views_updater import create_reload_flag
        create_reload_flag()
        logger.info(f"[DB_RESTORE] Reload flag created")

        logger.info(f"[DB_RESTORE] ========== RESTORE COMPLETED SUCCESSFULLY ==========")
        logger.info(f"[DB_RESTORE] Restored: {family_info['name'] if family_info else 'Unknown'}")
        logger.info(f"[DB_RESTORE] Users: {len(users_info)}")

        return {
            'success': True,
            'family': family_info,
            'users': users_info,
            'message': _('Database restored successfully')
        }

    except Exception as e:
        logger.error(f"[DB_RESTORE] Unexpected error during restore: {e}", exc_info=True)

        # Try to restore safety backup
        if backup_old and backup_old.exists():
            try:
                db_path = Path(settings.DATABASES['default']['NAME'])
                restore_conn = sqlite3.connect(str(db_path))
                safety_conn = sqlite3.connect(str(backup_old))
                with restore_conn:
                    safety_conn.backup(restore_conn)
                restore_conn.close()
                safety_conn.close()
                logger.info(f"[DB_RESTORE] Safety backup restored after exception")
            except Exception:
                logger.error(f"[DB_RESTORE] Failed to restore safety backup after exception")

        return {
            'success': False,
            'error': f'Restore failed: {str(e)}',
            'details': str(e)
        }

    finally:
        # ALWAYS clean up temporary backup file (success or failure)
        if temp_backup_path and temp_backup_path.exists():
            # Try multiple times to delete temp file (might be locked)
            for cleanup_attempt in range(5):
                try:
                    temp_backup_path.unlink()
                    logger.info(f"[DB_RESTORE] Temporary backup file deleted")
                    break
                except PermissionError:
                    if cleanup_attempt < 4:
                        logger.debug(f"[DB_RESTORE] Temp file locked, retry {cleanup_attempt + 1}/5")
                        gc.collect()
                        time.sleep(0.5)
                    else:
                        logger.warning(f"[DB_RESTORE] Could not delete temp file after 5 attempts: {temp_backup_path}")
                except Exception as cleanup_error:
                    logger.warning(f"[DB_RESTORE] Could not delete temp file: {cleanup_error}")
                    break

        # Always remove lock file
        if lock_file.exists():
            for lock_attempt in range(3):
                try:
                    lock_file.unlink()
                    logger.info(f"[DB_RESTORE] Lock file removed")
                    break
                except Exception as lock_error:
                    if lock_attempt < 2:
                        time.sleep(0.2)
                    else:
                        logger.warning(f"[DB_RESTORE] Could not remove lock file: {lock_error}")
