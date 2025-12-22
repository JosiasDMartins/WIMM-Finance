"""
Common database utilities used across multiple modules.

This module provides functions that are used by both SQLite and PostgreSQL
specific modules, such as database engine detection and backup type detection.
"""

import sqlite3
import logging
from pathlib import Path
from django.conf import settings

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


def detect_backup_type(file_path):
    """
    Detect whether a backup file is SQLite or PostgreSQL.

    Detection strategy:
    1. Try to open as SQLite database - if successful, it's SQLite
    2. If SQLite fails, check file signature for PostgreSQL dump
    3. PostgreSQL custom format dumps start with 'PGDMP'

    Args:
        file_path: Path or str to the backup file

    Returns:
        str: 'sqlite', 'postgresql', or 'unknown'
    """
    try:
        file_path = Path(file_path)

        if not file_path.exists():
            logger.error(f"[DETECT_TYPE] File does not exist: {file_path}")
            return 'unknown'

        # STRATEGY 1: Try to open as SQLite database
        try:
            logger.info(f"[DETECT_TYPE] Attempting to open as SQLite: {file_path}")
            conn = sqlite3.connect(str(file_path))
            cursor = conn.cursor()

            # Try to query sqlite_master (exists in all SQLite databases)
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
            cursor.fetchone()

            cursor.close()
            conn.close()

            logger.info(f"[DETECT_TYPE] File is SQLite database")
            return 'sqlite'

        except sqlite3.DatabaseError as e:
            logger.debug(f"[DETECT_TYPE] Not a SQLite database: {e}")
            # Not SQLite, continue to check PostgreSQL

        # STRATEGY 2: Check for PostgreSQL custom dump signature
        # PostgreSQL custom format dumps start with "PGDMP" magic bytes
        try:
            with open(file_path, 'rb') as f:
                # Read first 5 bytes
                header = f.read(5)

                # PostgreSQL custom format signature
                if header == b'PGDMP':
                    logger.info(f"[DETECT_TYPE] File is PostgreSQL custom dump (PGDMP signature)")
                    return 'postgresql'

                # Check for plain SQL dump (starts with -- or /*)
                if header.startswith(b'--') or header.startswith(b'/*'):
                    logger.info(f"[DETECT_TYPE] File appears to be PostgreSQL plain SQL dump")
                    return 'postgresql'

        except Exception as e:
            logger.error(f"[DETECT_TYPE] Error reading file header: {e}")

        logger.warning(f"[DETECT_TYPE] Could not determine backup type")
        return 'unknown'

    except Exception as e:
        logger.error(f"[DETECT_TYPE] Error detecting backup type: {e}", exc_info=True)
        return 'unknown'
