"""
Automatic database migration from SQLite to PostgreSQL.

This module detects if:
1. A SQLite database exists with data (users)
2. PostgreSQL is configured as the primary database
3. PostgreSQL database is empty or doesn't have the data yet

If all conditions are met, it automatically migrates data from SQLite to PostgreSQL.
"""

import os
import sys
import logging
import sqlite3
import tempfile
from pathlib import Path
from django.conf import settings
from django.core.management import call_command
from django.db import connection, connections
from io import StringIO

logger = logging.getLogger(__name__)


def get_sqlite_path():
    """
    Get the path to the default SQLite database file.

    Returns:
        Path: Path to db.sqlite3 or None if not found
    """
    # Default SQLite location
    base_dir = Path(settings.BASE_DIR)
    sqlite_path = base_dir / 'db' / 'db.sqlite3'

    return sqlite_path if sqlite_path.exists() else None


def sqlite_has_data(sqlite_path):
    """
    Check if SQLite database has data (specifically users).

    Args:
        sqlite_path (Path): Path to SQLite database

    Returns:
        bool: True if database has users, False otherwise
    """
    try:
        conn = sqlite3.connect(str(sqlite_path))
        cursor = conn.cursor()

        # Check if auth_user table exists and has data
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='auth_user'")
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return False

        cursor.execute("SELECT COUNT(*) FROM auth_user")
        user_count = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        return user_count > 0

    except Exception as e:
        logger.error(f"[DB_MIGRATION] Error checking SQLite data: {e}")
        return False


def postgres_is_configured():
    """
    Check if PostgreSQL is configured as the primary database.

    Returns:
        bool: True if PostgreSQL is configured, False otherwise
    """
    db_engine = settings.DATABASES['default']['ENGINE']
    return 'postgresql' in db_engine


def postgres_has_data():
    """
    Check if PostgreSQL database already has data (users).

    Returns:
        bool: True if database has users, False otherwise
    """
    try:
        from django.contrib.auth import get_user_model
        UserModel = get_user_model()

        # Try to count users
        user_count = UserModel.objects.count()
        return user_count > 0

    except Exception as e:
        # Table might not exist yet
        logger.debug(f"[DB_MIGRATION] Could not check PostgreSQL data: {e}")
        return False


def should_migrate():
    """
    Determine if automatic migration should occur.

    Logic:
    - SQLite database exists AND has data (users)
    - PostgreSQL is configured as primary database
    - PostgreSQL is empty (no users yet)

    Returns:
        tuple: (should_migrate: bool, sqlite_path: Path|None, reason: str)
    """
    # Check if SQLite exists
    sqlite_path = get_sqlite_path()
    if not sqlite_path:
        return False, None, "No SQLite database found"

    # Check if SQLite has data
    if not sqlite_has_data(sqlite_path):
        return False, None, "SQLite database is empty (no users)"

    # Check if PostgreSQL is configured
    if not postgres_is_configured():
        return False, None, "PostgreSQL is not configured as primary database"

    # Check if PostgreSQL already has data
    if postgres_has_data():
        return False, None, "PostgreSQL already has data (migration not needed)"

    return True, sqlite_path, "All conditions met for migration"


def migrate_sqlite_to_postgres(sqlite_path):
    """
    Migrate data from SQLite to PostgreSQL.

    Process:
    1. Temporarily reconfigure Django to use SQLite
    2. Export data using dumpdata
    3. Reconfigure Django to use PostgreSQL
    4. Run migrations to create tables
    5. Import data using loaddata
    6. Reset sequences
    7. Rename SQLite file to .migrated

    Args:
        sqlite_path (Path): Path to SQLite database

    Returns:
        dict: {'success': bool, 'message': str, 'details': str}
    """
    logger.info(f"[DB_MIGRATION] ========== STARTING AUTOMATIC MIGRATION ==========")
    logger.info(f"[DB_MIGRATION] SQLite: {sqlite_path}")
    logger.info(f"[DB_MIGRATION] Target: PostgreSQL")

    temp_dump_file = None
    original_db_config = None

    try:
        # STEP 1: Save original PostgreSQL configuration
        original_db_config = settings.DATABASES['default'].copy()
        logger.info(f"[DB_MIGRATION] Saved PostgreSQL config")

        # STEP 2: Temporarily switch to SQLite to export data
        logger.info(f"[DB_MIGRATION] Switching to SQLite for data export")
        settings.DATABASES['default'] = {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': str(sqlite_path),
        }

        # Close any existing connections
        connections.close_all()

        # STEP 3: Export data from SQLite
        logger.info(f"[DB_MIGRATION] Exporting data from SQLite using dumpdata")
        temp_dump_file = Path(tempfile.gettempdir()) / 'sqlite_migration_dump.json'

        with open(temp_dump_file, 'w', encoding='utf-8') as f:
            try:
                call_command(
                    'dumpdata',
                    natural_foreign=True,
                    natural_primary=True,
                    exclude=['contenttypes', 'auth.permission'],
                    stdout=f,
                    verbosity=2
                )
            except Exception as e:
                logger.error(f"[DB_MIGRATION] Dumpdata failed: {e}")
                raise

        logger.info(f"[DB_MIGRATION] Data exported successfully ({temp_dump_file.stat().st_size} bytes)")

        # STEP 4: Switch back to PostgreSQL
        logger.info(f"[DB_MIGRATION] Switching to PostgreSQL")
        settings.DATABASES['default'] = original_db_config
        connections.close_all()

        # STEP 5: Run migrations on PostgreSQL to create tables
        logger.info(f"[DB_MIGRATION] Running migrations on PostgreSQL")
        try:
            call_command('migrate', verbosity=2, interactive=False)
        except Exception as e:
            logger.error(f"[DB_MIGRATION] Migration failed: {e}")
            raise

        # STEP 6: Load data into PostgreSQL
        logger.info(f"[DB_MIGRATION] Loading data into PostgreSQL")
        try:
            call_command('loaddata', str(temp_dump_file), verbosity=2)
        except Exception as e:
            logger.error(f"[DB_MIGRATION] Loaddata failed: {e}")
            raise

        logger.info(f"[DB_MIGRATION] Data loaded successfully")

        # STEP 7: Reset PostgreSQL sequences
        logger.info(f"[DB_MIGRATION] Resetting PostgreSQL sequences")
        try:
            # Get SQL to reset sequences
            sql_output = StringIO()
            call_command('sqlsequencereset', 'finances', 'users', stdout=sql_output)
            sql_commands = sql_output.getvalue()

            if sql_commands.strip():
                # Execute the SQL
                with connection.cursor() as cursor:
                    cursor.execute(sql_commands)
                logger.info(f"[DB_MIGRATION] Sequences reset successfully")
            else:
                logger.info(f"[DB_MIGRATION] No sequences to reset")

        except Exception as e:
            logger.warning(f"[DB_MIGRATION] Could not reset sequences: {e}")
            # Not fatal, continue

        # STEP 8: Verify migration
        logger.info(f"[DB_MIGRATION] Verifying migration")
        from django.contrib.auth import get_user_model
        UserModel = get_user_model()
        user_count = UserModel.objects.count()

        if user_count == 0:
            raise Exception("Migration completed but no users found in PostgreSQL")

        logger.info(f"[DB_MIGRATION] Verification successful: {user_count} users found")

        # STEP 9: Create backup of SQLite before removing it
        backup_path = sqlite_path.parent / 'backups'
        backup_path.mkdir(parents=True, exist_ok=True)

        from datetime import datetime
        backup_filename = f"sqlite_backup_before_migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sqlite3"
        final_backup = backup_path / backup_filename

        logger.info(f"[DB_MIGRATION] Creating final backup of SQLite: {backup_filename}")

        try:
            # Create backup copy
            import shutil
            shutil.copy2(str(sqlite_path), str(final_backup))
            logger.info(f"[DB_MIGRATION] Backup created successfully: {final_backup}")

            # Also delete related SQLite files (WAL, SHM)
            related_files = [
                sqlite_path.parent / f"{sqlite_path.name}-wal",
                sqlite_path.parent / f"{sqlite_path.name}-shm",
                sqlite_path.parent / f"{sqlite_path.stem}.sqlite3-wal",
                sqlite_path.parent / f"{sqlite_path.stem}.sqlite3-shm",
            ]

            # STEP 10: Remove SQLite database file
            logger.info(f"[DB_MIGRATION] Removing SQLite database file: {sqlite_path.name}")
            sqlite_path.unlink()
            logger.info(f"[DB_MIGRATION] ✅ SQLite database removed successfully")

            # Remove related files if they exist
            for related_file in related_files:
                if related_file.exists():
                    try:
                        related_file.unlink()
                        logger.info(f"[DB_MIGRATION] Removed related file: {related_file.name}")
                    except Exception as e:
                        logger.debug(f"[DB_MIGRATION] Could not remove {related_file.name}: {e}")

        except Exception as e:
            logger.warning(f"[DB_MIGRATION] Could not remove SQLite file: {e}")
            # Not fatal - migration was successful

        # STEP 11: Create migration marker file
        logger.info(f"[DB_MIGRATION] Creating migration marker file")
        migration_marker = sqlite_path.parent / '.migrated_to_postgresql'

        try:
            with open(migration_marker, 'w', encoding='utf-8') as f:
                f.write(f"""# Database Migration Record
# ====================================================
# This file indicates that this SweetMoney installation
# has been migrated from SQLite to PostgreSQL.
#
# Migration Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# Users Migrated: {user_count}
# SQLite Backup: {backup_filename}
#
# The SQLite database has been removed and a backup
# has been saved in the db/backups/ directory.
#
# ⚠️  DO NOT DELETE THIS FILE
# If you need to revert to SQLite, you must manually
# configure local_settings.py and restore from backup.
# ====================================================
""")
            logger.info(f"[DB_MIGRATION] Migration marker created: {migration_marker.name}")
        except Exception as e:
            logger.warning(f"[DB_MIGRATION] Could not create migration marker: {e}")

        logger.info(f"[DB_MIGRATION] ========== MIGRATION COMPLETED SUCCESSFULLY ==========")
        logger.info(f"[DB_MIGRATION] Migrated {user_count} users from SQLite to PostgreSQL")
        logger.info(f"[DB_MIGRATION] SQLite database removed, backup saved at: {final_backup}")

        return {
            'success': True,
            'message': f'Successfully migrated {user_count} users from SQLite to PostgreSQL',
            'details': f'SQLite removed, backup saved at: {backup_filename}'
        }

    except Exception as e:
        logger.error(f"[DB_MIGRATION] Migration failed: {e}", exc_info=True)

        # Try to restore PostgreSQL config
        if original_db_config:
            settings.DATABASES['default'] = original_db_config
            connections.close_all()

        return {
            'success': False,
            'message': f'Migration failed: {str(e)}',
            'details': str(e)
        }

    finally:
        # Clean up temp file
        if temp_dump_file and temp_dump_file.exists():
            try:
                temp_dump_file.unlink()
                logger.info(f"[DB_MIGRATION] Temp dump file cleaned up")
            except Exception as e:
                logger.warning(f"[DB_MIGRATION] Could not delete temp file: {e}")


def check_and_migrate():
    """
    Check if migration is needed and perform it automatically.

    This function should be called during application startup.

    Returns:
        dict: {'migrated': bool, 'message': str}
    """
    try:
        # Check if migration should occur
        should_migrate_flag, sqlite_path, reason = should_migrate()

        logger.info(f"[DB_MIGRATION] Migration check: {reason}")

        if not should_migrate_flag:
            return {
                'migrated': False,
                'message': reason
            }

        # Perform migration
        logger.info(f"[DB_MIGRATION] Starting automatic migration from SQLite to PostgreSQL")
        result = migrate_sqlite_to_postgres(sqlite_path)

        if result['success']:
            return {
                'migrated': True,
                'message': result['message'],
                'details': result.get('details', '')
            }
        else:
            return {
                'migrated': False,
                'message': f"Migration failed: {result['message']}",
                'error': result.get('details', '')
            }

    except Exception as e:
        logger.error(f"[DB_MIGRATION] Unexpected error during migration check: {e}", exc_info=True)
        return {
            'migrated': False,
            'message': f'Migration check failed: {str(e)}',
            'error': str(e)
        }
