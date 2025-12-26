"""
SQLite-specific database utilities.

This module provides all SQLite-specific operations including:
- Backup creation using SQLite native API
- Database restore using SQLite native API
- SQLite database detection and verification
"""

import os
import sqlite3
import logging
import tempfile
from pathlib import Path
from datetime import datetime
from django.conf import settings
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


# ============================================================
# SQLite Detection and Verification Functions
# ============================================================

def get_sqlite_path():
    """
    Get the path to the default SQLite database file.

    Returns:
        Path: Path to db.sqlite3 or None if not found
    """
    # Check environment variable first (Docker)
    db_path_env = os.environ.get('DB_PATH')
    if db_path_env:
        sqlite_path = Path(db_path_env)
        logger.info(f"[SQLITE_UTILS] Checking DB_PATH: {db_path_env}")
        if sqlite_path.exists():
            logger.info(f"[SQLITE_UTILS] Found SQLite at DB_PATH: {sqlite_path}")
            return sqlite_path
        else:
            logger.info(f"[SQLITE_UTILS] DB_PATH set but file not found: {db_path_env}")

    # Default SQLite location
    base_dir = Path(settings.BASE_DIR)
    sqlite_path = base_dir / 'db' / 'db.sqlite3'

    logger.info(f"[SQLITE_UTILS] Checking default location: {sqlite_path}")
    if sqlite_path.exists():
        logger.info(f"[SQLITE_UTILS] Found SQLite at default location: {sqlite_path}")
        return sqlite_path
    else:
        logger.info(f"[SQLITE_UTILS] SQLite not found at default location: {sqlite_path}")
        return None


def sqlite_has_data(sqlite_path):
    """
    Check if SQLite database has data (users or transactions).

    Args:
        sqlite_path (Path): Path to SQLite database

    Returns:
        bool: True if database has users, False otherwise
    """
    if not sqlite_path:
        logger.info(f"[SQLITE_UTILS] sqlite_path is None, cannot check for data")
        return False

    try:
        logger.info(f"[SQLITE_UTILS] Connecting to SQLite at: {sqlite_path}")
        conn = sqlite3.connect(str(sqlite_path))
        cursor = conn.cursor()

        # Check if 'finances_customuser' table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='finances_customuser'")
        user_table_exists = cursor.fetchone()

        if not user_table_exists:
            logger.info(f"[SQLITE_UTILS] SQLite has no 'finances_customuser' table")
            cursor.close()
            conn.close()
            return False

        # Check if 'finances_transaction' table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='finances_transaction'")
        transaction_table_exists = cursor.fetchone()

        if not transaction_table_exists:
            logger.info(f"[SQLITE_UTILS] SQLite has no 'finances_transaction' table")
            cursor.close()
            conn.close()
            return False

        # Check for users
        cursor.execute("SELECT COUNT(*) FROM finances_customuser")
        user_count = cursor.fetchone()[0]
        logger.info(f"[SQLITE_UTILS] SQLite has {user_count} users")

        # Check for transactions
        cursor.execute("SELECT COUNT(*) FROM finances_transaction")
        transaction_count = cursor.fetchone()[0]
        logger.info(f"[SQLITE_UTILS] SQLite has {transaction_count} transactions")

        cursor.close()
        conn.close()

        # Return True if there is any data
        return user_count > 0 or transaction_count > 0

    except Exception as e:
        logger.error(f"[SQLITE_UTILS] Error checking SQLite data: {e}", exc_info=True)
        return False


# ============================================================
# SQLite Backup Functions
# ============================================================

def create_sqlite_backup(family_id=None):
    """
    Create a backup of SQLite database.

    If family_id is provided, creates a family-isolated backup containing only
    data for that specific family. Otherwise, creates a full database backup.

    Args:
        family_id (int, optional): ID of the family to backup. If None, backs up entire database.

    Returns:
        dict: {'success': bool, 'backup_path': str, 'filename': str, 'size': int, 'error': str}
    """
    if family_id is not None:
        return _create_family_isolated_backup(family_id)
    else:
        return _create_full_sqlite_backup()


def _create_full_sqlite_backup():
    """
    Create a FULL backup of SQLite database using native backup API.
    This backs up the entire database with all families.

    Returns:
        dict: {'success': bool, 'backup_path': str, 'filename': str, 'error': str}
    """
    try:
        # Get database path
        db_path = Path(settings.DATABASES['default']['NAME'])

        if not db_path.exists():
            return {
                'success': False,
                'error': _('Database file not found')
            }

        # Create backups directory
        backups_dir = db_path.parent / 'backups'
        backups_dir.mkdir(parents=True, exist_ok=True)

        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'backup_full_{timestamp}.sqlite3'
        backup_path = backups_dir / backup_filename

        logger.info(f"[SQLITE_BACKUP] Creating FULL SQLite backup: {backup_path}")

        # Use SQLite backup API for transactional backup
        source_conn = sqlite3.connect(str(db_path))
        backup_conn = sqlite3.connect(str(backup_path))

        with backup_conn:
            source_conn.backup(backup_conn)

        source_conn.close()
        backup_conn.close()

        # Verify backup file was created
        if not backup_path.exists():
            return {
                'success': False,
                'error': _('Backup file was not created')
            }

        file_size = backup_path.stat().st_size
        logger.info(f"[SQLITE_BACKUP] FULL SQLite backup created successfully ({file_size} bytes)")

        return {
            'success': True,
            'backup_path': str(backup_path),
            'filename': backup_filename,
            'size': file_size
        }

    except Exception as e:
        logger.error(f"[SQLITE_BACKUP] FULL SQLite backup failed: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }


def _create_family_isolated_backup(family_id):
    """
    Create a family-isolated backup containing only data for a specific family.

    This creates a new SQLite database file with:
    - Only the specified family's data
    - All users that are members of that family
    - All periods, transactions, flow groups, etc. for that family
    - Proper schema structure that can be restored to a fresh SweetMoney instance

    Args:
        family_id (int): ID of the family to backup

    Returns:
        dict: {'success': bool, 'backup_path': str, 'filename': str, 'size': int, 'family_name': str, 'error': str}
    """
    try:
        from django.db import connection

        # Get database path
        db_path = Path(settings.DATABASES['default']['NAME'])

        if not db_path.exists():
            return {
                'success': False,
                'error': _('Database file not found')
            }

        # Create backups directory
        backups_dir = db_path.parent / 'backups'
        backups_dir.mkdir(parents=True, exist_ok=True)

        # Get family name for logging and filename
        from finances.models import Family
        try:
            family = Family.objects.get(id=family_id)
            family_name = family.name
        except Family.DoesNotExist:
            return {
                'success': False,
                'error': _('Family with ID %(family_id)s not found') % {'family_id': family_id}
            }

        # Generate backup filename with timestamp and family name
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Sanitize family name for filename (remove special chars)
        safe_family_name = "".join(c for c in family_name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_family_name = safe_family_name.replace(' ', '_')
        backup_filename = f'backup_{safe_family_name}_{timestamp}.sqlite3'
        backup_path = backups_dir / backup_filename

        logger.info(f"[SQLITE_FAMILY_BACKUP] Creating family-isolated backup for '{family_name}' (ID: {family_id})")
        logger.info(f"[SQLITE_FAMILY_BACKUP] Backup file: {backup_path}")

        # STEP 1: Create new empty SQLite database with same schema
        backup_conn = sqlite3.connect(str(backup_path))
        backup_cursor = backup_conn.cursor()

        # Get schema from source database
        source_conn = sqlite3.connect(str(db_path))
        source_cursor = source_conn.cursor()

        # Copy schema (CREATE TABLE statements)
        source_cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        tables_sql = source_cursor.fetchall()

        for (table_sql,) in tables_sql:
            if table_sql:  # Skip None values
                backup_cursor.execute(table_sql)
                logger.debug(f"[SQLITE_FAMILY_BACKUP] Created table from schema")

        # Copy indexes
        source_cursor.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%' AND sql IS NOT NULL")
        indexes_sql = source_cursor.fetchall()

        for (index_sql,) in indexes_sql:
            try:
                backup_cursor.execute(index_sql)
            except sqlite3.OperationalError as e:
                # Some indexes might fail if they're auto-created with tables
                logger.debug(f"[SQLITE_FAMILY_BACKUP] Skipped index (might be auto-created): {e}")

        backup_conn.commit()
        logger.info(f"[SQLITE_FAMILY_BACKUP] Schema created in backup database")

        # STEP 2: Get all user IDs that are members of this family
        source_cursor.execute("""
            SELECT DISTINCT user_id
            FROM finances_familymember
            WHERE family_id = ?
        """, (family_id,))
        user_ids = [row[0] for row in source_cursor.fetchall()]
        user_ids_str = ','.join('?' * len(user_ids))

        logger.info(f"[SQLITE_FAMILY_BACKUP] Found {len(user_ids)} users in family")

        # STEP 3: Get all family member IDs for this family
        source_cursor.execute("""
            SELECT id
            FROM finances_familymember
            WHERE family_id = ?
        """, (family_id,))
        member_ids = [row[0] for row in source_cursor.fetchall()]
        member_ids_str = ','.join('?' * len(member_ids))

        logger.info(f"[SQLITE_FAMILY_BACKUP] Found {len(member_ids)} family memberships")

        # STEP 4: Copy data table by table (in correct order to respect FK constraints)

        # Disable FK constraints temporarily for faster insertion
        backup_cursor.execute("PRAGMA foreign_keys = OFF")

        # Order matters! Tables without FK first, then tables that depend on them
        tables_to_copy = [
            # Core user and family tables
            ('finances_customuser', f'id IN ({user_ids_str})', user_ids),
            ('finances_family', 'id = ?', [family_id]),
            ('finances_familymember', 'family_id = ?', [family_id]),
            ('finances_familyconfiguration', 'family_id = ?', [family_id]),

            # Period and flow groups
            ('finances_period', 'family_id = ?', [family_id]),
            ('finances_flowgroup', 'family_id = ?', [family_id]),

            # Transactions (via member)
            ('finances_transaction', f'member_id IN ({member_ids_str})' if member_ids else '1=0', member_ids if member_ids else []),

            # History and access
            ('finances_familymemberrolehistory', f'member_id IN ({member_ids_str})' if member_ids else '1=0', member_ids if member_ids else []),
            ('finances_flowgroupaccess', f'member_id IN ({member_ids_str})' if member_ids else '1=0', member_ids if member_ids else []),

            # Investments and balances
            ('finances_investment', 'family_id = ?', [family_id]),
            ('finances_bankbalance', 'family_id = ?', [family_id]),

            # Notifications
            ('finances_notification', 'family_id = ?', [family_id]),
        ]

        total_rows_copied = 0

        for table_name, where_clause, params in tables_to_copy:
            try:
                # Get column names
                source_cursor.execute(f"PRAGMA table_info({table_name})")
                columns_info = source_cursor.fetchall()
                column_names = [col[1] for col in columns_info]
                columns_str = ', '.join(column_names)
                placeholders = ', '.join(['?'] * len(column_names))

                # Select data from source
                query = f"SELECT {columns_str} FROM {table_name} WHERE {where_clause}"
                source_cursor.execute(query, params)
                rows = source_cursor.fetchall()

                # Insert into backup
                if rows:
                    insert_query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
                    backup_cursor.executemany(insert_query, rows)
                    backup_conn.commit()
                    total_rows_copied += len(rows)
                    logger.info(f"[SQLITE_FAMILY_BACKUP] Copied {len(rows)} rows from {table_name}")
                else:
                    logger.debug(f"[SQLITE_FAMILY_BACKUP] No rows to copy from {table_name}")

            except sqlite3.OperationalError as e:
                # Table might not exist in this installation
                logger.warning(f"[SQLITE_FAMILY_BACKUP] Skipped table {table_name}: {e}")
                continue

        # Re-enable FK constraints
        backup_cursor.execute("PRAGMA foreign_keys = ON")
        backup_conn.commit()

        logger.info(f"[SQLITE_FAMILY_BACKUP] Total rows copied: {total_rows_copied}")

        # STEP 5: Copy Django migrations and other system tables
        system_tables = [
            'django_migrations',
            'django_content_type',
            'auth_permission',
            'django_admin_log',
            'django_session',
        ]

        for table_name in system_tables:
            try:
                source_cursor.execute(f"SELECT * FROM {table_name}")
                rows = source_cursor.fetchall()

                if rows:
                    # Get column count
                    placeholders = ', '.join(['?'] * len(rows[0]))
                    backup_cursor.executemany(f"INSERT INTO {table_name} VALUES ({placeholders})", rows)
                    backup_conn.commit()
                    logger.debug(f"[SQLITE_FAMILY_BACKUP] Copied {len(rows)} rows from system table {table_name}")

            except sqlite3.OperationalError as e:
                logger.debug(f"[SQLITE_FAMILY_BACKUP] Skipped system table {table_name}: {e}")
                continue

        # Close connections
        source_cursor.close()
        source_conn.close()
        backup_cursor.close()
        backup_conn.close()

        # Verify backup file
        if not backup_path.exists():
            return {
                'success': False,
                'error': _('Backup file was not created')
            }

        file_size = backup_path.stat().st_size
        logger.info(f"[SQLITE_FAMILY_BACKUP] Family-isolated backup created successfully")
        logger.info(f"[SQLITE_FAMILY_BACKUP] Family: {family_name}")
        logger.info(f"[SQLITE_FAMILY_BACKUP] File size: {file_size} bytes")
        logger.info(f"[SQLITE_FAMILY_BACKUP] Users: {len(user_ids)}")
        logger.info(f"[SQLITE_FAMILY_BACKUP] Total rows: {total_rows_copied}")

        return {
            'success': True,
            'backup_path': str(backup_path),
            'filename': backup_filename,
            'size': file_size,
            'family_name': family_name,
            'family_id': family_id,
            'users_count': len(user_ids),
            'rows_copied': total_rows_copied
        }

    except Exception as e:
        logger.error(f"[SQLITE_FAMILY_BACKUP] Family backup failed: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }


# ============================================================
# SQLite Restore Functions
# ============================================================

def restore_sqlite_from_file(uploaded_file):
    """
    Restore SQLite database from an uploaded backup file using SQLite's native backup API.

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
        logger.info(f"[SQLITE_RESTORE] ========== RESTORE STARTED ==========")
        logger.info(f"[SQLITE_RESTORE] Lock file created")

        # STEP 2: Close ALL database connections to prepare for restore
        from django.db import connections
        import gc
        import time

        logger.info(f"[SQLITE_RESTORE] Closing {len(connections.all())} database connections")

        # Close all Django ORM connections
        for conn in connections.all():
            try:
                conn.close()
            except Exception as e:
                logger.warning(f"[SQLITE_RESTORE] Error closing connection: {e}")

        # Close Channels layer if available
        try:
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            if channel_layer and hasattr(channel_layer, 'close'):
                logger.info(f"[SQLITE_RESTORE] Closing channel layer")
                channel_layer.close()
        except Exception as e:
            logger.warning(f"[SQLITE_RESTORE] No channel layer to close: {e}")

        # Force garbage collection
        gc.collect()
        time.sleep(1.0)
        logger.info(f"[SQLITE_RESTORE] All connections closed")

        # Get database path
        db_path = Path(settings.DATABASES['default']['NAME'])
        logger.info(f"[SQLITE_RESTORE] Target DB: {db_path}")

        # STEP 3: Save uploaded file to temporary location
        temp_backup_file = tempfile.NamedTemporaryFile(delete=False, suffix='.sqlite3')
        temp_backup_path = Path(temp_backup_file.name)
        temp_backup_file.close()

        logger.info(f"[SQLITE_RESTORE] Saving uploaded file to: {temp_backup_path}")
        with open(temp_backup_path, 'wb') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        uploaded_size = temp_backup_path.stat().st_size
        logger.info(f"[SQLITE_RESTORE] Upload complete, size: {uploaded_size} bytes")

        # STEP 4: Verify uploaded database integrity
        logger.info(f"[SQLITE_RESTORE] Verifying uploaded database integrity")
        try:
            backup_conn = sqlite3.connect(str(temp_backup_path))
            cursor = backup_conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()

            if integrity_result[0] != 'ok':
                cursor.close()
                backup_conn.close()
                logger.error(f"[SQLITE_RESTORE] Integrity check failed: {integrity_result[0]}")
                temp_backup_path.unlink()
                return {
                    'success': False,
                    'error': _('Uploaded database file is corrupted and cannot be restored.'),
                    'details': f'Integrity check failed: {integrity_result[0]}'
                }

            logger.info(f"[SQLITE_RESTORE] Integrity check PASSED")

        except sqlite3.DatabaseError as db_error:
            logger.error(f"[SQLITE_RESTORE] Database error: {db_error}")
            if temp_backup_path.exists():
                temp_backup_path.unlink()
            return {
                'success': False,
                'error': _('Uploaded database file is corrupted: %(error)s') % {'error': str(db_error)},
                'details': str(db_error)
            }

        # STEP 5: Read family and user info from backup BEFORE restore
        logger.info(f"[SQLITE_RESTORE] Reading family and user info from backup")
        cursor.execute("SELECT id, name FROM finances_family LIMIT 1")
        family_row = cursor.fetchone()

        family_info = None
        users_info = []

        if family_row:
            family_id, family_name = family_row
            family_info = {'id': family_id, 'name': family_name}
            logger.info(f"[SQLITE_RESTORE] Found family: '{family_name}' (ID: {family_id})")

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
            logger.info(f"[SQLITE_RESTORE] Found {len(users_info)} users: {[u['username'] for u in users_info]}")
        else:
            logger.warning(f"[SQLITE_RESTORE] No family found in uploaded database!")

        # CRITICAL: Close backup connection NOW to release file lock on temp file
        cursor.close()
        backup_conn.close()
        del cursor
        del backup_conn
        gc.collect()
        time.sleep(0.3)
        logger.info(f"[SQLITE_RESTORE] Backup DB analysis complete, connection closed")

        # STEP 6: Create backup of current database (if exists)
        if db_path.exists():
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_old = db_path.parent / f'{db_path.stem}_pre_restore_{timestamp}{db_path.suffix}'
            try:
                logger.info(f"[SQLITE_RESTORE] Creating safety backup: {backup_old.name}")

                # Use SQLite backup API for safety backup too
                current_conn = sqlite3.connect(str(db_path))
                backup_safety_conn = sqlite3.connect(str(backup_old))

                with backup_safety_conn:
                    current_conn.backup(backup_safety_conn)

                backup_safety_conn.close()
                current_conn.close()

                logger.info(f"[SQLITE_RESTORE] Safety backup created ({backup_old.stat().st_size} bytes)")
            except Exception as backup_error:
                logger.error(f"[SQLITE_RESTORE] Could not create safety backup: {backup_error}")
                # Not fatal, continue with restore

        # STEP 7: WIPE current database using SQLite commands
        logger.info(f"[SQLITE_RESTORE] Wiping current database using SQLite DROP commands")

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
                logger.info(f"[SQLITE_RESTORE] Opening current DB to drop all tables")
                wipe_conn = sqlite3.connect(str(db_path))
                wipe_cursor = wipe_conn.cursor()

                # Get list of all tables
                wipe_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
                tables = [row[0] for row in wipe_cursor.fetchall()]
                logger.info(f"[SQLITE_RESTORE] Found {len(tables)} tables to drop")

                # Drop all tables
                wipe_cursor.execute("PRAGMA foreign_keys = OFF")  # Disable FK constraints
                for table in tables:
                    try:
                        wipe_cursor.execute(f"DROP TABLE IF EXISTS {table}")
                    except Exception as drop_error:
                        logger.warning(f"[SQLITE_RESTORE] Could not drop table {table}: {drop_error}")

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
                logger.info(f"[SQLITE_RESTORE] Running VACUUM to reset database file")
                wipe_cursor.execute("VACUUM")

                # Close and cleanup
                wipe_cursor.close()
                wipe_conn.close()
                del wipe_cursor
                del wipe_conn
                gc.collect()

                logger.info(f"[SQLITE_RESTORE] Database wiped successfully")

            except Exception as wipe_error:
                logger.error(f"[SQLITE_RESTORE] Error wiping database: {wipe_error}")

                # Try to restore safety backup
                if backup_old and backup_old.exists():
                    try:
                        restore_conn = sqlite3.connect(str(db_path))
                        safety_conn = sqlite3.connect(str(backup_old))
                        with restore_conn:
                            safety_conn.backup(restore_conn)
                        restore_conn.close()
                        safety_conn.close()
                        logger.info(f"[SQLITE_RESTORE] Safety backup restored after wipe failure")
                    except Exception:
                        pass

                return {
                    'success': False,
                    'error': _('Could not wipe current database. Previous database may have been restored.'),
                    'details': str(wipe_error)
                }
        else:
            # Database doesn't exist, create empty one
            logger.info(f"[SQLITE_RESTORE] Database doesn't exist, will create new one")
            db_path.parent.mkdir(parents=True, exist_ok=True)

        # STEP 8: Perform the actual restore using SQLite backup API
        logger.info(f"[SQLITE_RESTORE] Starting database restore using SQLite backup API")

        try:
            # Open connections for backup operation
            logger.info(f"[SQLITE_RESTORE] Opening source DB: {temp_backup_path}")
            source_conn = sqlite3.connect(str(temp_backup_path))

            logger.info(f"[SQLITE_RESTORE] Creating new empty target DB: {db_path}")
            db_path.parent.mkdir(parents=True, exist_ok=True)
            target_conn = sqlite3.connect(str(db_path))

            # Use SQLite's backup API to copy from source to target
            logger.info(f"[SQLITE_RESTORE] Executing SQLite backup API (source -> target)")

            def progress_callback(_status, remaining, total):
                """Callback to log progress during backup"""
                if total > 0:
                    percent = ((total - remaining) / total) * 100
                    logger.info(f"[SQLITE_RESTORE] Progress: {percent:.1f}% ({total - remaining}/{total} pages)")

            # Perform the backup (copy from source to target)
            with target_conn:
                source_conn.backup(target_conn, pages=100, progress=progress_callback)

            logger.info(f"[SQLITE_RESTORE] Backup API completed successfully")

            # Close connections
            source_conn.close()
            target_conn.close()
            del source_conn
            del target_conn
            gc.collect()
            time.sleep(0.3)

            logger.info(f"[SQLITE_RESTORE] All restore connections closed")

        except sqlite3.Error as backup_error:
            logger.error(f"[SQLITE_RESTORE] CRITICAL: SQLite backup failed: {backup_error}")

            # Try to restore safety backup
            if backup_old and backup_old.exists():
                try:
                    logger.info(f"[SQLITE_RESTORE] Restoring safety backup due to error")
                    restore_conn = sqlite3.connect(str(db_path))
                    safety_conn = sqlite3.connect(str(backup_old))
                    with restore_conn:
                        safety_conn.backup(restore_conn)
                    restore_conn.close()
                    safety_conn.close()
                    logger.info(f"[SQLITE_RESTORE] Safety backup restored")
                except Exception as restore_error:
                    logger.error(f"[SQLITE_RESTORE] Failed to restore safety backup: {restore_error}")

            return {
                'success': False,
                'error': _('Database restore failed: %(error)s') % {'error': str(backup_error)},
                'details': str(backup_error)
            }

        # STEP 9: Verify integrity of restored database
        try:
            logger.info(f"[SQLITE_RESTORE] Verifying restored database integrity")
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
                logger.error(f"[SQLITE_RESTORE] Restored DB failed integrity check: {verify_result[0]}")

                # Restore safety backup
                if backup_old and backup_old.exists():
                    restore_conn = sqlite3.connect(str(db_path))
                    safety_conn = sqlite3.connect(str(backup_old))
                    with restore_conn:
                        safety_conn.backup(restore_conn)
                    restore_conn.close()
                    safety_conn.close()
                    logger.info(f"[SQLITE_RESTORE] Safety backup restored")

                return {
                    'success': False,
                    'error': _('Restored database failed integrity check. Safety backup restored.'),
                    'details': f'Integrity check: {verify_result[0]}'
                }

            logger.info(f"[SQLITE_RESTORE] Integrity check PASSED")

        except Exception as verify_error:
            logger.error(f"[SQLITE_RESTORE] Error verifying restored DB: {verify_error}")

            # Restore safety backup
            if backup_old and backup_old.exists():
                try:
                    restore_conn = sqlite3.connect(str(db_path))
                    safety_conn = sqlite3.connect(str(backup_old))
                    with restore_conn:
                        safety_conn.backup(restore_conn)
                    restore_conn.close()
                    safety_conn.close()
                    logger.info(f"[SQLITE_RESTORE] Safety backup restored")
                except Exception:
                    pass

            return {
                'success': False,
                'error': _('Error verifying restored database. Safety backup may have been restored.'),
                'details': str(verify_error)
            }

        # STEP 10: Close all Django connections to force reconnect
        logger.info(f"[SQLITE_RESTORE] Forcing Django to reconnect to restored database")
        for conn in connections.all():
            conn.close()
        gc.collect()
        time.sleep(0.5)

        # STEP 11: Verify Django can read the restored database
        try:
            from django.contrib.auth import get_user_model
            UserModel = get_user_model()
            user_count = UserModel.objects.count()
            logger.info(f"[SQLITE_RESTORE] SUCCESS! Django can read restored DB, found {user_count} users")

            if user_count == 0:
                logger.warning(f"[SQLITE_RESTORE] WARNING: Restored database has 0 users!")

            # Verify the user count matches what we read from backup
            if user_count != len(users_info):
                logger.warning(f"[SQLITE_RESTORE] User count mismatch! Backup had {len(users_info)}, DB has {user_count}")

        except Exception as db_read_error:
            logger.error(f"[SQLITE_RESTORE] ERROR: Django cannot read restored database: {db_read_error}")

            # Restore safety backup
            if backup_old and backup_old.exists():
                try:
                    restore_conn = sqlite3.connect(str(db_path))
                    safety_conn = sqlite3.connect(str(backup_old))
                    with restore_conn:
                        safety_conn.backup(restore_conn)
                    restore_conn.close()
                    safety_conn.close()
                    logger.info(f"[SQLITE_RESTORE] Safety backup restored")
                except Exception:
                    pass

            return {
                'success': False,
                'error': _('Restored database cannot be read by Django. Safety backup restored.'),
                'details': str(db_read_error)
            }

        # STEP 12: Create reload flag to signal server restart needed
        from finances.views.views_updater import create_reload_flag
        create_reload_flag()
        logger.info(f"[SQLITE_RESTORE] Reload flag created")

        logger.info(f"[SQLITE_RESTORE] ========== RESTORE COMPLETED SUCCESSFULLY ==========")
        logger.info(f"[SQLITE_RESTORE] Restored: {family_info['name'] if family_info else 'Unknown'}")
        logger.info(f"[SQLITE_RESTORE] Users: {len(users_info)}")

        return {
            'success': True,
            'family': family_info,
            'users': users_info,
            'message': _('Database restored successfully')
        }

    except Exception as e:
        logger.error(f"[SQLITE_RESTORE] Unexpected error during restore: {e}", exc_info=True)

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
                logger.info(f"[SQLITE_RESTORE] Safety backup restored after exception")
            except Exception:
                logger.error(f"[SQLITE_RESTORE] Failed to restore safety backup after exception")

        return {
            'success': False,
            'error': f'Restore failed: {str(e)}',
            'details': str(e)
        }

    finally:
        # ALWAYS clean up temporary backup file (success or failure)
        if temp_backup_path and temp_backup_path.exists():
            import gc
            import time
            # Try multiple times to delete temp file (might be locked)
            for cleanup_attempt in range(5):
                try:
                    temp_backup_path.unlink()
                    logger.info(f"[SQLITE_RESTORE] Temporary backup file deleted")
                    break
                except PermissionError:
                    if cleanup_attempt < 4:
                        logger.debug(f"[SQLITE_RESTORE] Temp file locked, retry {cleanup_attempt + 1}/5")
                        gc.collect()
                        time.sleep(0.5)
                    else:
                        logger.warning(f"[SQLITE_RESTORE] Could not delete temp file after 5 attempts: {temp_backup_path}")
                except Exception as cleanup_error:
                    logger.warning(f"[SQLITE_RESTORE] Could not delete temp file: {cleanup_error}")
                    break

        # Always remove lock file
        if lock_file.exists():
            import time
            for lock_attempt in range(3):
                try:
                    lock_file.unlink()
                    logger.info(f"[SQLITE_RESTORE] Lock file removed")
                    break
                except Exception as lock_error:
                    if lock_attempt < 2:
                        time.sleep(0.2)
                    else:
                        logger.warning(f"[SQLITE_RESTORE] Could not remove lock file: {lock_error}")
