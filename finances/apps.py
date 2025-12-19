from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class FinancesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'finances'

    def ready(self):
        """
        This method is called when Django starts.
        We use it to check for automatic database migration from SQLite to PostgreSQL.
        """
        # Only run migration check in main process (not in reloader)
        import os
        if os.environ.get('RUN_MAIN') != 'true' and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
            # Skip in reloader process
            return

        try:
            # Log which database is being used
            from django.conf import settings
            from finances.utils.db_backup import get_database_engine

            db_engine = get_database_engine()
            db_config = settings.DATABASES['default']

            if db_engine == 'sqlite':
                db_path = db_config.get('NAME', 'unknown')
                logger.info(f"[STARTUP] 💾 Using SQLite database: {db_path}")
            elif db_engine == 'postgresql':
                db_name = db_config.get('NAME', 'unknown')
                db_host = db_config.get('HOST', 'unknown')
                db_port = db_config.get('PORT', '5432')
                db_user = db_config.get('USER', 'unknown')
                db_password = db_config.get('PASSWORD')

                # Check if credentials are properly configured
                if not db_password or db_name == 'unknown' or db_host == 'unknown' or db_user == 'unknown':
                    logger.warning(f"[STARTUP] ⚠️  PostgreSQL configured but credentials incomplete!")
                    logger.warning(f"[STARTUP]     NAME: {db_name}, USER: {db_user}, HOST: {db_host}, PASSWORD: {'SET' if db_password else 'MISSING'}")
                    logger.warning(f"[STARTUP]     Please check config/local_settings.py and .env file")
                else:
                    logger.info(f"[STARTUP] 🐘 Using PostgreSQL database: {db_name}@{db_host}:{db_port} (user: {db_user})")
            else:
                logger.info(f"[STARTUP] ⚙️ Using {db_engine} database")

            # Check for automatic database migration
            from finances.utils.db_migration import check_and_migrate

            logger.info("[STARTUP] Checking for automatic database migration...")
            result = check_and_migrate()

            if result.get('migrated'):
                logger.info(f"[STARTUP] ✅ {result['message']}")
                if result.get('details'):
                    logger.info(f"[STARTUP] Details: {result['details']}")
            else:
                logger.debug(f"[STARTUP] Migration not needed: {result['message']}")

        except Exception as e:
            # Don't crash the application if migration check fails
            logger.error(f"[STARTUP] Error during migration check: {e}", exc_info=True)
