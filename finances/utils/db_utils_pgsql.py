"""
PostgreSQL-specific database utilities.

This module provides all PostgreSQL-specific operations including:
- Backup creation using pg_dump
- Database restore using pg_restore
- PostgreSQL database configuration and verification
"""

import os
import logging
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from django.conf import settings
from django.utils.translation import gettext as _
from django.db import connections
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import gc
import time

logger = logging.getLogger(__name__)


# ============================================================
# PostgreSQL Configuration and Verification Functions
# ============================================================

def postgres_is_configured():
    """
    Check if PostgreSQL is configured as the primary database.

    Returns:
        bool: True if PostgreSQL is configured with all required credentials, False otherwise
    """
    db_engine = settings.DATABASES['default']['ENGINE']
    if 'postgresql' not in db_engine:
        return False

    # Check if all required PostgreSQL credentials are present
    db_config = settings.DATABASES['default']
    required_fields = ['NAME', 'USER', 'PASSWORD', 'HOST']

    for field in required_fields:
        value = db_config.get(field)
        if not value or value == 'unknown':
            logger.warning(f"[PGSQL_UTILS] PostgreSQL configured but {field} is missing or invalid")
            return False

    return True


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
        logger.debug(f"[PGSQL_UTILS] Could not check PostgreSQL data: {e}")
        return False


def check_postgres_database_exists():
    """
    Check if the PostgreSQL database exists.
    If not, create it.

    Returns:
        dict: {'exists': bool, 'created': bool, 'message': str}
    """
    db_config = settings.DATABASES['default']
    db_name = db_config['NAME']
    db_user = db_config['USER']
    db_password = db_config['PASSWORD']
    db_host = db_config['HOST']
    db_port = db_config.get('PORT', '5432')

    try:
        # Connect to 'postgres' database to check if target database exists
        logger.info(f"[PGSQL_UTILS] Checking if database '{db_name}' exists...")

        conn = psycopg2.connect(
            dbname='postgres',
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # Check if database exists
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (db_name,)
        )
        exists = cursor.fetchone() is not None

        if exists:
            logger.info(f"[PGSQL_UTILS] [OK] Database '{db_name}' exists")
            cursor.close()
            conn.close()
            return {
                'exists': True,
                'created': False,
                'message': f"Database '{db_name}' already exists"
            }

        # Database doesn't exist - create it
        logger.info(f"[PGSQL_UTILS] [WARN] Database '{db_name}' does not exist - creating...")

        cursor.execute(sql.SQL("CREATE DATABASE {}").format(
            sql.Identifier(db_name)
        ))

        logger.info(f"[PGSQL_UTILS] [OK] Database '{db_name}' created successfully")

        cursor.close()
        conn.close()

        return {
            'exists': True,
            'created': True,
            'message': f"Database '{db_name}' created successfully"
        }

    except psycopg2.OperationalError as e:
        logger.error(f"[PGSQL_UTILS] [ERROR] Cannot connect to PostgreSQL server: {e}")
        return {
            'exists': False,
            'created': False,
            'message': f"Cannot connect to PostgreSQL: {e}"
        }
    except Exception as e:
        logger.error(f"[PGSQL_UTILS] [ERROR] Error checking/creating database: {e}")
        return {
            'exists': False,
            'created': False,
            'message': f"Error: {e}"
        }


# ============================================================
# PostgreSQL Backup Functions
# ============================================================

def create_postgres_backup():
    """
    Create a backup of PostgreSQL database using pg_dump.

    Returns:
        dict: {'success': bool, 'backup_path': str, 'filename': str, 'error': str}
    """
    try:
        db_config = settings.DATABASES['default']

        # Get database connection parameters
        db_name = db_config.get('NAME')
        db_user = db_config.get('USER')
        db_password = db_config.get('PASSWORD')
        db_host = db_config.get('HOST', 'localhost')
        db_port = db_config.get('PORT', '5432')

        # Create backups directory
        base_dir = Path(settings.BASE_DIR)
        backups_dir = base_dir / 'db' / 'backups'
        backups_dir.mkdir(parents=True, exist_ok=True)

        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'backup_{timestamp}.dump'
        backup_path = backups_dir / backup_filename

        logger.info(f"[PGSQL_BACKUP] Creating PostgreSQL backup: {backup_path}")

        # Build pg_dump command
        # Using custom format (-Fc) which is compressed and suitable for pg_restore
        cmd = [
            'pg_dump',
            '--username', db_user,
            '--host', db_host,
            '--port', str(db_port),
            '--dbname', db_name,
            '--format', 'c',  # Custom format (compressed)
            '--file', str(backup_path)
        ]

        # Set PGPASSWORD environment variable for authentication
        env = os.environ.copy()
        env['PGPASSWORD'] = db_password

        # Execute pg_dump
        logger.info(f"[PGSQL_BACKUP] Executing pg_dump command")
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes timeout
        )

        if result.returncode != 0:
            logger.error(f"[PGSQL_BACKUP] pg_dump failed: {result.stderr}")
            return {
                'success': False,
                'error': _('PostgreSQL backup failed: %(error)s') % {'error': result.stderr}
            }

        # Verify backup file was created
        if not backup_path.exists():
            return {
                'success': False,
                'error': _('Backup file was not created')
            }

        file_size = backup_path.stat().st_size
        logger.info(f"[PGSQL_BACKUP] PostgreSQL backup created successfully ({file_size} bytes)")

        return {
            'success': True,
            'backup_path': str(backup_path),
            'filename': backup_filename,
            'size': file_size
        }

    except subprocess.TimeoutExpired:
        logger.error(f"[PGSQL_BACKUP] PostgreSQL backup timed out")
        return {
            'success': False,
            'error': _('Backup operation timed out')
        }
    except FileNotFoundError:
        logger.error(f"[PGSQL_BACKUP] pg_dump command not found")
        return {
            'success': False,
            'error': _('pg_dump command not found. Please ensure PostgreSQL client tools are installed.')
        }
    except Exception as e:
        logger.error(f"[PGSQL_BACKUP] PostgreSQL backup failed: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }


# ============================================================
# PostgreSQL Restore Functions
# ============================================================

def restore_postgres_from_file(uploaded_file):
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

        logger.info(f"[PGSQL_RESTORE] ========== STARTING POSTGRESQL RESTORE ==========")
        logger.info(f"[PGSQL_RESTORE] Database: {db_name}@{db_host}:{db_port}")

        # STEP 1: Validate uploaded file
        if not uploaded_file:
            return {
                'success': False,
                'error': _('No backup file provided')
            }

        logger.info(f"[PGSQL_RESTORE] Uploaded file: {uploaded_file.name} ({uploaded_file.size} bytes)")

        # STEP 2: Save uploaded file to temporary location
        temp_backup_path = Path(tempfile.gettempdir()) / f"restore_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.dump"

        logger.info(f"[PGSQL_RESTORE] Saving uploaded file to: {temp_backup_path}")
        with open(temp_backup_path, 'wb') as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)

        logger.info(f"[PGSQL_RESTORE] File saved successfully ({temp_backup_path.stat().st_size} bytes)")

        # STEP 3: Create backup of current PostgreSQL database before restore
        logger.info(f"[PGSQL_RESTORE] Creating backup of current PostgreSQL database")
        backup_created = False
        try:
            from finances.utils.db_backup import create_database_backup
            backup_result = create_database_backup()

            if backup_result['success']:
                backup_created = True
                logger.info(f"[PGSQL_RESTORE] PostgreSQL backup created: {backup_result['filename']}")
            else:
                logger.warning(f"[PGSQL_RESTORE] Could not create PostgreSQL backup: {backup_result.get('error')}")
                # Not fatal, continue with restore

        except Exception as backup_error:
            logger.warning(f"[PGSQL_RESTORE] Could not create PostgreSQL backup: {backup_error}")
            # Not fatal, continue with restore

        # STEP 4: Read metadata from backup
        # For PostgreSQL dumps, we'll read it from the restored DB after restore
        family_info = {'name': 'Unknown Family'}
        users_info = []

        # STEP 5: Close all Django connections
        logger.info(f"[PGSQL_RESTORE] Closing all Django database connections")
        for conn in connections.all():
            try:
                conn.close()
            except Exception as e:
                logger.warning(f"[PGSQL_RESTORE] Could not close connection: {e}")

        gc.collect()
        time.sleep(0.5)

        # STEP 6: Restore using pg_restore with --clean
        logger.info(f"[PGSQL_RESTORE] Starting pg_restore with --clean option")

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
            str(temp_backup_path)
        ]

        # Set PGPASSWORD environment variable for authentication
        env = os.environ.copy()
        env['PGPASSWORD'] = db_password

        # Execute pg_restore
        logger.info(f"[PGSQL_RESTORE] Executing pg_restore command")
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
            has_real_error = any(err in stderr_lower for err in ['fatal:', 'could not connect', 'authentication failed'])

            if has_real_error:
                logger.error(f"[PGSQL_RESTORE] pg_restore failed: {result.stderr}")
                return {
                    'success': False,
                    'error': _('Database restore failed'),
                    'details': result.stderr
                }
            else:
                logger.warning(f"[PGSQL_RESTORE] pg_restore had warnings: {result.stderr}")

        logger.info(f"[PGSQL_RESTORE] pg_restore completed")

        # STEP 7: Force Django to reconnect
        logger.info(f"[PGSQL_RESTORE] Forcing Django to reconnect to database")
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
            logger.info(f"[PGSQL_RESTORE] SUCCESS! Django can read restored DB, found {user_count} users")

            if user_count == 0:
                logger.warning(f"[PGSQL_RESTORE] WARNING: Restored database has 0 users!")

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
                logger.warning(f"[PGSQL_RESTORE] Could not read family info: {e}")

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
                logger.warning(f"[PGSQL_RESTORE] Could not read user info: {e}")

        except Exception as db_read_error:
            logger.error(f"[PGSQL_RESTORE] ERROR: Django cannot read restored database: {db_read_error}")
            return {
                'success': False,
                'error': _('Restored database cannot be read by Django'),
                'details': str(db_read_error)
            }

        # STEP 9: Create reload flag to signal server restart needed
        try:
            from finances.views.views_updater import create_reload_flag
            create_reload_flag()
            logger.info(f"[PGSQL_RESTORE] Reload flag created")
        except Exception as e:
            logger.warning(f"[PGSQL_RESTORE] Could not create reload flag: {e}")

        logger.info(f"[PGSQL_RESTORE] ========== RESTORE COMPLETED SUCCESSFULLY ==========")
        logger.info(f"[PGSQL_RESTORE] Restored: {family_info['name']}")
        logger.info(f"[PGSQL_RESTORE] Users: {len(users_info)}")

        return {
            'success': True,
            'family': family_info,
            'users': users_info,
            'message': _('Database restored successfully')
        }

    except subprocess.TimeoutExpired:
        logger.error(f"[PGSQL_RESTORE] Restore operation timed out")
        return {
            'success': False,
            'error': _('Restore operation timed out'),
            'details': 'pg_restore took longer than 10 minutes'
        }

    except FileNotFoundError:
        logger.error(f"[PGSQL_RESTORE] pg_restore command not found")
        return {
            'success': False,
            'error': _('pg_restore command not found. Please ensure PostgreSQL client tools are installed.'),
            'details': 'pg_restore not in PATH'
        }

    except Exception as e:
        logger.error(f"[PGSQL_RESTORE] Unexpected error during restore: {e}", exc_info=True)
        return {
            'success': False,
            'error': f'Restore failed: {str(e)}',
            'details': str(e)
        }

    finally:
        # ALWAYS clean up temporary backup file
        if temp_backup_path and temp_backup_path.exists():
            for cleanup_attempt in range(5):
                try:
                    temp_backup_path.unlink()
                    logger.info(f"[PGSQL_RESTORE] Temporary backup file deleted")
                    break
                except PermissionError:
                    if cleanup_attempt < 4:
                        logger.debug(f"[PGSQL_RESTORE] Temp file locked, retry {cleanup_attempt + 1}/5")
                        gc.collect()
                        time.sleep(0.5)
                    else:
                        logger.warning(f"[PGSQL_RESTORE] Could not delete temp file after 5 attempts: {temp_backup_path}")
                except Exception as cleanup_error:
                    logger.warning(f"[PGSQL_RESTORE] Could not delete temp file: {cleanup_error}")
                    break
