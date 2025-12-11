"""
Utility functions for Docker container integration.
Handles flag creation for hot-reload system.
"""
import os
from pathlib import Path


FLAGS_DIR = Path("/app/flags")


def is_running_in_docker():
    """Check if the application is running inside a Docker container."""
    return os.path.exists('/.dockerenv') or os.path.isfile('/app/config/local_settings.py')


def create_reload_flag():
    """
    Create a flag file to signal Daphne reload.
    The update_monitor daemon will detect this and send SIGHUP to Daphne.
    """
    if not is_running_in_docker():
        return False

    try:
        FLAGS_DIR.mkdir(parents=True, exist_ok=True)
        flag_file = FLAGS_DIR / "reload.flag"
        flag_file.touch()
        print(f"[DOCKER_UTILS] Created reload flag: {flag_file}")
        return True
    except Exception as e:
        print(f"[DOCKER_UTILS] Error creating reload flag: {e}")
        return False


def create_requirements_flag():
    """
    Create a flag file to signal requirements installation.
    The update_monitor daemon will run pip install.
    """
    if not is_running_in_docker():
        return False

    try:
        FLAGS_DIR.mkdir(parents=True, exist_ok=True)
        flag_file = FLAGS_DIR / "requirements.flag"
        flag_file.touch()
        print(f"[DOCKER_UTILS] Created requirements flag: {flag_file}")
        return True
    except Exception as e:
        print(f"[DOCKER_UTILS] Error creating requirements flag: {e}")
        return False


def create_migrate_flag():
    """
    Create a flag file to signal database migrations.
    The update_monitor daemon will run manage.py migrate.
    """
    if not is_running_in_docker():
        return False

    try:
        FLAGS_DIR.mkdir(parents=True, exist_ok=True)
        flag_file = FLAGS_DIR / "migrate.flag"
        flag_file.touch()
        print(f"[DOCKER_UTILS] Created migrate flag: {flag_file}")
        return True
    except Exception as e:
        print(f"[DOCKER_UTILS] Error creating migrate flag: {e}")
        return False
