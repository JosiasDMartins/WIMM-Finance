"""
Database backup utility with support for multiple database backends.

This module provides a unified interface for creating database backups
that works with both SQLite and PostgreSQL.
"""

import os
import logging
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from django.conf import settings
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


def get_database_engine():
    """
    Get the current database engine type.

    Returns:
        str: 'sqlite' or 'postgresql' or 'unknown'
    """
    engine = settings.DATABASES['default']['ENGINE']

    if 'sqlite3' in engine:
        return 'sqlite'
    elif 'postgresql' in engine:
        return 'postgresql'
    else:
        return 'unknown'


def create_database_backup():
    """
    Create a database backup file.

    Automatically detects the database backend and uses the appropriate
    backup strategy.

    Returns:
        dict: {
            'success': bool,
            'backup_path': str (if success),
            'filename': str (if success),
            'error': str (if not success)
        }
    """
    engine = get_database_engine()

    logger.info(f"[DB_BACKUP] Creating backup for {engine} database")

    if engine == 'sqlite':
        return _create_sqlite_backup()
    elif engine == 'postgresql':
        return _create_postgres_backup()
    else:
        return {
            'success': False,
            'error': _('Unsupported database engine: %(engine)s') % {'engine': engine}
        }


def _create_sqlite_backup():
    """
    Create a backup of SQLite database using native backup API.

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
        backup_filename = f'backup_{timestamp}.sqlite3'
        backup_path = backups_dir / backup_filename

        logger.info(f"[DB_BACKUP] Creating SQLite backup: {backup_path}")

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
        logger.info(f"[DB_BACKUP] SQLite backup created successfully ({file_size} bytes)")

        return {
            'success': True,
            'backup_path': str(backup_path),
            'filename': backup_filename,
            'size': file_size
        }

    except Exception as e:
        logger.error(f"[DB_BACKUP] SQLite backup failed: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }


def _create_postgres_backup():
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

        logger.info(f"[DB_BACKUP] Creating PostgreSQL backup: {backup_path}")

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
        logger.info(f"[DB_BACKUP] Executing pg_dump command")
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes timeout
        )

        if result.returncode != 0:
            logger.error(f"[DB_BACKUP] pg_dump failed: {result.stderr}")
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
        logger.info(f"[DB_BACKUP] PostgreSQL backup created successfully ({file_size} bytes)")

        return {
            'success': True,
            'backup_path': str(backup_path),
            'filename': backup_filename,
            'size': file_size
        }

    except subprocess.TimeoutExpired:
        logger.error(f"[DB_BACKUP] PostgreSQL backup timed out")
        return {
            'success': False,
            'error': _('Backup operation timed out')
        }
    except FileNotFoundError:
        logger.error(f"[DB_BACKUP] pg_dump command not found")
        return {
            'success': False,
            'error': _('pg_dump command not found. Please ensure PostgreSQL client tools are installed.')
        }
    except Exception as e:
        logger.error(f"[DB_BACKUP] PostgreSQL backup failed: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }
