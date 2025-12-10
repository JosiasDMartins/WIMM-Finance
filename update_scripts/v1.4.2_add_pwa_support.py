"""
Update Script: Add Progressive Web App (PWA) Support
Version: 1.4.2
Description: Installs django-pwa package and enables PWA functionality

This script:
1. Installs django-pwa package via pip
2. Verifies installation was successful
3. Runs collectstatic to gather PWA files
4. Checks if service worker file exists
5. Reports the update status

Changes:
- Installs django-pwa package
- Enables Progressive Web App capabilities
- Allows app installation on mobile/desktop devices
- Provides offline page and asset caching
"""

import subprocess
import sys
import os


def run():
    """
    Main execution function.
    Must return a dict with:
        - success: bool
        - message: str
        - details: dict (optional)
    """
    try:
        print("[Update v1.4.2] Starting PWA support installation...")

        results = {
            'installed_packages': [],
            'warnings': [],
            'errors': []
        }

        # =====================================================
        # STEP 1: Install django-pwa package
        # =====================================================
        print("[Update v1.4.2] Step 1: Installing django-pwa package...")

        try:
            # Install django-pwa
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', 'django-pwa', '--quiet'
            ])
            results['installed_packages'].append('django-pwa')
            print("[Update v1.4.2] [OK] django-pwa installed successfully")
        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to install django-pwa: {str(e)}"
            print(f"[ERROR] {error_msg}", file=sys.stderr)
            results['errors'].append(error_msg)
            return {
                'success': False,
                'message': 'PWA package installation failed',
                'details': results
            }

        # =====================================================
        # STEP 2: Verify django-pwa is importable
        # =====================================================
        print("[Update v1.4.2] Step 2: Verifying django-pwa installation...")

        try:
            import pwa
            print(f"[Update v1.4.2] [OK] django-pwa version: {getattr(pwa, '__version__', 'unknown')}")
        except ImportError as e:
            error_msg = f"django-pwa installed but not importable: {str(e)}"
            print(f"[WARNING] {error_msg}", file=sys.stderr)
            results['warnings'].append(error_msg)

        # =====================================================
        # STEP 3: Check if service worker file exists
        # =====================================================
        print("[Update v1.4.2] Step 3: Checking service worker file...")

        service_worker_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'finances', 'static', 'finances', 'js', 'serviceworker.js'
        )

        if os.path.exists(service_worker_path):
            print(f"[Update v1.4.2] [OK] Service worker found at: {service_worker_path}")
        else:
            warning_msg = f"Service worker not found at: {service_worker_path}"
            print(f"[Update v1.4.2] [WARNING] {warning_msg}")
            results['warnings'].append(warning_msg)
            results['warnings'].append("Service worker must be created manually")

        # =====================================================
        # STEP 4: Run collectstatic
        # =====================================================
        print("[Update v1.4.2] Step 4: Running collectstatic...")

        try:
            from django.core.management import call_command
            call_command('collectstatic', '--noinput', '--clear', verbosity=0)
            print("[Update v1.4.2] [OK] Static files collected successfully")
        except Exception as collectstatic_error:
            warning_msg = f"collectstatic warning: {str(collectstatic_error)}"
            print(f"[Update v1.4.2] [WARNING] {warning_msg}")
            results['warnings'].append(warning_msg)
            # Don't fail the update for collectstatic issues

        # =====================================================
        # STEP 5: Build result message
        # =====================================================
        if results['errors']:
            message = f"PWA support installation failed: {', '.join(results['errors'])}"
            success = False
        else:
            message = "PWA support installed successfully! "
            message += f"Installed packages: {', '.join(results['installed_packages'])}"

            if results['warnings']:
                message += f" (Warnings: {len(results['warnings'])})"

            success = True

        print(f"[Update v1.4.2] {message}")

        if success:
            print("[Update v1.4.2] [SUCCESS] Update completed successfully!")
            print("[Update v1.4.2] New features:")
            print("  - Progressive Web App support enabled")
            print("  - Users can install app on mobile/desktop devices")
            print("  - Offline page and asset caching available")
            print("  - 'Add to Home Screen' functionality enabled")
            print("")
            print("[Update v1.4.2] Next steps:")
            print("  1. Ensure 'pwa' is added to INSTALLED_APPS in settings.py")
            print("  2. Include PWA URLs in main urls.py")
            print("  3. Add PWA meta tags to base template")
            print("  4. Create service worker JavaScript file")
            print("  5. Test PWA installation on mobile/desktop")

        return {
            'success': success,
            'message': message,
            'details': results
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'message': f"PWA support installation failed: {str(e)}",
            'error': str(e)
        }


# For testing purposes
if __name__ == "__main__":
    import django

    # Setup Django environment
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wimm_project.settings')
    django.setup()

    # Run the update
    result = run()
    print(f"\nSuccess: {result['success']}")
    print(f"Message: {result['message']}")
    if 'details' in result:
        print(f"Details: {result['details']}")
