"""
Database initialization and automatic migration module.

This module handles:
1. Database connection verification
2. Database creation if needed (PostgreSQL)
3. Running initial migrations if database is empty
4. Automatic migration from SQLite to PostgreSQL if applicable

This runs during Django startup (apps.py ready()) and is Docker-independent.
"""

import logging
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from django.conf import settings
from django.core.management import call_command
from django.db import connection, connections
from finances.utils.db_backup import get_database_engine

logger = logging.getLogger(__name__)


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
        logger.info(f"[DB_INIT] Checking if database '{db_name}' exists...")

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
            logger.info(f"[DB_INIT] [OK] Database '{db_name}' exists")
            cursor.close()
            conn.close()
            return {
                'exists': True,
                'created': False,
                'message': f"Database '{db_name}' already exists"
            }

        # Database doesn't exist - create it
        logger.info(f"[DB_INIT] [WARN] Database '{db_name}' does not exist - creating...")

        cursor.execute(sql.SQL("CREATE DATABASE {}").format(
            sql.Identifier(db_name)
        ))

        logger.info(f"[DB_INIT] [OK] Database '{db_name}' created successfully")

        cursor.close()
        conn.close()

        return {
            'exists': True,
            'created': True,
            'message': f"Database '{db_name}' created successfully"
        }

    except psycopg2.OperationalError as e:
        logger.error(f"[DB_INIT] [ERROR] Cannot connect to PostgreSQL server: {e}")
        return {
            'exists': False,
            'created': False,
            'message': f"Cannot connect to PostgreSQL: {e}"
        }
    except Exception as e:
        logger.error(f"[DB_INIT] [ERROR] Error checking/creating database: {e}")
        return {
            'exists': False,
            'created': False,
            'message': f"Error: {e}"
        }


def check_database_has_tables():
    """
    Check if the database has tables (is initialized).

    Returns:
        bool: True if database has tables, False otherwise
    """
    try:
        # Close any stale connections first
        connections.close_all()

        # Try to get table names
        with connection.cursor() as cursor:
            if get_database_engine() == 'postgresql':
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_type = 'BASE TABLE'
                """)
            else:  # SQLite
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM sqlite_master
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)

            count = cursor.fetchone()[0]
            has_tables = count > 0

            if has_tables:
                logger.info(f"[DB_INIT] Database has {count} tables")
            else:
                logger.info(f"[DB_INIT] Database is empty (no tables)")

            return has_tables

    except Exception as e:
        logger.debug(f"[DB_INIT] Cannot check tables (database might not exist or no connection yet): {e}")
        # If we can't connect, assume no tables
        return False


def run_migrations():
    """
    Run Django migrations to create/update database schema.

    Returns:
        dict: {'success': bool, 'message': str}
    """
    try:
        logger.info(f"[DB_INIT] Running Django migrations...")

        # Close any existing connections to avoid locks
        connections.close_all()

        # Run migrations
        call_command('migrate', verbosity=1, interactive=False)

        logger.info(f"[DB_INIT] [OK] Migrations completed successfully")

        return {
            'success': True,
            'message': 'Migrations completed successfully'
        }

    except Exception as e:
        logger.error(f"[DB_INIT] [ERROR] Migrations failed: {e}")
        return {
            'success': False,
            'message': f'Migrations failed: {e}'
        }


def initialize_database():
    """
    Initialize database with the following logic:

    1. Detect configured database (SQLite or PostgreSQL)
    2. If PostgreSQL:
       a. Check if database exists, create if needed
       b. Check if SQLite exists. If so, run migrations on it first.
       c. Check if SQLite has data.
       d. Run migrations on PostgreSQL to create schema.
       e. If SQLite has data, import it to PostgreSQL.
    3. If SQLite: Just ensure it exists and has tables.

    Returns:
        dict: success bool, message str, details list
    """
    details = []
    db_engine = get_database_engine()

    from finances.utils.db_migration import get_sqlite_path, sqlite_has_data, migrate_sqlite_to_postgres

    logger.info(f"[DB_INIT] ==========================================")
    logger.info(f"[DB_INIT] DATABASE INITIALIZATION")
    logger.info(f"[DB_INIT] ==========================================")

    if db_engine == 'postgresql':
        db_config = settings.DATABASES['default']
        logger.info(f"[DB_INIT] System Database: PostgreSQL")
        logger.info(f"[DB_INIT]   Host: {db_config.get('HOST', 'localhost')}")
        logger.info(f"[DB_INIT]   Port: {db_config.get('PORT', '5432')}")
        logger.info(f"[DB_INIT]   Database: {db_config.get('NAME')}")

        db_check = check_postgres_database_exists()
        if not db_check['exists']:
            return {'success': False, 'message': db_check['message'], 'details': []}
        if db_check['created']:
            details.append("PostgreSQL database created")

        # Check for SQLite migration
        sqlite_path = get_sqlite_path()
        sqlite_needs_migration = False

        if sqlite_path:
            logger.info(f"[DB_INIT] ==========================================")
            logger.info(f"[DB_INIT] LEGACY SQLITE DATABASE DETECTED")
            logger.info(f"[DB_INIT] ==========================================")
            logger.info(f"[DB_INIT] SQLite file: {sqlite_path}")

            # Temporarily switch to SQLite to ensure its schema is up-to-date
            original_db_config = settings.DATABASES['default'].copy()
            logger.info(f"[DB_INIT] Updating SQLite schema (if needed)...")
            settings.DATABASES['default'] = {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': sqlite_path,
            }
            connections.close_all()

            # Run migrations on SQLite
            migration_result = run_migrations()
            if not migration_result['success']:
                # Restore original settings before failing
                settings.DATABASES['default'] = original_db_config
                connections.close_all()
                return {'success': False, 'message': f"Failed to migrate SQLite schema: {migration_result['message']}", 'details': details}

            # Now check if it has data
            has_data = sqlite_has_data(sqlite_path)
            if has_data:
                sqlite_needs_migration = True
                logger.info(f"[DB_INIT] SQLite contains data - will migrate to PostgreSQL")
            else:
                logger.info(f"[DB_INIT] SQLite is empty - no migration needed")

            # Switch back to PostgreSQL
            logger.info(f"[DB_INIT] Switching back to PostgreSQL configuration...")
            settings.DATABASES['default'] = original_db_config
            connections.close_all()

        # Run migrations on PostgreSQL
        logger.info(f"[DB_INIT] Initializing PostgreSQL schema...")
        migration_result = run_migrations()
        if not migration_result['success']:
            return {'success': False, 'message': migration_result['message'], 'details': details}
        details.append("PostgreSQL schema is up to date.")

        # If SQLite migration is needed, do it now
        if sqlite_needs_migration:
            logger.info(f"[DB_INIT] ==========================================")
            logger.info(f"[DB_INIT] MIGRATING DATA: SQLite -> PostgreSQL")
            logger.info(f"[DB_INIT] ==========================================")

            migration_result = migrate_sqlite_to_postgres(sqlite_path)
            if migration_result['success']:
                details.append(f"[OK] {migration_result['message']}")
                logger.info(f"[DB_INIT] [OK] SQLite data successfully migrated to PostgreSQL")
            else:
                logger.error(f"[DB_INIT] [ERROR] SQLite migration failed: {migration_result['message']}")
                return {'success': False, 'message': f"SQLite migration failed: {migration_result['message']}", 'details': details}

    elif db_engine == 'sqlite':
        db_path = settings.DATABASES['default'].get('NAME')
        logger.info(f"[DB_INIT] System Database: SQLite")
        logger.info(f"[DB_INIT]   Path: {db_path}")

        has_tables = check_database_has_tables()
        if not has_tables:
            logger.info(f"[DB_INIT] SQLite database is empty - initializing schema...")
            details.append("Initializing SQLite schema...")
            migration_result = run_migrations()
            if migration_result['success']:
                details.append("[OK] SQLite initialized successfully")
            else:
                return {'success': False, 'message': migration_result['message'], 'details': details}
        else:
            logger.info(f"[DB_INIT] SQLite schema is already initialized")
            details.append("SQLite database already initialized")

    logger.info(f"[DB_INIT] ==========================================")
    logger.info(f"[DB_INIT] [OK] DATABASE INITIALIZATION COMPLETE")
    logger.info(f"[DB_INIT] ==========================================")

    return {
        'success': True,
        'message': 'Database initialized successfully',
        'details': details
    }
