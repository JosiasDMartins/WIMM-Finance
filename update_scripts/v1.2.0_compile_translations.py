"""
Update Script: Compile Django i18n Translations
Version: 1.2.0
Description: Compiles translation files (.po to .mo) for multi-language support

This script:
1. Runs Django migrations (if any)
2. Compiles all translation files using Django's compilemessages command
3. Verifies that .mo files were created successfully
"""

from django.core.management import call_command
from pathlib import Path
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
        print("[Update v1.2.0] Starting i18n translations compilation...")

        # =====================================================
        # STEP 1: Run Django migrations
        # =====================================================
        print("[Update v1.2.0] Step 1: Running Django migrations...")
        try:
            call_command('migrate', verbosity=1)
            print("[Update v1.2.0] Migrations completed successfully")
        except Exception as migrate_error:
            error_msg = f"Migration failed: {str(migrate_error)}"
            print(f"[ERROR] {error_msg}", file=sys.stderr)
            return {
                'success': False,
                'message': error_msg,
                'error': str(migrate_error)
            }

        # =====================================================
        # STEP 2: Compile translation files
        # =====================================================
        print("[Update v1.2.0] Step 2: Compiling translation files...")

        try:
            # Run compilemessages command
            call_command('compilemessages', verbosity=1)
            print("[Update v1.2.0] Translation files compiled successfully")
        except Exception as compile_error:
            error_msg = f"Translation compilation failed: {str(compile_error)}"
            print(f"[ERROR] {error_msg}", file=sys.stderr)
            return {
                'success': False,
                'message': error_msg,
                'error': str(compile_error)
            }

        # =====================================================
        # STEP 3: Verify compiled files
        # =====================================================
        print("[Update v1.2.0] Step 3: Verifying compiled translation files...")

        from django.conf import settings

        results = {
            'compiled_languages': [],
            'missing_files': []
        }

        # Check for compiled .mo files
        locale_paths = getattr(settings, 'LOCALE_PATHS', [])
        languages = getattr(settings, 'LANGUAGES', [])

        for locale_path in locale_paths:
            locale_path = Path(locale_path)
            for lang_code, lang_name in languages:
                mo_file = locale_path / lang_code / 'LC_MESSAGES' / 'django.mo'
                if mo_file.exists():
                    results['compiled_languages'].append(f"{lang_name} ({lang_code})")
                    print(f"[Update v1.2.0] ✓ Found compiled file: {mo_file}")
                else:
                    # Not an error for 'en' as it's the default language
                    if lang_code != 'en':
                        results['missing_files'].append(f"{lang_name} ({lang_code})")
                        print(f"[Update v1.2.0] ⚠ Missing compiled file: {mo_file}")

        # Build result message
        if results['compiled_languages']:
            message = f"Successfully compiled translations for: {', '.join(results['compiled_languages'])}"
        else:
            message = "No translation files were compiled (English is the default language)"

        if results['missing_files']:
            message += f" | Missing: {', '.join(results['missing_files'])}"

        print(f"[Update v1.2.0] {message}")
        print("[Update v1.2.0] i18n setup completed successfully!")
        print("[Update v1.2.0] Users can now select their preferred language in Settings → Configuration")

        return {
            'success': True,
            'message': message,
            'details': results
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'message': f"Translation compilation failed: {str(e)}",
            'error': str(e)
        }


# For testing purposes
if __name__ == "__main__":
    import os
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
