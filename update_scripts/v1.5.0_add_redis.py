#!/usr/bin/env python3
"""
Update script for SweetMoney v1.5.0 - Add Redis and WebSocket Support

This script:
1. Installs Redis/WebSocket dependencies (channels, channels-redis, daphne, supervisor)
2. Updates SystemVersion to 1.5.0
3. No database migrations needed (no model changes)
4. Container restart required for supervisor and Redis integration

Execution: This script runs during the update process via update_manager.py
"""

import os
import sys
import subprocess
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wimm_project.settings')
django.setup()

from finances.models import SystemVersion


def log(message):
    """Print log message with prefix"""
    print(f"[Update v1.5.0] {message}")


def check_docker_environment():
    """Detect if running in Docker environment"""
    return os.path.exists('/.dockerenv')


def install_dependencies():
    """Install required Python packages"""
    log("Installing Redis and WebSocket dependencies...")

    # Determine correct pip command based on environment
    is_docker = check_docker_environment()
    pip_cmd = 'pip' if is_docker else sys.executable

    if pip_cmd == 'pip':
        # Docker environment
        install_cmd = ['pip', 'install', 'channels>=4.0.0', 'channels-redis>=4.1.0', 'daphne>=4.0.0', 'supervisor']
    else:
        # Local development environment
        install_cmd = [pip_cmd, '-m', 'pip', 'install', 'channels>=4.0.0', 'channels-redis>=4.1.0', 'daphne>=4.0.0', 'supervisor']

    log(f"Using pip command: {' '.join(install_cmd)}")

    try:
        # Install dependencies with timeout
        result = subprocess.run(
            install_cmd,
            capture_output=True,
            text=True,
            timeout=180  # 3 minute timeout
        )

        if result.returncode == 0:
            log("Dependencies installed successfully!")
            if result.stdout:
                log(f"Install output: {result.stdout[:500]}")  # Show first 500 chars
            return True
        else:
            log(f"Failed to install dependencies. Return code: {result.returncode}")
            if result.stderr:
                log(f"Error: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        log("Dependency installation timed out after 3 minutes")
        return False
    except Exception as e:
        log(f"Error installing dependencies: {str(e)}")
        return False


def update_system_version():
    """Update system version to 1.5.0"""
    log("Updating system version to 1.5.0...")

    try:
        version, created = SystemVersion.objects.get_or_create(id=1)
        version.version = '1.5.0'
        version.save()

        log("System version updated successfully!")
        return True

    except Exception as e:
        log(f"Error updating system version: {str(e)}")
        return False


def check_redis_configuration():
    """Check if Redis configuration is present in settings"""
    log("Checking Redis configuration...")

    try:
        from django.conf import settings

        # Check if CHANNEL_LAYERS is configured
        if hasattr(settings, 'CHANNEL_LAYERS'):
            log("CHANNEL_LAYERS configuration found")

            # Check if ASGI_APPLICATION is set
            if hasattr(settings, 'ASGI_APPLICATION'):
                log(f"ASGI_APPLICATION set to: {settings.ASGI_APPLICATION}")
                return True
            else:
                log("Warning: ASGI_APPLICATION not configured")
                return False
        else:
            log("Warning: CHANNEL_LAYERS not configured")
            return False

    except Exception as e:
        log(f"Error checking configuration: {str(e)}")
        return False


def main():
    """Main update process"""
    log("Starting update to v1.5.0 (Redis + WebSocket Support)")

    success = True

    # Step 1: Install dependencies
    if not install_dependencies():
        log("Warning: Dependency installation failed. Continue with caution.")
        success = False

    # Step 2: Update system version
    if not update_system_version():
        log("Error: Failed to update system version")
        return False

    # Step 3: Check configuration
    if not check_redis_configuration():
        log("Warning: Redis configuration may be incomplete")

    # Final message
    if success:
        log("")
        log("=" * 70)
        log("Update to v1.5.0 completed successfully!")
        log("")
        log("IMPORTANT NOTES:")
        log("1. Container restart REQUIRED for changes to take effect")
        log("2. Redis service will start automatically with docker-compose")
        log("3. Supervisor will manage Gunicorn, Daphne, and Update Monitor")
        log("4. WebSocket connections available at ws://host:8001/ws/updates/")
        log("5. HTTP still available at port 8000")
        log("")
        log("Next steps:")
        log("- Update docker-compose.yml with Redis service (if not done)")
        log("- Restart container: docker-compose restart")
        log("- Check logs: docker logs sweetmoney")
        log("- Test WebSocket: Open browser console and check for connection")
        log("=" * 70)
        return True
    else:
        log("")
        log("Update completed with warnings. Please check logs above.")
        return True  # Don't block update even if there were warnings


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
