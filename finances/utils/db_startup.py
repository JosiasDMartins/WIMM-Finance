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
            logger.info(f"[DB_INIT] ✅ Database '{db_name}' exists")
            cursor.close()
            conn.close()
            return {
                'exists': True,
                'created': False,
                'message': f"Database '{db_name}' already exists"
            }

        # Database doesn't exist - create it
        logger.info(f"[DB_INIT] ⚠️  Database '{db_name}' does not exist - creating...")

        cursor.execute(sql.SQL("CREATE DATABASE {}").format(
            sql.Identifier(db_name)
        ))

        logger.info(f"[DB_INIT] ✅ Database '{db_name}' created successfully")

        cursor.close()
        conn.close()

        return {
            'exists': True,
            'created': True,
            'message': f"Database '{db_name}' created successfully"
        }

    except psycopg2.OperationalError as e:
        logger.error(f"[DB_INIT] ❌ Cannot connect to PostgreSQL server: {e}")
        return {
            'exists': False,
            'created': False,
            'message': f"Cannot connect to PostgreSQL: {e}"
        }
    except Exception as e:
        logger.error(f"[DB_INIT] ❌ Error checking/creating database: {e}")
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

        logger.info(f"[DB_INIT] ✅ Migrations completed successfully")

        return {
            'success': True,
            'message': 'Migrations completed successfully'
        }

    except Exception as e:
        logger.error(f"[DB_INIT] ❌ Migrations failed: {e}")
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
       b. Check if database has tables
       c. If no tables: Run migrations
       d. After migrations, check for SQLite data to import
    3. If SQLite: Just ensure it exists and has tables

    Returns:
        dict: {'success': bool, 'message': str, 'details': list}
    """
    details = []
    db_engine = get_database_engine()

    logger.info(f"[DB_INIT] ========================================")
    logger.info(f"[DB_INIT] DATABASE INITIALIZATION")
    logger.info(f"[DB_INIT] Engine: {db_engine}")
    logger.info(f"[DB_INIT] ========================================")

    # STEP 1: Handle based on database type
    if db_engine == 'postgresql':
        # STEP 2: Check if PostgreSQL database exists
        db_check = check_postgres_database_exists()

        if not db_check['exists']:
            return {
                'success': False,
                'message': db_check['message'],
                'details': []
            }

        if db_check['created']:
            details.append("PostgreSQL database created")

        # STEP 3: Check if database has tables
        has_tables = check_database_has_tables()

        if not has_tables:
            # STEP 3a: Database is empty - run migrations
            logger.info(f"[DB_INIT] Database is empty - running initial migrations...")
            details.append("Running initial migrations...")

            migration_result = run_migrations()

            if not migration_result['success']:
                return {
                    'success': False,
                    'message': migration_result['message'],
                    'details': details
                }

            details.append("Initial migrations completed")

            # STEP 3b: After migrations, check for SQLite data to import
            logger.info(f"[DB_INIT] Checking for SQLite data to import...")

            from finances.utils.db_migration import get_sqlite_path, sqlite_has_data, migrate_sqlite_to_postgres

            sqlite_path = get_sqlite_path()

            if sqlite_path and sqlite_has_data(sqlite_path):
                logger.info(f"[DB_INIT] Found SQLite database with data - migrating to PostgreSQL...")
                details.append(f"Found SQLite database with data at {sqlite_path}")

                migration_result = migrate_sqlite_to_postgres(sqlite_path)

                if migration_result['success']:
                    details.append("✅ SQLite data migrated to PostgreSQL")
                    details.append(f"   {migration_result.get('details', '')}")
                else:
                    details.append(f"⚠️  SQLite migration failed: {migration_result.get('message')}")
            else:
                logger.info(f"[DB_INIT] No SQLite data to import")
                details.append("No SQLite data found to import")

        else:
            # Database already has tables
            details.append("Database already initialized with tables")

            # Check if there are pending migrations
            try:
                from io import StringIO
                import sys

                # Capture output of showmigrations
                old_stdout = sys.stdout
                sys.stdout = StringIO()

                call_command('showmigrations', '--plan', verbosity=0)

                output = sys.stdout.getvalue()
                sys.stdout = old_stdout

                # Check if there are unapplied migrations (lines starting with [ ])
                unapplied = [line for line in output.split('\n') if line.strip().startswith('[ ]')]

                if unapplied:
                    logger.info(f"[DB_INIT] Found {len(unapplied)} pending migrations - applying...")
                    details.append(f"Applying {len(unapplied)} pending migrations...")

                    migration_result = run_migrations()

                    if migration_result['success']:
                        details.append("Pending migrations applied")
                    else:
                        details.append(f"⚠️  Migration failed: {migration_result['message']}")

            except Exception as e:
                logger.debug(f"[DB_INIT] Could not check for pending migrations: {e}")

    elif db_engine == 'sqlite':
        # SQLite - just check if it has tables
        has_tables = check_database_has_tables()

        if not has_tables:
            logger.info(f"[DB_INIT] SQLite database is empty - running initial migrations...")
            details.append("Running initial migrations on SQLite...")

            migration_result = run_migrations()

            if migration_result['success']:
                details.append("SQLite initialized with tables")
            else:
                return {
                    'success': False,
                    'message': migration_result['message'],
                    'details': details
                }
        else:
            details.append("SQLite database already initialized")

    logger.info(f"[DB_INIT] ========================================")
    logger.info(f"[DB_INIT] DATABASE INITIALIZATION COMPLETE")
    logger.info(f"[DB_INIT] ========================================")

    return {
        'success': True,
        'message': 'Database initialized successfully',
        'details': details
    }
