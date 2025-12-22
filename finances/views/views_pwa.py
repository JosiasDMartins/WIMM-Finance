"""
PWA-related views for SweetMoney.

This module provides custom views for Progressive Web App functionality:
- Dynamic manifest.json with version synchronization
- Service worker with cache versioning
"""

from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.template.loader import render_to_string
from finances.models import SystemVersion
from finances.context_processors import VERSION as APP_VERSION
import logging

logger = logging.getLogger(__name__)


def manifest_json(request):
    """
    Custom manifest.json view that includes dynamic version from database.

    This ensures the PWA version is always synchronized with the server version,
    forcing reinstallation when the server is updated.

    IMPORTANT: Headers prevent caching to ensure Windows/browsers always get latest version.
    """
    # CRITICAL: Check if DB exists before trying to access it
    # During setup/restore, DB might not exist or be inaccessible
    from pathlib import Path
    from finances.utils.db_utils_common import get_database_engine

    db_engine = get_database_engine()
    db_exists = False

    if db_engine == 'sqlite':
        # For SQLite, check if file exists
        db_path = Path(settings.DATABASES['default']['NAME'])
        db_exists = db_path.exists()
    else:
        # For PostgreSQL, assume DB exists if configured
        # (PostgreSQL connection failures are handled by the exception block)
        db_exists = True

    if not db_exists:
        # DB doesn't exist yet (first-time setup)
        logger.debug(f"[MANIFEST] SQLite DB doesn't exist, using APP_VERSION: {APP_VERSION}")
        db_version = APP_VERSION
    else:
        try:
            db_version = SystemVersion.get_current_version()
        except Exception as e:
            logger.debug(f"[MANIFEST] Cannot access database version, using APP_VERSION: {APP_VERSION}")
            db_version = APP_VERSION

    manifest = {
        "name": settings.PWA_APP_NAME,
        "short_name": settings.PWA_APP_NAME,
        "description": settings.PWA_APP_DESCRIPTION,
        "version": db_version,  # Dynamic version from database
        "id": f"/?version={db_version}",  # Unique ID per version - forces Windows to detect update
        "start_url": f"/?version={db_version}",  # Include version in start_url for cache busting
        "scope": settings.PWA_APP_SCOPE,
        "display": settings.PWA_APP_DISPLAY,
        "orientation": settings.PWA_APP_ORIENTATION,
        "theme_color": settings.PWA_APP_THEME_COLOR,
        "background_color": settings.PWA_APP_BACKGROUND_COLOR,
        "lang": settings.PWA_APP_LANG,
        "dir": settings.PWA_APP_DIR,
        "icons": settings.PWA_APP_ICONS,
    }

    response = JsonResponse(manifest, safe=False)

    # CRITICAL: Prevent caching of manifest.json
    # Windows/browsers must always fetch latest version
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'

    return response


def service_worker(request):
    """
    Custom service worker view that includes dynamic cache version.

    The cache version is based on the database version, ensuring that
    when the server is updated, the service worker invalidates old caches
    and forces a fresh installation.

    IMPORTANT: Headers prevent caching to ensure browsers always get latest version.
    """
    # CRITICAL: Check if DB exists before trying to access it
    # During setup/restore, DB might not exist or be inaccessible
    from pathlib import Path
    from finances.utils.db_utils_common import get_database_engine

    db_engine = get_database_engine()
    db_exists = False

    if db_engine == 'sqlite':
        # For SQLite, check if file exists
        db_path = Path(settings.DATABASES['default']['NAME'])
        db_exists = db_path.exists()
    else:
        # For PostgreSQL, assume DB exists if configured
        # (PostgreSQL connection failures are handled by the exception block)
        db_exists = True

    if not db_exists:
        # DB doesn't exist yet (first-time setup)
        # Use APP_VERSION without accessing database
        logger.debug(f"[SERVICE_WORKER] SQLite DB doesn't exist, using APP_VERSION: {APP_VERSION}")
        db_version = APP_VERSION
    else:
        try:
            db_version = SystemVersion.get_current_version()
            if not db_version:
                db_version = APP_VERSION
        except Exception as e:
            logger.debug(f"[SERVICE_WORKER] Cannot access database version, using APP_VERSION: {APP_VERSION}")
            db_version = APP_VERSION

    # Render service worker template with dynamic version
    sw_content = render_to_string('finances/serviceworker.js', {
        'cache_version': db_version.replace('.', '_'),  # e.g., "1_4_2" for cache name
        'db_version': db_version
    })

    response = HttpResponse(
        sw_content,
        content_type='application/javascript; charset=utf-8'
    )

    # CRITICAL: Prevent caching of service worker
    # Browsers must always fetch latest version for update detection
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response['Service-Worker-Allowed'] = '/'

    return response
