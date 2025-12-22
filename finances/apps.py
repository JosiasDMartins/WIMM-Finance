from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class FinancesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'finances'

    def ready(self):
        """
        This method is called when Django starts.

        Handles:
        1. Database initialization (PostgreSQL or SQLite)
        2. Automatic migration from SQLite to PostgreSQL if needed
        3. Running migrations if database is empty
        """
        # Only run in main process (not in reloader)
        import os
        if os.environ.get('RUN_MAIN') != 'true' and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
            return

        try:
            from django.conf import settings
            from finances.utils.db_backup import get_database_engine
            from finances.utils.db_startup import initialize_database

            db_engine = get_database_engine()
            db_config = settings.DATABASES['default']

            # Log database type
            if db_engine == 'sqlite':
                db_path = db_config.get('NAME', 'unknown')
                logger.info(f"[STARTUP] 💾 Using SQLite database: {db_path}")
            elif db_engine == 'postgresql':
                db_name = db_config.get('NAME', 'unknown')
                db_host = db_config.get('HOST', 'unknown')
                db_port = db_config.get('PORT', '5432')
                db_user = db_config.get('USER', 'unknown')
                db_password = db_config.get('PASSWORD')

                if not db_password or db_name == 'unknown' or db_host == 'unknown' or db_user == 'unknown':
                    logger.warning(f"[STARTUP] [WARNING] PostgreSQL configured but credentials incomplete!")
                    logger.warning(f"[STARTUP]     NAME: {db_name}, USER: {db_user}, HOST: {db_host}, PASSWORD: {'SET' if db_password else 'MISSING'}")
                    logger.warning(f"[STARTUP]     Please check config/local_settings.py and .env file")
                    return
                else:
                    logger.info(f"[STARTUP] Using PostgreSQL database: {db_name}@{db_host}:{db_port} (user: {db_user})")
            else:
                logger.info(f"[STARTUP] Using {db_engine} database")

            # Initialize database (create if needed, migrate if needed, import SQLite if needed)
            logger.info("[STARTUP] Initializing database...")
            result = initialize_database()

            if result.get('success'):
                logger.info(f"[STARTUP] [OK] {result['message']}")
                if result.get('details'):
                    for detail in result['details']:
                        logger.info(f"[STARTUP]    - {detail}")
            else:
                logger.warning(f"[STARTUP] [WARNING] {result['message']}")

        except Exception as e:
            # Don't crash the application if initialization fails
            logger.error(f"[STARTUP] Error during database initialization: {e}", exc_info=True)
