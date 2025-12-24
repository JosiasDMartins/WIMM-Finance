#!/usr/bin/env python3
"""
Update script for SweetMoney v1.5.0 - Add Redis and WebSocket Support

This script:
1. Updates SystemVersion to 1.5.0
2. No database migrations needed (no model changes)
3. No dependency installation (already in container)

Execution: This script runs during the update process via update_manager.py
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wimm_project.settings')
django.setup()

from finances.models import SystemVersion


def log(message):
    """Print log message with prefix"""
    print(f"[Update v1.5.0] {message}")


def run():
    """
    Main update process - called by the update manager
    This function is required by the update system
    """
    log("Starting update to v1.5.0 (Redis + WebSocket Support)")

    try:
        # Update system version to 1.5.0
        version, created = SystemVersion.objects.get_or_create(id=1)
        version.version = '1.5.0'
        version.save()

        log("System version updated successfully to 1.5.0!")
        log("")
        log("=" * 70)
        log("Update to v1.5.0 completed successfully!")
        log("")
        log("IMPORTANT NOTES:")
        log("1. All dependencies are included in the container")
        log("2. Redis integration is active (falls back to InMemory if unavailable)")
        log("3. WebSocket connections available at ws://host:8000/ws/updates/")
        log("4. Daphne handles both HTTP and WebSocket on port 8000")
        log("")
        log("Changes in v1.5.0:")
        log("- Redis channel layer for WebSocket (with automatic fallback)")
        log("- Unified Daphne ASGI server (single port for HTTP + WebSocket)")
        log("- Enhanced real-time updates")
        log("- Security improvements (CSP, logging)")
        log("=" * 70)

        return True

    except Exception as e:
        log(f"Error updating system version: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Legacy main function for standalone execution"""
    return run()


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
