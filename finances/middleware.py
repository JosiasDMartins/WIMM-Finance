# finances/middleware.py

import logging
from django.shortcuts import redirect
from django.urls import reverse, resolve, Resolver404
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.utils import OperationalError
from django.core.exceptions import ImproperlyConfigured
from django.utils import translation

logger = logging.getLogger(__name__)


class UserLanguageMiddleware:
    """
    Middleware to activate the user's preferred language.
    Must be placed after AuthenticationMiddleware in settings.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and hasattr(request.user, 'language'):
            user_language = request.user.language
            if user_language:
                translation.activate(user_language)
                request.LANGUAGE_CODE = user_language

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
            # Try to access the database
            UserModel = get_user_model()
            
            # Check if users table exists and has any records
            if not UserModel.objects.exists():
                # No users exist - redirect to setup
                # This takes priority over everything, including login
                try:
                    return redirect('initial_setup')
                except (Resolver404, ImproperlyConfigured):
                    # If reverse fails, use direct path
                    return redirect('/setup/')
        except OperationalError:
            # Database doesn't exist yet or tables not created
            # Redirect to setup page which will handle DB creation
            try:
                return redirect('initial_setup')
            except (Resolver404, ImproperlyConfigured):
                return redirect('/setup/')
        except Exception as e:
            # Any other database error - allow setup page
            logger.warning(f"Database check error in middleware: {e}")
            try:
                return redirect('initial_setup')
            except (Resolver404, ImproperlyConfigured):
                return redirect('/setup/')
        
        # Users exist - continue normal flow
        response = self.get_response(request)
        return response
