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
    try:
        db_version = SystemVersion.get_current_version()
    except Exception as e:
        logger.error(f"Failed to get database version for manifest: {e}")
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
    try:
        db_version = SystemVersion.get_current_version()
    except Exception as e:
        logger.error(f"Failed to get database version for service worker: {e}")
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
