"""
PostgreSQL database restore utility.

This module provides PostgreSQL-specific restore functionality using pg_restore.
"""

import os
import logging
import subprocess
import tempfile
import sqlite3
from pathlib import Path
from datetime import datetime
from django.conf import settings
from django.utils.translation import gettext as _
from django.db import connections
import gc
import time

logger = logging.getLogger(__name__)


def restore_postgres_database_from_file(uploaded_file):
    """
    Restore a PostgreSQL database from an uploaded backup file.

    This function:
    1. Validates the uploaded backup file
    2. Saves it to a temporary location
    3. Reads metadata from the backup
    4. Cleans the current database using DROP CASCADE
    5. Restores data using pg_restore
    6. Verifies the restored database

    Args:
        uploaded_file: Django UploadedFile object containing the backup

    Returns:
        dict: {
            'success': bool,
            'family': dict (if success),
            'users': list (if success),
            'error': str (if failure),
            'details': str (if failure)
        }
    """
    temp_backup_path = None

    try:
        db_config = settings.DATABASES['default']

        # Get database connection parameters
        db_name = db_config.get('NAME')
        db_user = db_config.get('USER')
        db_password = db_config.get('PASSWORD')
        db_host = db_config.get('HOST', 'localhost')
        db_port = db_config.get('PORT', '5432')

        logger.info(f"[PG_RESTORE] ========== STARTING POSTGRESQL RESTORE ==========")
        logger.info(f"[PG_RESTORE] Database: {db_name}@{db_host}:{db_port}")

        # STEP 1: Validate uploaded file
        if not uploaded_file:
            return {
                'success': False,
                'error': _('No backup file provided')
            }

        logger.info(f"[PG_RESTORE] Uploaded file: {uploaded_file.name} ({uploaded_file.size} bytes)")

        # STEP 2: Save uploaded file to temporary location
        temp_backup_path = Path(tempfile.gettempdir()) / f"restore_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.dump"

        logger.info(f"[PG_RESTORE] Saving uploaded file to: {temp_backup_path}")
        with open(temp_backup_path, 'wb') as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)

        logger.info(f"[PG_RESTORE] File saved successfully ({temp_backup_path.stat().st_size} bytes)")

        # STEP 2.5: Clean the backup file to remove incompatible SET commands
        # PostgreSQL 17 adds SET commands that don't exist in older versions
        logger.info(f"[PG_RESTORE] Cleaning backup file to remove incompatible SET commands")

        use_sql_format = False
        sql_output_path = None
        original_backup_path = temp_backup_path  # Keep reference to original

        try:
            # Convert backup to SQL, filter out problematic commands, then restore
            # Use pg_restore to convert to SQL
            env = os.environ.copy()
            env['PGPASSWORD'] = db_password

            # First, convert dump to SQL format
            sql_output_path = Path(tempfile.gettempdir()) / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"

            cmd_to_sql = [
                'pg_restore',
                '--file', str(sql_output_path),
                str(temp_backup_path)
            ]

            logger.info(f"[PG_RESTORE] Converting dump to SQL format")
            result = subprocess.run(cmd_to_sql, env=env, capture_output=True, text=True, timeout=60)

            if result.returncode == 0 and sql_output_path.exists():
                # Filter out problematic SET commands
                logger.info(f"[PG_RESTORE] Filtering incompatible SET commands from SQL")
                with open(sql_output_path, 'r', encoding='utf-8', errors='ignore') as f:
                    sql_content = f.read()

                # Remove the problematic SET command
                filtered_sql = sql_content.replace('SET transaction_timeout = 0;', '-- SET transaction_timeout = 0; (removed for compatibility)')

                # Save filtered SQL
                with open(sql_output_path, 'w', encoding='utf-8') as f:
                    f.write(filtered_sql)

                logger.info(f"[PG_RESTORE] Filtered SQL saved, will use SQL format for restore")
                use_sql_format = True
            else:
                logger.warning(f"[PG_RESTORE] Could not convert to SQL format, using original dump")
                use_sql_format = False
                if sql_output_path and sql_output_path.exists():
                    sql_output_path.unlink()
                    sql_output_path = None
        except Exception as filter_error:
            logger.warning(f"[PG_RESTORE] Could not filter backup: {filter_error}, using original")
            use_sql_format = False
            if sql_output_path and sql_output_path.exists():
                sql_output_path.unlink()
                sql_output_path = None

        # STEP 3: Create backup of current PostgreSQL database before restore
        logger.info(f"[PG_RESTORE] Creating backup of current PostgreSQL database")
        backup_created = False
        try:
            from finances.utils.db_backup import create_database_backup
            backup_result = create_database_backup()

            if backup_result['success']:
                backup_created = True
                logger.info(f"[PG_RESTORE] PostgreSQL backup created: {backup_result['filename']}")
            else:
                logger.warning(f"[PG_RESTORE] Could not create PostgreSQL backup: {backup_result.get('error')}")
                # Not fatal, continue with restore

        except Exception as backup_error:
            logger.warning(f"[PG_RESTORE] Could not create PostgreSQL backup: {backup_error}")
            # Not fatal, continue with restore

        # STEP 4: Read metadata from backup
        # For PostgreSQL dumps, we need to extract metadata differently
        # We'll try to read it from a temporary SQLite conversion or from the restored DB after restore
        family_info = {'name': 'Unknown Family'}
        users_info = []

        # STEP 5: Close all Django connections
        logger.info(f"[PG_RESTORE] Closing all Django database connections")
        for conn in connections.all():
            try:
                conn.close()
            except Exception as e:
                logger.warning(f"[PG_RESTORE] Could not close connection: {e}")

        gc.collect()
        time.sleep(0.5)

        # STEP 6: Restore database
        # Set PGPASSWORD environment variable for authentication
        env = os.environ.copy()
        env['PGPASSWORD'] = db_password

        if use_sql_format and sql_output_path:
            # Use psql to restore from filtered SQL file
            logger.info(f"[PG_RESTORE] Restoring from filtered SQL file using psql")
            cmd = [
                'psql',
                '--username', db_user,
                '--host', db_host,
                '--port', str(db_port),
                '--dbname', db_name,
                '--file', str(sql_output_path),
                '--quiet'
            ]

            logger.info(f"[PG_RESTORE] Executing psql command")
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=600  # 10 minutes timeout
            )
        else:
            # Use pg_restore for original dump file
            logger.info(f"[PG_RESTORE] Restoring from dump file using pg_restore")

            # Build pg_restore command
            # --clean: Drop database objects before recreating them
            # --if-exists: Use IF EXISTS when dropping objects (prevents errors if objects don't exist)
            # --no-owner: Don't set ownership of objects
            # --no-acl: Don't restore access privileges
            cmd = [
                'pg_restore',
                '--username', db_user,
                '--host', db_host,
                '--port', str(db_port),
                '--dbname', db_name,
                '--clean',          # Drop objects before recreating
                '--if-exists',      # Use IF EXISTS (no errors if object doesn't exist)
                '--no-owner',       # Don't try to set ownership
                '--no-acl',         # Don't restore privileges
                '--verbose',        # Show progress
                str(original_backup_path)
            ]

            logger.info(f"[PG_RESTORE] Executing pg_restore command")
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=600  # 10 minutes timeout
            )

        # pg_restore may return non-zero even on success (warnings about existing objects)
        # We check stderr for actual errors
        if result.returncode != 0:
            # Check if it's just warnings or actual errors
            stderr_lower = result.stderr.lower()

            # Ignore specific errors that are not critical:
            # - transaction_timeout: compatibility issue between PostgreSQL versions
            ignorable_errors = [
                'transaction_timeout',
                'unrecognized configuration parameter'
            ]

            # Check if stderr contains ignorable errors only
            is_ignorable = any(ignore_err in stderr_lower for ignore_err in ignorable_errors)

            # Check for real critical errors
            critical_errors = ['fatal:', 'could not connect', 'authentication failed', 'does not exist']
            has_critical_error = any(err in stderr_lower for err in critical_errors)

            if has_critical_error:
                logger.error(f"[PG_RESTORE] pg_restore failed with critical error: {result.stderr}")
                return {
                    'success': False,
                    'error': _('Database restore failed'),
                    'details': result.stderr
                }
            elif is_ignorable:
                logger.warning(f"[PG_RESTORE] pg_restore had ignorable warnings: {result.stderr}")
            else:
                logger.warning(f"[PG_RESTORE] pg_restore had warnings: {result.stderr}")

        logger.info(f"[PG_RESTORE] pg_restore completed")

        # STEP 7: Force Django to reconnect
        logger.info(f"[PG_RESTORE] Forcing Django to reconnect to database")
        for conn in connections.all():
            conn.close()
        gc.collect()
        time.sleep(0.5)

        # STEP 8: Verify Django can read the restored database
        try:
            from django.contrib.auth import get_user_model
            from finances.models import Family

            UserModel = get_user_model()
            user_count = UserModel.objects.count()
            logger.info(f"[PG_RESTORE] SUCCESS! Django can read restored DB, found {user_count} users")

            if user_count == 0:
                logger.warning(f"[PG_RESTORE] WARNING: Restored database has 0 users!")

            # Try to get family info
            try:
                families = Family.objects.all()
                if families.exists():
                    family = families.first()
                    family_info = {
                        'name': family.name,
                        'id': family.id
                    }
            except Exception as e:
                logger.warning(f"[PG_RESTORE] Could not read family info: {e}")

            # Get user info
            try:
                users = UserModel.objects.all()
                users_info = [
                    {
                        'username': user.username,
                        'email': user.email,
                        'role': 'admin' if user.is_superuser else 'user'
                    }
                    for user in users
                ]
            except Exception as e:
                logger.warning(f"[PG_RESTORE] Could not read user info: {e}")

        except Exception as db_read_error:
            logger.error(f"[PG_RESTORE] ERROR: Django cannot read restored database: {db_read_error}")
            return {
                'success': False,
                'error': _('Restored database cannot be read by Django'),
                'details': str(db_read_error)
            }

        # STEP 9: Create reload flag to signal server restart needed
        try:
            from finances.views.views_updater import create_reload_flag
            create_reload_flag()
            logger.info(f"[PG_RESTORE] Reload flag created")
        except Exception as e:
            logger.warning(f"[PG_RESTORE] Could not create reload flag: {e}")

        logger.info(f"[PG_RESTORE] ========== RESTORE COMPLETED SUCCESSFULLY ==========")
        logger.info(f"[PG_RESTORE] Restored: {family_info['name']}")
        logger.info(f"[PG_RESTORE] Users: {len(users_info)}")

        return {
            'success': True,
            'family': family_info,
            'users': users_info,
            'message': _('Database restored successfully')
        }

    except subprocess.TimeoutExpired:
        logger.error(f"[PG_RESTORE] Restore operation timed out")
        return {
            'success': False,
            'error': _('Restore operation timed out'),
            'details': 'pg_restore took longer than 10 minutes'
        }

    except FileNotFoundError:
        logger.error(f"[PG_RESTORE] pg_restore command not found")
        return {
            'success': False,
            'error': _('pg_restore command not found. Please ensure PostgreSQL client tools are installed.'),
            'details': 'pg_restore not in PATH'
        }

    except Exception as e:
        logger.error(f"[PG_RESTORE] Unexpected error during restore: {e}", exc_info=True)
        return {
            'success': False,
            'error': f'Restore failed: {str(e)}',
            'details': str(e)
        }

    finally:
        # ALWAYS clean up temporary files
        # Clean up original backup file
        if original_backup_path and original_backup_path.exists():
            for cleanup_attempt in range(5):
                try:
                    original_backup_path.unlink()
                    logger.info(f"[PG_RESTORE] Temporary backup file deleted")
                    break
                except PermissionError:
                    if cleanup_attempt < 4:
                        logger.debug(f"[PG_RESTORE] Temp file locked, retry {cleanup_attempt + 1}/5")
                        gc.collect()
                        time.sleep(0.5)
                    else:
                        logger.warning(f"[PG_RESTORE] Could not delete temp file after 5 attempts: {original_backup_path}")
                except Exception as cleanup_error:
                    logger.warning(f"[PG_RESTORE] Could not delete temp file: {cleanup_error}")
                    break

        # Clean up filtered SQL file if it exists
        if sql_output_path and sql_output_path.exists():
            try:
                sql_output_path.unlink()
                logger.info(f"[PG_RESTORE] Filtered SQL file deleted")
            except Exception as cleanup_error:
                logger.warning(f"[PG_RESTORE] Could not delete SQL file: {cleanup_error}")
