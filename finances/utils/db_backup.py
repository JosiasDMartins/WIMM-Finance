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


def create_database_backup():
    """
    Create a database backup file.

    Automatically detects the database backend and delegates to the appropriate
    backup function.

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
        return create_sqlite_backup()
    elif engine == 'postgresql':
        return create_postgres_backup()
    else:
        return {
            'success': False,
            'error': _('Unsupported database engine: %(engine)s') % {'engine': engine}
        }
