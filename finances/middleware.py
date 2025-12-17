# finances/middleware.py

import logging
import sqlite3
from pathlib import Path
from datetime import datetime
from django.shortcuts import redirect
from django.urls import reverse, resolve, Resolver404
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.utils import OperationalError, DatabaseError
from django.core.exceptions import ImproperlyConfigured
from django.utils import translation
from django.conf import settings

logger = logging.getLogger(__name__)


def handle_corrupted_database():
    """
    TEMPORARY: Disabled during restore operations.

    Handles a corrupted database by renaming it with a timestamp and redirecting to setup.

    Returns:
        True if database was corrupted and renamed, False otherwise

    TODO: Modularize this function and make it safe to run during restore operations.
    Current issue: Opens SQLite connections that lock the database file on Windows.
    """
    # DISABLED: This function opens SQLite connections that can lock the database
    # during restore operations, preventing file deletion/renaming on Windows
    logger.warning("[handle_corrupted_database] Function temporarily disabled to avoid DB locks")
    return False

    # Original implementation commented out:
    # try:
    #     db_path = Path(settings.DATABASES['default']['NAME'])
    #     if not db_path.exists():
    #         return False
    #     try:
    #         conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True, timeout=1.0)
    #         cursor = conn.cursor()
    #         cursor.execute("PRAGMA integrity_check")
    #         result = cursor.fetchone()
    #         cursor.close()
    #         conn.close()
    #         del cursor
    #         del conn
    #         if result and result[0] == 'ok':
    #             return False
    #     except sqlite3.DatabaseError as e:
    #         logger.error(f"Corrupted database detected: {e}")
    #     timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    #     corrupted_name = db_path.parent / f'{db_path.stem}_corrupted_{timestamp}{db_path.suffix}'
    #     logger.warning(f"Renaming corrupted database from {db_path} to {corrupted_name}")
    #     db_path.rename(corrupted_name)
    #     return True
    # except Exception as e:
    #     logger.error(f"Error handling corrupted database: {e}")
    #     return False


class UserLanguageMiddleware:
    """
    Middleware to activate the user's preferred language.
    Must be placed after AuthenticationMiddleware in settings.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            if request.user.is_authenticated and hasattr(request.user, 'language'):
                user_language = request.user.language
                if user_language:
                    translation.activate(user_language)
                    request.LANGUAGE_CODE = user_language
        except (OperationalError, DatabaseError) as e:
            # If there's a DB error (like missing django_session table),
            # just skip language activation and let SetupRequiredMiddleware handle it
            logger.debug(f"Database error in UserLanguageMiddleware, skipping language activation: {e}")
            pass

        response = self.get_response(request)
        return response


class SetupRequiredMiddleware:
    """
    Middleware that redirects to setup page if:
    1. No users exist in the database (first-time setup needed)
    2. User is not on the setup page already
    
    This middleware runs BEFORE login_required decorator.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Get current path
        current_path = request.path

        # Always allow static files and admin
        if current_path.startswith('/static/') or current_path.startswith('/admin/'):
            return self.get_response(request)

        # Always allow health-check endpoint (used by updater to verify server is running)
        if current_path == '/api/health-check/':
            return self.get_response(request)

        # Always allow PWA files (must be accessible for browsers to detect installable PWA)
        # These files must be publicly accessible without authentication
        if current_path in ['/manifest.json', '/serviceworker.js', '/offline/']:
            return self.get_response(request)

        # Always allow setup page itself and restore-backup API
        try:
            setup_url = reverse('initial_setup')
            restore_backup_url = reverse('restore_backup')
            if current_path == setup_url or current_path == restore_backup_url:
                return self.get_response(request)
        except (Resolver404, ImproperlyConfigured) as e:
            # Fallback to direct path check if URL reverse fails
            logger.debug(f"URL reverse failed in middleware: {e}")
            if current_path in ['/setup/', '/restore-backup/']:
                return self.get_response(request)
        
        # Check if database is accessible and if users exist
        try:
            # CRITICAL: Check if database was recently modified (e.g., restored from backup)
            # If so, close all connections to force Django to reconnect to the new database
            db_path = Path(settings.DATABASES['default']['NAME'])

            if db_path.exists():
                from datetime import datetime, timedelta
                db_modified_time = datetime.fromtimestamp(db_path.stat().st_mtime)
                time_since_modification = datetime.now() - db_modified_time

                # If DB was modified in the last 10 seconds, close all connections FIRST
                # This ensures we reconnect to the new database
                if time_since_modification < timedelta(seconds=10):
                    from django.db import connections
                    logger.info(f"[MIDDLEWARE] DB modified {time_since_modification.total_seconds():.2f}s ago - closing {len(connections.all())} connections BEFORE querying")
                    for conn in connections.all():
                        try:
                            conn.close()
                        except Exception:
                            pass

                    # Force garbage collection to release references
                    import gc
                    gc.collect()

                    # CRITICAL: Wait for a moment to allow the OS to release file
                    # handles and for Django to be ready to create a new connection.
                    import time
                    time.sleep(1)

                    logger.info(f"[MIDDLEWARE] All connections closed, will reconnect to new DB")

            # Try to access the database
            UserModel = get_user_model()

            # Check if users table exists and has any records
            users_exist = UserModel.objects.exists()
            logger.info(f"[MIDDLEWARE] Path: {current_path}, DB exists: {db_path.exists()}, Users exist: {users_exist}")

            if not users_exist:
                # No users exist - redirect to setup
                # This takes priority over everything, including login
                logger.warning(f"[MIDDLEWARE] No users found, redirecting to setup from {current_path}")
                try:
                    return redirect('initial_setup')
                except (Resolver404, ImproperlyConfigured):
                    # If reverse fails, use direct path
                    return redirect('/setup/')
        except OperationalError as e:
            # Check if this is a session error due to missing/corrupted DB
            error_str = str(e).lower()
            is_session_table_error = 'django_session' in error_str and 'no such table' in error_str

            if is_session_table_error:
                # Session table missing - verify if DB exists and is functional
                logger.warning(f"Session table missing: {e}")

                # Check if database file exists
                db_path = Path(settings.DATABASES['default']['NAME'])
                db_missing_or_corrupted = False

                if not db_path.exists():
                    logger.error("Database file does not exist")
                    db_missing_or_corrupted = True
                else:
                    # DB exists but session table is missing
                    # TEMPORARY: Integrity check disabled during restore operations
                    # TODO: Modularize this into a separate function that can be disabled during restore
                    logger.warning("DB exists but session table missing - skipping integrity check during restore")
                    db_missing_or_corrupted = True

                if db_missing_or_corrupted:
                    # Clear the session cookie to prevent repeated errors
                    from django.http import HttpResponseRedirect
                    from django.conf import settings as django_settings

                    try:
                        redirect_url = reverse('initial_setup')
                    except (Resolver404, ImproperlyConfigured):
                        redirect_url = '/setup/'

                    response = HttpResponseRedirect(redirect_url)

                    # Delete the session cookie
                    session_cookie_name = django_settings.SESSION_COOKIE_NAME
                    response.delete_cookie(
                        session_cookie_name,
                        path=django_settings.SESSION_COOKIE_PATH,
                        domain=django_settings.SESSION_COOKIE_DOMAIN,
                    )

                    logger.info(f"Cleared session cookie '{session_cookie_name}' and redirecting to setup")
                    return response

            # Other OperationalError cases (not session-related)
            # Database doesn't exist yet or tables not created
            # Redirect to setup page which will handle DB creation
            try:
                return redirect('initial_setup')
            except (Resolver404, ImproperlyConfigured):
                return redirect('/setup/')
        except DatabaseError as e:
            # Check if database is corrupted ("database disk image is malformed")
            if 'malformed' in str(e).lower() or 'corrupt' in str(e).lower():
                logger.error(f"Corrupted database detected: {e}")
                # Rename corrupted database and redirect to setup
                if handle_corrupted_database():
                    logger.info("Corrupted database renamed, redirecting to setup")
                try:
                    return redirect('initial_setup')
                except (Resolver404, ImproperlyConfigured):
                    return redirect('/setup/')
            else:
                # Other database errors
                logger.warning(f"Database error in middleware: {e}")
                try:
                    return redirect('initial_setup')
                except (Resolver404, ImproperlyConfigured):
                    return redirect('/setup/')
        except Exception as e:
            # Any other database error - check if it's a corruption issue
            error_str = str(e).lower()
            if 'malformed' in error_str or 'corrupt' in error_str or 'database disk image' in error_str:
                logger.error(f"Corrupted database detected: {e}")
                if handle_corrupted_database():
                    logger.info("Corrupted database renamed, redirecting to setup")
            else:
                logger.warning(f"Database check error in middleware: {e}")
            try:
                return redirect('initial_setup')
            except (Resolver404, ImproperlyConfigured):
                return redirect('/setup/')
        
        # Users exist - continue normal flow
        response = self.get_response(request)
        return response
