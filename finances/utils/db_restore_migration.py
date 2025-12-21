"""
Database Restore with Migration Support

This module handles restoring SQLite backups into PostgreSQL database.
It reuses the migration logic from db_migration.py but works with uploaded files.
"""

import io
import logging
import tempfile
import sqlite3
from pathlib import Path
from django.conf import settings
from django.core.management import call_command
from django.db import connections
from django.utils.translation import gettext as _
import gc
import time

logger = logging.getLogger(__name__)


def restore_sqlite_to_postgres(uploaded_file):
    """
    Restore a SQLite backup file into PostgreSQL database.

    This function:
    1. Saves uploaded SQLite file to temporary location
    2. Validates SQLite file integrity
    3. Creates backup of current PostgreSQL database
    4. Drops all data from PostgreSQL (transactional)
    5. Exports data from SQLite using dumpdata
    6. Imports data into PostgreSQL using loaddata
    7. Resets PostgreSQL sequences
    8. Verifies migration

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
    temp_dump_path = None
    backup_created = False

    try:
        logger.info(f"[SQLITE_TO_PG] ========== STARTING SQLITE TO POSTGRESQL MIGRATION ==========")

        db_config = settings.DATABASES['default']
        db_name = db_config.get('NAME')
        db_user = db_config.get('USER')
        db_password = db_config.get('PASSWORD')
        db_host = db_config.get('HOST', 'localhost')
        db_port = db_config.get('PORT', '5432')

        logger.info(f"[SQLITE_TO_PG] Target PostgreSQL: {db_name}@{db_host}:{db_port}")

        # STEP 1: Save uploaded SQLite file to temporary location
        temp_sqlite_path = Path(tempfile.gettempdir()) / f"migrate_sqlite_{int(time.time())}.sqlite3"

        logger.info(f"[SQLITE_TO_PG] Saving uploaded SQLite file to: {temp_sqlite_path}")
        with open(temp_sqlite_path, 'wb') as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)

        logger.info(f"[SQLITE_TO_PG] SQLite file saved ({temp_sqlite_path.stat().st_size} bytes)")

        # STEP 2: Validate SQLite file integrity
        logger.info(f"[SQLITE_TO_PG] Validating SQLite database integrity")
        try:
            conn = sqlite3.connect(str(temp_sqlite_path))
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()

            if integrity_result[0] != 'ok':
                cursor.close()
                conn.close()
                logger.error(f"[SQLITE_TO_PG] Integrity check failed: {integrity_result[0]}")
                return {
                    'success': False,
                    'error': _('SQLite backup file is corrupted and cannot be restored.'),
                    'details': f'Integrity check failed: {integrity_result[0]}'
                }

            logger.info(f"[SQLITE_TO_PG] Integrity check PASSED")

            # Read metadata from SQLite backup
            cursor.execute("SELECT id, name FROM finances_family LIMIT 1")
            family_row = cursor.fetchone()

            family_info = None
            users_info = []

            if family_row:
                family_id, family_name = family_row
                family_info = {'id': family_id, 'name': family_name}
                logger.info(f"[SQLITE_TO_PG] Found family: '{family_name}' (ID: {family_id})")

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
                logger.info(f"[SQLITE_TO_PG] Found {len(users_info)} users: {[u['username'] for u in users_info]}")
            else:
                logger.warning(f"[SQLITE_TO_PG] No family found in SQLite backup!")

            cursor.close()
            conn.close()

        except sqlite3.DatabaseError as db_error:
            logger.error(f"[SQLITE_TO_PG] SQLite error: {db_error}")
            return {
                'success': False,
                'error': _('SQLite backup file is corrupted: %(error)s') % {'error': str(db_error)},
                'details': str(db_error)
            }

        # STEP 3: Create backup of current PostgreSQL database
        logger.info(f"[SQLITE_TO_PG] Creating backup of current PostgreSQL database")
        try:
            from finances.utils.db_backup import create_database_backup
            backup_result = create_database_backup()

            if backup_result['success']:
                backup_created = True
                logger.info(f"[SQLITE_TO_PG] PostgreSQL backup created: {backup_result['filename']}")
            else:
                logger.warning(f"[SQLITE_TO_PG] Could not create PostgreSQL backup: {backup_result.get('error')}")
                # Not fatal, continue with migration

        except Exception as backup_error:
            logger.warning(f"[SQLITE_TO_PG] Could not create PostgreSQL backup: {backup_error}")
            # Not fatal, continue with migration

        # STEP 4: Close all Django connections
        logger.info(f"[SQLITE_TO_PG] Closing all Django database connections")
        for conn in connections.all():
            try:
                conn.close()
            except Exception as e:
                logger.warning(f"[SQLITE_TO_PG] Could not close connection: {e}")

        gc.collect()
        time.sleep(0.5)

        # STEP 5: Add temporary SQLite connection to settings
        logger.info(f"[SQLITE_TO_PG] Adding temporary SQLite connection")
        settings.DATABASES['sqlite_migration'] = {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': str(temp_sqlite_path)
        }

        # STEP 6: Export data from SQLite using dumpdata
        logger.info(f"[SQLITE_TO_PG] Exporting data from SQLite using dumpdata")

        temp_dump_path = Path(tempfile.gettempdir()) / f"sqlite_migration_dump_{int(time.time())}.json"

        try:
            # Use the same approach as db_migration.py (which works!)
            # Capture both stdout and stderr to diagnose issues
            stderr_buffer = io.StringIO()

            with open(temp_dump_path, 'w', encoding='utf-8') as f:
                try:
                    call_command(
                        'dumpdata',
                        natural_foreign=True,
                        natural_primary=True,
                        exclude=['contenttypes', 'auth.permission'],
                        database='sqlite_migration',
                        stdout=f,
                        stderr=stderr_buffer,
                        verbosity=2
                    )
                except Exception as cmd_error:
                    stderr_output = stderr_buffer.getvalue()
                    logger.error(f"[SQLITE_TO_PG] call_command raised exception: {cmd_error}")
                    logger.error(f"[SQLITE_TO_PG] stderr output: {stderr_output}")
                    raise Exception(f"dumpdata command failed: {cmd_error}. stderr: {stderr_output}")

            stderr_output = stderr_buffer.getvalue()
            if stderr_output:
                logger.warning(f"[SQLITE_TO_PG] dumpdata stderr output: {stderr_output}")

            logger.info(f"[SQLITE_TO_PG] dumpdata completed successfully")

            # Check if file exists and has content
            if not temp_dump_path.exists():
                raise Exception("Dump file was not created")

            file_size = temp_dump_path.stat().st_size
            logger.info(f"[SQLITE_TO_PG] Dump file size: {file_size} bytes")

            # Verify dump file is not empty
            if file_size == 0:
                raise Exception("Dump file is empty. Cannot load data.")

        except Exception as dump_error:
            logger.error(f"[SQLITE_TO_PG] dumpdata failed: {dump_error}", exc_info=True)
            return {
                'success': False,
                'error': _('Failed to export data from SQLite backup'),
                'details': str(dump_error)
            }

        finally:
            # Remove temporary SQLite connection
            if 'sqlite_migration' in settings.DATABASES:
                del settings.DATABASES['sqlite_migration']

            # Close all connections again
            for conn in connections.all():
                try:
                    conn.close()
                except Exception:
                    pass

            gc.collect()
            time.sleep(0.3)

        # STEP 7: Drop all data from PostgreSQL
        logger.info(f"[SQLITE_TO_PG] Dropping all data from PostgreSQL database")

        try:
            from django.db import connection
            with connection.cursor() as cursor:
                # Get all table names
                cursor.execute("""
                    SELECT tablename FROM pg_tables
                    WHERE schemaname = 'public'
                """)
                tables = [row[0] for row in cursor.fetchall()]

                logger.info(f"[SQLITE_TO_PG] Found {len(tables)} tables to drop")

                # Drop all tables with CASCADE
                for table in tables:
                    try:
                        cursor.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
                        logger.debug(f"[SQLITE_TO_PG] Dropped table: {table}")
                    except Exception as drop_error:
                        logger.warning(f"[SQLITE_TO_PG] Could not drop table {table}: {drop_error}")

            logger.info(f"[SQLITE_TO_PG] All tables dropped successfully")

            # Close connection to force reconnect
            connection.close()
            gc.collect()
            time.sleep(0.3)

        except Exception as drop_error:
            logger.error(f"[SQLITE_TO_PG] Error dropping PostgreSQL tables: {drop_error}")
            return {
                'success': False,
                'error': _('Failed to clean PostgreSQL database'),
                'details': str(drop_error)
            }

        # STEP 8: Run migrations to recreate schema
        logger.info(f"[SQLITE_TO_PG] Running migrations to recreate PostgreSQL schema")

        try:
            output = io.StringIO()
            call_command('migrate', stdout=output, stderr=output, interactive=False)
            logger.info(f"[SQLITE_TO_PG] Migrations completed: {output.getvalue()}")

        except Exception as migrate_error:
            logger.error(f"[SQLITE_TO_PG] Migrations failed: {migrate_error}")
            return {
                'success': False,
                'error': _('Failed to recreate PostgreSQL schema'),
                'details': str(migrate_error)
            }

        # STEP 9: Import data into PostgreSQL using loaddata
        logger.info(f"[SQLITE_TO_PG] Importing data into PostgreSQL using loaddata")

        try:
            output = io.StringIO()
            call_command('loaddata', str(temp_dump_path), stdout=output, stderr=output)
            logger.info(f"[SQLITE_TO_PG] loaddata completed: {output.getvalue()}")

        except Exception as load_error:
            logger.error(f"[SQLITE_TO_PG] loaddata failed: {load_error}")
            return {
                'success': False,
                'error': _('Failed to import data into PostgreSQL'),
                'details': str(load_error)
            }

        # STEP 10: Reset PostgreSQL sequences
        logger.info(f"[SQLITE_TO_PG] Resetting PostgreSQL sequences")

        try:
            from django.db import connection
            with connection.cursor() as cursor:
                # Get SQL to reset sequences
                output = io.StringIO()
                call_command('sqlsequencereset', 'finances', stdout=output)
                reset_sql = output.getvalue()

                if reset_sql.strip():
                    logger.info(f"[SQLITE_TO_PG] Executing sequence reset SQL")
                    cursor.execute(reset_sql)
                    logger.info(f"[SQLITE_TO_PG] Sequences reset successfully")
                else:
                    logger.warning(f"[SQLITE_TO_PG] No sequence reset SQL generated")

        except Exception as seq_error:
            logger.warning(f"[SQLITE_TO_PG] Error resetting sequences: {seq_error}")
            # Not fatal, continue

        # STEP 11: Verify migration
        logger.info(f"[SQLITE_TO_PG] Verifying migration")

        try:
            from django.contrib.auth import get_user_model
            from finances.models import Family

            UserModel = get_user_model()
            user_count = UserModel.objects.count()
            logger.info(f"[SQLITE_TO_PG] Found {user_count} users in PostgreSQL")

            if user_count == 0:
                logger.warning(f"[SQLITE_TO_PG] WARNING: PostgreSQL has 0 users after migration!")

            if user_count != len(users_info):
                logger.warning(f"[SQLITE_TO_PG] User count mismatch! SQLite had {len(users_info)}, PostgreSQL has {user_count}")

            # Verify family
            families = Family.objects.all()
            if families.exists():
                family = families.first()
                logger.info(f"[SQLITE_TO_PG] Found family: {family.name}")
            else:
                logger.warning(f"[SQLITE_TO_PG] No family found in PostgreSQL after migration!")

        except Exception as verify_error:
            logger.error(f"[SQLITE_TO_PG] Error verifying migration: {verify_error}")
            return {
                'success': False,
                'error': _('Migration verification failed'),
                'details': str(verify_error)
            }

        # STEP 12: Create reload flag
        try:
            from finances.views.views_updater import create_reload_flag
            create_reload_flag()
            logger.info(f"[SQLITE_TO_PG] Reload flag created")
        except Exception as e:
            logger.warning(f"[SQLITE_TO_PG] Could not create reload flag: {e}")

        logger.info(f"[SQLITE_TO_PG] ========== MIGRATION COMPLETED SUCCESSFULLY ==========")
        logger.info(f"[SQLITE_TO_PG] Migrated: {family_info['name'] if family_info else 'Unknown'}")
        logger.info(f"[SQLITE_TO_PG] Users: {len(users_info)}")

        return {
            'success': True,
            'family': family_info,
            'users': users_info,
            'message': _('SQLite backup successfully migrated to PostgreSQL')
        }

    except Exception as e:
        logger.error(f"[SQLITE_TO_PG] Unexpected error during migration: {e}", exc_info=True)
        return {
            'success': False,
            'error': f'Migration failed: {str(e)}',
            'details': str(e)
        }

    finally:
        # Clean up temporary files
        if temp_sqlite_path and temp_sqlite_path.exists():
            try:
                temp_sqlite_path.unlink()
                logger.info(f"[SQLITE_TO_PG] Temporary SQLite file deleted")
            except Exception as e:
                logger.warning(f"[SQLITE_TO_PG] Could not delete temp SQLite file: {e}")

        if temp_dump_path and temp_dump_path.exists():
            try:
                temp_dump_path.unlink()
                logger.info(f"[SQLITE_TO_PG] Temporary dump file deleted")
            except Exception as e:
                logger.warning(f"[SQLITE_TO_PG] Could not delete temp dump file: {e}")
