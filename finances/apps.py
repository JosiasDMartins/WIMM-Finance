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
