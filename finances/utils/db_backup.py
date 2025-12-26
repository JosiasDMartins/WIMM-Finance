"""
Database backup utility with support for multiple database backends.

This module provides a unified interface (facade) for creating database backups
that works with both SQLite and PostgreSQL by delegating to specialized modules.
"""

import logging
from django.utils.translation import gettext as _

# Import from new organized modules
from finances.utils.db_utils_common import get_database_engine
from finances.utils.db_utils_sqlite import create_sqlite_backup
from finances.utils.db_utils_pgsql import create_postgres_backup

logger = logging.getLogger(__name__)


def create_database_backup(family_id=None):
    """
    Create a database backup file.

    Automatically detects the database backend and delegates to the appropriate
    backup function.

    Args:
        family_id (int, optional): ID of the family to backup. If None, backs up entire database.
                                   If provided, creates a family-isolated backup with only that family's data.

    Returns:
        dict: {
            'success': bool,
            'backup_path': str (if success),
            'filename': str (if success),
            'size': int (if success),
            'family_name': str (if family_id provided and success),
            'family_id': int (if family_id provided and success),
            'users_count': int (if family_id provided and success),
            'rows_copied': int (if family_id provided and success),
            'error': str (if not success)
        }
    """
    engine = get_database_engine()

    if family_id is not None:
        logger.info(f"[DB_BACKUP] Creating FAMILY-ISOLATED backup for family ID {family_id} on {engine} database")
    else:
        logger.info(f"[DB_BACKUP] Creating FULL backup for {engine} database")

    if engine == 'sqlite':
        return create_sqlite_backup(family_id=family_id)
    elif engine == 'postgresql':
        return create_postgres_backup(family_id=family_id)
    else:
        return {
            'success': False,
            'error': _('Unsupported database engine: %(engine)s') % {'engine': engine}
        }
