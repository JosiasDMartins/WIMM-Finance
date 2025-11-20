# finances/middleware.py

from django.shortcuts import redirect
from django.urls import reverse, resolve, Resolver404
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.utils import OperationalError

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

        # Always allow setup page itself and restore-backup API
        try:
            setup_url = reverse('initial_setup')
            restore_backup_url = reverse('restore_backup')
            if current_path == setup_url or current_path == restore_backup_url:
                return self.get_response(request)
        except:
            # Fallback to direct path check
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
                except:
                    # If reverse fails, use direct path
                    return redirect('/setup/')
        except OperationalError:
            # Database doesn't exist yet or tables not created
            # Redirect to setup page which will handle DB creation
            try:
                return redirect('initial_setup')
            except:
                return redirect('/setup/')
        except Exception as e:
            # Any other database error - allow setup page
            print(f"Database check error in middleware: {e}")
            try:
                return redirect('initial_setup')
            except:
                return redirect('/setup/')
        
        # Users exist - continue normal flow
        response = self.get_response(request)
        return response
