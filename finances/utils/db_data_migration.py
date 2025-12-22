"""
Automatic database migration from SQLite to PostgreSQL.

This module detects if:
1. A SQLite database exists with data (users)
2. PostgreSQL is configured as the primary database
3. PostgreSQL database is empty or doesn't have the data yet

If all conditions are met, it automatically migrates data from SQLite to PostgreSQL.
"""

import logging
import tempfile
from pathlib import Path
from django.conf import settings
from django.core.management import call_command
from django.db import connection, connections
from io import StringIO

# Import from new organized modules
from finances.utils.db_utils_sqlite import get_sqlite_path, sqlite_has_data
from finances.utils.db_utils_pgsql import postgres_is_configured, postgres_has_data

logger = logging.getLogger(__name__)


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
    1. Add a temporary, named database connection for SQLite.
    2. Export data using dumpdata from the named SQLite connection.
    3. Load data into the default PostgreSQL connection.
    4. Reset sequences on PostgreSQL.
    5. Clean up and rename the SQLite file.
    """
    logger.info(f"[DATA_MIGRATION] ========== STARTING AUTOMATIC MIGRATION ==========")
    logger.info(f"[DATA_MIGRATION] SQLite: {sqlite_path}")
    logger.info(f"[DATA_MIGRATION] Target: PostgreSQL")

    temp_dump_file = None
    sqlite_db_alias = 'sqlite_migration'

    try:
        # STEP 1: Add a temporary database alias for SQLite by copying the default
        # and overriding the engine and name.
        logger.info(f"[DATA_MIGRATION] Adding temporary SQLite DB connection: '{sqlite_db_alias}'")
        settings.DATABASES[sqlite_db_alias] = settings.DATABASES['default'].copy()
        settings.DATABASES[sqlite_db_alias]['ENGINE'] = 'django.db.backends.sqlite3'
        settings.DATABASES[sqlite_db_alias]['NAME'] = str(sqlite_path)

        # STEP 2: Export data from SQLite using the new alias
        logger.info(f"[DATA_MIGRATION] Exporting data from SQLite using dumpdata")
        temp_dump_file = Path(tempfile.gettempdir()) / 'sqlite_migration_dump.json'

        with open(temp_dump_file, 'w', encoding='utf-8') as f:
            try:
                call_command(
                    'dumpdata',
                    natural_foreign=True,
                    natural_primary=True,
                    exclude=['contenttypes', 'auth.permission'],
                    database=sqlite_db_alias,  # Use the named SQLite connection
                    stdout=f,
                    verbosity=2
                )
            except Exception as e:
                logger.error(f"[DATA_MIGRATION] Dumpdata failed: {e}")
                raise

        logger.info(f"[DATA_MIGRATION] Data exported successfully ({temp_dump_file.stat().st_size} bytes)")

        # STEP 3: Remove the temporary SQLite connection
        del settings.DATABASES[sqlite_db_alias]
        connections.close_all() # Important to close connections after settings change

        # STEP 4: Load data into PostgreSQL (the default connection)
        logger.info(f"[DATA_MIGRATION] Loading data into PostgreSQL")
        try:
            # Verify the dump file is not empty before loading
            if temp_dump_file.stat().st_size == 0:
                raise Exception("Dump file is empty. Cannot load data.")
                
            call_command('loaddata', str(temp_dump_file), verbosity=2)
        except Exception as e:
            logger.error(f"[DATA_MIGRATION] Loaddata failed: {e}")
            raise

        logger.info(f"[DATA_MIGRATION] Data loaded successfully")

        # STEP 5: Reset PostgreSQL sequences
        logger.info(f"[DATA_MIGRATION] Resetting PostgreSQL sequences")
        try:
            sql_output = StringIO()
            call_command('sqlsequencereset', 'finances', stdout=sql_output)
            sql_commands = sql_output.getvalue()

            if sql_commands.strip():
                with connection.cursor() as cursor:
                    cursor.execute(sql_commands)
                logger.info(f"[DATA_MIGRATION] Sequences reset successfully")
            else:
                logger.info(f"[DATA_MIGRATION] No sequences to reset")
        except Exception as e:
            logger.warning(f"[DATA_MIGRATION] Could not reset sequences: {e}")

        # STEP 6: Verify migration
        logger.info(f"[DATA_MIGRATION] Verifying migration")
        from django.contrib.auth import get_user_model
        UserModel = get_user_model()
        user_count = UserModel.objects.count()

        if user_count == 0:
            raise Exception("Migration completed but no users found in PostgreSQL")

        logger.info(f"[DATA_MIGRATION] Verification successful: {user_count} users found")

        # STEP 7: Backup and remove SQLite database
        backup_path = sqlite_path.parent / 'backups'
        backup_path.mkdir(parents=True, exist_ok=True)
        from datetime import datetime
        backup_filename = f"sqlite_backup_before_migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sqlite3"
        final_backup = backup_path / backup_filename

        logger.info(f"[DATA_MIGRATION] Creating final backup of SQLite: {backup_filename}")
        try:
            import shutil
            shutil.copy2(str(sqlite_path), str(final_backup))
            
            # Remove original and related files
            for file_path in [sqlite_path, sqlite_path.with_suffix('.sqlite3-wal'), sqlite_path.with_suffix('.sqlite3-shm')]:
                if file_path.exists():
                    try:
                        file_path.unlink()
                        logger.info(f"[DATA_MIGRATION] Removed file: {file_path.name}")
                    except Exception as e:
                        logger.warning(f"[DATA_MIGRATION] Could not remove {file_path.name}: {e}")

        except Exception as e:
            logger.warning(f"[DATA_MIGRATION] Could not back up or remove SQLite file: {e}")

        logger.info(f"[DATA_MIGRATION] ========== MIGRATION COMPLETED SUCCESSFULLY ==========")
        return {
            'success': True,
            'message': f'Successfully migrated {user_count} users from SQLite to PostgreSQL',
            'details': f'SQLite removed, backup saved at: {backup_filename}'
        }

    except Exception as e:
        logger.error(f"[DATA_MIGRATION] Migration failed: {e}", exc_info=True)
        return {
            'success': False,
            'message': f'Migration failed: {str(e)}',
            'details': str(e)
        }

    finally:
        # Clean up alias and temp file
        if sqlite_db_alias in settings.DATABASES:
            del settings.DATABASES[sqlite_db_alias]
            connections.close_all()
        if temp_dump_file and temp_dump_file.exists():
            try:
                temp_dump_file.unlink()
                logger.info(f"[DATA_MIGRATION] Temp dump file cleaned up")
            except Exception as e:
                logger.warning(f"[DATA_MIGRATION] Could not delete temp file: {e}")


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

        logger.info(f"[DATA_MIGRATION] Migration check: {reason}")

        if not should_migrate_flag:
            return {
                'migrated': False,
                'message': reason
            }

        # Perform migration
        logger.info(f"[DATA_MIGRATION] Starting automatic migration from SQLite to PostgreSQL")
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
        logger.error(f"[DATA_MIGRATION] Unexpected error during migration check: {e}", exc_info=True)
        return {
            'migrated': False,
            'message': f'Migration check failed: {str(e)}',
            'error': str(e)
        }
