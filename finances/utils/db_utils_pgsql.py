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

def create_postgres_backup(family_id=None):
    """
    Create a backup of PostgreSQL database.

    If family_id is provided, creates a family-isolated backup containing only
    data for that specific family. Otherwise, creates a full database backup.

    Args:
        family_id (int, optional): ID of the family to backup. If None, backs up entire database.

    Returns:
        dict: {'success': bool, 'backup_path': str, 'filename': str, 'size': int, 'error': str}
    """
    if family_id is not None:
        return _create_family_isolated_postgres_backup(family_id)
    else:
        return _create_full_postgres_backup()


def _create_full_postgres_backup():
    """
    Create a FULL backup of PostgreSQL database using pg_dump.
    This backs up the entire database with all families.

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
        backup_filename = f'backup_full_{timestamp}.dump'
        backup_path = backups_dir / backup_filename

        logger.info(f"[PGSQL_BACKUP] Creating FULL PostgreSQL backup: {backup_path}")

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
        logger.info(f"[PGSQL_BACKUP] FULL PostgreSQL backup created successfully ({file_size} bytes)")

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


def _create_family_isolated_postgres_backup(family_id):
    """
    Create a family-isolated PostgreSQL backup containing only data for a specific family.

    This creates a SQL dump file with:
    - Schema (CREATE TABLE statements)
    - Only the specified family's data
    - All users that are members of that family
    - All periods, transactions, flow groups, etc. for that family

    Args:
        family_id (int): ID of the family to backup

    Returns:
        dict: {'success': bool, 'backup_path': str, 'filename': str, 'size': int, 'family_name': str, 'error': str}
    """
    try:
        from finances.models import Family, FamilyMember

        # Get family name
        try:
            family = Family.objects.get(id=family_id)
            family_name = family.name
        except Family.DoesNotExist:
            return {
                'success': False,
                'error': _('Family with ID %(family_id)s not found') % {'family_id': family_id}
            }

        # Get database connection parameters
        db_config = settings.DATABASES['default']
        db_name = db_config.get('NAME')
        db_user = db_config.get('USER')
        db_password = db_config.get('PASSWORD')
        db_host = db_config.get('HOST', 'localhost')
        db_port = db_config.get('PORT', '5432')

        # Create backups directory
        base_dir = Path(settings.BASE_DIR)
        backups_dir = base_dir / 'db' / 'backups'
        backups_dir.mkdir(parents=True, exist_ok=True)

        # Generate backup filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_family_name = "".join(c for c in family_name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_family_name = safe_family_name.replace(' ', '_')
        backup_filename = f'backup_{safe_family_name}_{timestamp}.sql'
        backup_path = backups_dir / backup_filename

        logger.info(f"[PGSQL_FAMILY_BACKUP] Creating family-isolated backup for '{family_name}' (ID: {family_id})")
        logger.info(f"[PGSQL_FAMILY_BACKUP] Backup file: {backup_path}")

        # Get all user IDs and member IDs for this family
        user_ids = list(FamilyMember.objects.filter(family_id=family_id).values_list('user_id', flat=True))
        member_ids = list(FamilyMember.objects.filter(family_id=family_id).values_list('id', flat=True))

        logger.info(f"[PGSQL_FAMILY_BACKUP] Found {len(user_ids)} users, {len(member_ids)} members")

        # Connect to PostgreSQL
        conn = psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port
        )
        cursor = conn.cursor()

        # Open backup file for writing
        with open(backup_path, 'w', encoding='utf-8') as backup_file:
            # Write header
            backup_file.write("-- SweetMoney Family-Isolated Backup\n")
            backup_file.write(f"-- Family: {family_name} (ID: {family_id})\n")
            backup_file.write(f"-- Generated: {datetime.now().isoformat()}\n")
            backup_file.write(f"-- Users: {len(user_ids)}\n")
            backup_file.write("--\n")
            backup_file.write("-- This backup contains ONLY data for the specified family.\n")
            backup_file.write("-- It can be restored to a fresh SweetMoney instance.\n")
            backup_file.write("--\n\n")

            backup_file.write("BEGIN;\n\n")

            # STEP 1: Export schema for all tables
            logger.info(f"[PGSQL_FAMILY_BACKUP] Exporting schema...")
            backup_file.write("-- ==============================================\n")
            backup_file.write("-- SCHEMA\n")
            backup_file.write("-- ==============================================\n\n")

            # Get schema using pg_dump for schema only
            schema_cmd = [
                'pg_dump',
                '--username', db_user,
                '--host', db_host,
                '--port', str(db_port),
                '--dbname', db_name,
                '--schema-only',  # Only schema, no data
                '--no-owner',  # Don't include ownership commands
                '--no-privileges'  # Don't include privilege commands
            ]

            env = os.environ.copy()
            env['PGPASSWORD'] = db_password

            schema_result = subprocess.run(
                schema_cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=120
            )

            if schema_result.returncode == 0:
                backup_file.write(schema_result.stdout)
                backup_file.write("\n\n")
            else:
                logger.error(f"[PGSQL_FAMILY_BACKUP] Schema dump failed: {schema_result.stderr}")
                cursor.close()
                conn.close()
                return {
                    'success': False,
                    'error': _('Failed to dump schema: %(error)s') % {'error': schema_result.stderr}
                }

            # STEP 2: Export data for family-specific tables
            logger.info(f"[PGSQL_FAMILY_BACKUP] Exporting family data...")
            backup_file.write("-- ==============================================\n")
            backup_file.write("-- DATA\n")
            backup_file.write("-- ==============================================\n\n")

            # Disable triggers during data import
            backup_file.write("SET session_replication_role = 'replica';\n\n")

            total_rows_copied = 0

            # Define tables and their WHERE clauses
            tables_to_export = [
                # Core user and family tables
                ('finances_customuser', f'id IN ({",".join(map(str, user_ids))})' if user_ids else '1=0'),
                ('finances_family', f'id = {family_id}'),
                ('finances_familymember', f'family_id = {family_id}'),
                ('finances_familyconfiguration', f'family_id = {family_id}'),

                # Period and flow groups
                ('finances_period', f'family_id = {family_id}'),
                ('finances_flowgroup', f'family_id = {family_id}'),

                # Transactions (via member)
                ('finances_transaction', f'member_id IN ({",".join(map(str, member_ids))})' if member_ids else '1=0'),

                # History and access
                ('finances_familymemberrolehistory', f'member_id IN ({",".join(map(str, member_ids))})' if member_ids else '1=0'),
                ('finances_flowgroupaccess', f'member_id IN ({",".join(map(str, member_ids))})' if member_ids else '1=0'),

                # Investments and balances
                ('finances_investment', f'family_id = {family_id}'),
                ('finances_bankbalance', f'family_id = {family_id}'),

                # Notifications
                ('finances_notification', f'family_id = {family_id}'),
            ]

            for table_name, where_clause in tables_to_export:
                try:
                    # Get column names
                    cursor.execute(f"""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = %s
                        ORDER BY ordinal_position
                    """, (table_name,))
                    columns = [row[0] for row in cursor.fetchall()]

                    if not columns:
                        logger.debug(f"[PGSQL_FAMILY_BACKUP] Table {table_name} not found, skipping")
                        continue

                    columns_str = ', '.join([f'"{col}"' for col in columns])

                    # Select data
                    query = f"SELECT {columns_str} FROM {table_name} WHERE {where_clause}"
                    cursor.execute(query)
                    rows = cursor.fetchall()

                    if rows:
                        backup_file.write(f"-- Table: {table_name} ({len(rows)} rows)\n")

                        # Write COPY statement for efficient bulk insert
                        copy_columns = ', '.join([f'"{col}"' for col in columns])
                        backup_file.write(f"COPY {table_name} ({copy_columns}) FROM stdin;\n")

                        for row in rows:
                            # Convert row to PostgreSQL COPY format (tab-separated)
                            row_data = []
                            for value in row:
                                if value is None:
                                    row_data.append('\\N')
                                elif isinstance(value, bool):
                                    row_data.append('t' if value else 'f')
                                elif isinstance(value, (datetime, )):
                                    row_data.append(str(value))
                                else:
                                    # Escape special characters for COPY format
                                    str_value = str(value).replace('\\', '\\\\').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
                                    row_data.append(str_value)

                            backup_file.write('\t'.join(row_data) + '\n')

                        backup_file.write('\\.\n\n')
                        total_rows_copied += len(rows)
                        logger.info(f"[PGSQL_FAMILY_BACKUP] Exported {len(rows)} rows from {table_name}")

                except Exception as e:
                    logger.warning(f"[PGSQL_FAMILY_BACKUP] Error exporting {table_name}: {e}")
                    continue

            # Re-enable triggers
            backup_file.write("SET session_replication_role = 'origin';\n\n")

            # Update sequences to correct values
            backup_file.write("-- ==============================================\n")
            backup_file.write("-- UPDATE SEQUENCES\n")
            backup_file.write("-- ==============================================\n\n")

            cursor.execute("""
                SELECT sequence_name, table_name, column_name
                FROM information_schema.sequences
                WHERE sequence_schema = 'public'
            """)
            sequences = cursor.fetchall()

            for seq_name, _, _ in sequences:
                backup_file.write(f"SELECT setval('{seq_name}', COALESCE((SELECT MAX(id) FROM {seq_name.replace('_id_seq', '')}), 1));\n")

            backup_file.write("\n")
            backup_file.write("COMMIT;\n")

        cursor.close()
        conn.close()

        file_size = backup_path.stat().st_size
        logger.info(f"[PGSQL_FAMILY_BACKUP] Family-isolated backup created successfully")
        logger.info(f"[PGSQL_FAMILY_BACKUP] Family: {family_name}")
        logger.info(f"[PGSQL_FAMILY_BACKUP] File size: {file_size} bytes")
        logger.info(f"[PGSQL_FAMILY_BACKUP] Total rows: {total_rows_copied}")

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

    except subprocess.TimeoutExpired:
        logger.error(f"[PGSQL_FAMILY_BACKUP] Schema dump timed out")
        return {
            'success': False,
            'error': _('Backup operation timed out')
        }
    except FileNotFoundError:
        logger.error(f"[PGSQL_FAMILY_BACKUP] pg_dump command not found")
        return {
            'success': False,
            'error': _('pg_dump command not found. Please ensure PostgreSQL client tools are installed.')
        }
    except Exception as e:
        logger.error(f"[PGSQL_FAMILY_BACKUP] Family backup failed: {e}", exc_info=True)
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
