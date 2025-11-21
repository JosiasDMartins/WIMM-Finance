# finances/github_utils.py

import requests
import zipfile
import shutil
import os
from pathlib import Path
from typing import Optional, Dict, Tuple
from django.conf import settings
from datetime import datetime

from .version_utils import Version, needs_update

# GitHub repository configuration
GITHUB_OWNER = "JosiasDMartins"
GITHUB_REPO = "SweetMoney"
GITHUB_RELEASES_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases"
GITHUB_RAW_CONTENT_URL = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/main"

# Cache for container update version (to avoid multiple GitHub requests)
_cached_container_version = None


def get_latest_github_release() -> Optional[Dict]:
    """
    Fetches the latest release from GitHub.
    Since /latest endpoint doesn't exist, fetch all releases and get the first one.
    
    Returns:
        Dict with release info or None if failed
    """
    try:
        print(f"Fetching releases from: {GITHUB_RELEASES_URL}")
        response = requests.get(GITHUB_RELEASES_URL, timeout=10)
        
        if response.status_code == 200:
            releases = response.json()
            
            # Check if we got any releases
            if releases and len(releases) > 0:
                # The first release in the list is the most recent
                latest_release = releases[0]
                print(f"Latest release found: {latest_release.get('tag_name', 'unknown')}")
                return latest_release
            else:
                print("No releases found in repository")
                return None
        else:
            print(f"Failed to fetch releases. Status code: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"Error fetching GitHub releases: {str(e)}")
        return None


def get_min_container_version_from_github() -> Optional[str]:
    """
    Fetches the minimum version that requires container update from GitHub.
    Reads the need_container_update.txt file from the main branch.

    Returns:
        Version string (e.g., "1.0.0-alpha4") or None if failed
    """
    global _cached_container_version

    # Return cached version if available
    if _cached_container_version is not None:
        return _cached_container_version

    try:
        url = f"{GITHUB_RAW_CONTENT_URL}/need_container_update.txt"
        print(f"Fetching container version requirement from: {url}")

        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            # Read version from file (trim whitespace, newlines, and 'v' prefix)
            version = response.text.strip().lstrip('v')

            if version:
                print(f"Container update required for versions < {version}")
                _cached_container_version = version
                return version
            else:
                print("Empty version in need_container_update.txt")
                return None
        else:
            print(f"Failed to fetch need_container_update.txt. Status: {response.status_code}")
            return None

    except Exception as e:
        print(f"Error fetching container version requirement: {str(e)}")
        return None


def check_github_update(current_version: str) -> Tuple[bool, Optional[Dict]]:
    """
    Checks if a newer version is available on GitHub.
    
    Args:
        current_version: Current version string (e.g., "1.0.0-alpha3")
    
    Returns:
        Tuple of (has_update: bool, release_info: dict or None)
    """
    try:
        release = get_latest_github_release()
        
        if not release:
            return False, None
        
        # Extract version from tag_name (remove 'v' prefix if present)
        tag_name = release.get('tag_name', '')
        github_version = tag_name.lstrip('v')
        
        if not github_version:
            return False, None
        
        # Compare versions
        try:
            has_update = needs_update(current_version, github_version)
        except ValueError:
            # If version comparison fails, assume update is available
            has_update = True
    
        if has_update:
            # Format release info
            release_info = {
                'version': github_version,
                'tag_name': tag_name,
                'name': release.get('name', tag_name),
                'body': release.get('body', ''),
                'html_url': release.get('html_url', ''),
                'published_at': release.get('published_at', ''),
                'zipball_url': release.get('zipball_url', ''),
                'tarball_url': release.get('tarball_url', ''),
            }
            return True, release_info
        
        return False, None
        
    except Exception as e:
        print(f"Error checking GitHub update: {str(e)}")
        return False, None


def requires_container_update(current_version: str, target_version: str) -> bool:
    """
    Determines if the update requires a container rebuild.

    Checks the need_container_update.txt file on GitHub to get the minimum version
    that supports web updates. If current version is below this minimum, container
    update is required.

    Can be bypassed for testing using FORCE_CONTAINER_UPDATE_SKIP flag.

    Args:
        current_version: Current version string
        target_version: Target version string (not used, kept for compatibility)

    Returns:
        bool: True if container update is required
    """
    try:
        # Check if testing flag is enabled
        from .version_utils import FORCE_CONTAINER_UPDATE_SKIP

        if FORCE_CONTAINER_UPDATE_SKIP:
            print(f"[TESTING] FORCE_CONTAINER_UPDATE_SKIP is enabled - allowing web update")
            return False

        # Get minimum version from GitHub
        min_web_update_version_str = get_min_container_version_from_github()

        if min_web_update_version_str:
            # Parse versions
            current_ver = Version(current_version)
            min_web_update_version = Version(min_web_update_version_str)

            # If current version is older than minimum, container update is required
            if current_ver < min_web_update_version:
                print(f"Container update required: {current_version} < {min_web_update_version_str}")
                return True
            else:
                print(f"Web update OK: {current_version} >= {min_web_update_version_str}")
                return False
        else:
            # If we can't fetch the file, use fallback version
            print("Could not fetch container version requirement, using fallback")
            fallback_version = Version("1.0.0-alpha4")
            current_ver = Version(current_version)

            if current_ver < fallback_version:
                return True
            return False

    except ValueError as e:
        # If version parsing fails, assume container update is needed for safety
        print(f"Version parsing error: {e}")
        return True
    except Exception as e:
        # Any other error, assume container update is needed for safety
        print(f"Error checking container update requirement: {e}")
        return True


def download_and_extract_release(zipball_url: str) -> Tuple[bool, str, list]:
    """
    Downloads and extracts a GitHub release zipball to the project directory.

    Args:
        zipball_url: URL to the zipball archive

    Returns:
        Tuple of (success: bool, message: str, logs: list)
    """
    temp_dir = None
    temp_zip = None
    logs = []  # Capture all logs for frontend

    try:
        base_dir = Path(settings.BASE_DIR)
        temp_dir = base_dir / 'temp_update'
        temp_zip = base_dir / 'temp_release.zip'

        logs.append(f"Starting download from: {zipball_url}")
        logs.append(f"Base directory: {base_dir}")
        logs.append(f"Temp directory: {temp_dir}")
        print(f"[UPDATE] Starting download from: {zipball_url}")
        print(f"[UPDATE] Base directory: {base_dir}")
        print(f"[UPDATE] Temp directory: {temp_dir}")

        # Create temp directory if it doesn't exist
        temp_dir.mkdir(exist_ok=True)
        logs.append(f"Temp directory created/verified")
        print(f"[UPDATE] Temp directory created/verified")

        # Download the zipball
        logs.append(f"Downloading release...")
        print(f"[UPDATE] Downloading release...")
        response = requests.get(zipball_url, stream=True, timeout=60)

        logs.append(f"Response status: {response.status_code}")
        print(f"[UPDATE] Response status: {response.status_code}")
        if response.status_code != 200:
            error_msg = f"Failed to download release. Status code: {response.status_code}"
            logs.append(f"ERROR: {error_msg}")
            print(f"[UPDATE ERROR] {error_msg}")
            return False, error_msg, logs

        # Save to temp file
        logs.append(f"Saving to: {temp_zip}")
        print(f"[UPDATE] Saving to: {temp_zip}")
        total_size = 0
        with open(temp_zip, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                total_size += len(chunk)

        logs.append(f"Download complete. Size: {total_size} bytes")
        print(f"[UPDATE] Download complete. Size: {total_size} bytes")

        # Verify zip file
        if not temp_zip.exists():
            error_msg = "Downloaded file not found"
            logs.append(f"ERROR: {error_msg}")
            return False, error_msg, logs

        logs.append(f"Extracting archive...")
        print(f"[UPDATE] Extracting archive...")

        # Extract zipball
        try:
            with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            logs.append(f"Extraction complete")
            print(f"[UPDATE] Extraction complete")
        except zipfile.BadZipFile as e:
            error_msg = f"Downloaded file is not a valid ZIP archive: {str(e)}"
            logs.append(f"ERROR: Bad zip file: {e}")
            print(f"[UPDATE ERROR] Bad zip file: {e}")
            return False, error_msg, logs

        # Find the extracted directory (GitHub creates a directory with repo name + commit hash)
        extracted_dirs = [d for d in temp_dir.iterdir() if d.is_dir()]
        logs.append(f"Found {len(extracted_dirs)} directories in extracted archive")
        print(f"[UPDATE] Found {len(extracted_dirs)} directories in extracted archive")

        if not extracted_dirs:
            error_msg = "No directory found in extracted archive"
            logs.append(f"ERROR: {error_msg}")
            return False, error_msg, logs

        extracted_dir = extracted_dirs[0]
        logs.append(f"Using extracted directory: {extracted_dir.name}")
        print(f"[UPDATE] Using extracted directory: {extracted_dir.name}")

        # Copy files from extracted directory to project root
        # Skip: .git, __pycache__, *.pyc, db.sqlite3, .env, backups, temp_*
        skip_patterns = {'.git', '__pycache__', 'db.sqlite3', '.env', 'backups', 'venv', 'env'}

        files_updated = 0
        logs.append(f"Starting file copy...")
        print(f"[UPDATE] Starting file copy...")

        for item in extracted_dir.rglob('*'):
            # Skip if matches skip patterns
            if any(pattern in item.parts for pattern in skip_patterns):
                continue

            # Skip .pyc files
            if item.suffix == '.pyc':
                continue

            # Calculate relative path
            rel_path = item.relative_to(extracted_dir)
            dest_path = base_dir / rel_path

            if item.is_file():
                # Create parent directories if they don't exist
                dest_path.parent.mkdir(parents=True, exist_ok=True)

                # Copy file
                shutil.copy2(item, dest_path)
                files_updated += 1
                if files_updated <= 10:  # Print first 10 files
                    logs.append(f"Updated: {rel_path}")
                    print(f"[UPDATE] Updated: {rel_path}")

        logs.append(f"Total files updated: {files_updated}")
        print(f"[UPDATE] Total files updated: {files_updated}")

        # Cleanup
        logs.append(f"Cleaning up temporary files...")
        print(f"[UPDATE] Cleaning up temporary files...")
        shutil.rmtree(temp_dir)
        temp_zip.unlink()

        logs.append(f"Update completed successfully!")
        print(f"[UPDATE] Update completed successfully")
        return True, f"Release files updated successfully ({files_updated} files)", logs

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logs.append(f"ERROR: Exception occurred: {str(e)}")
        logs.append(f"Traceback:\n{error_trace}")
        print(f"[UPDATE ERROR] Exception occurred: {str(e)}")
        print(f"[UPDATE ERROR] Traceback:\n{error_trace}")

        # Cleanup on error
        try:
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            if temp_zip and temp_zip.exists():
                temp_zip.unlink()
            logs.append(f"Cleanup completed after error")
        except Exception as cleanup_error:
            logs.append(f"ERROR: Cleanup failed: {cleanup_error}")
            print(f"[UPDATE ERROR] Cleanup failed: {cleanup_error}")

        return False, f"Error during update: {str(e)}", logs


def create_database_backup():
    """
    Creates a backup of the database.

    Returns:
        Tuple of (success: bool, message: str, backup_path: Path or None)
    """
    try:
        from django.conf import settings
        import shutil
        from datetime import datetime

        # Create backups directory if it doesn't exist
        backups_dir = Path(settings.BASE_DIR) / 'backups'
        backups_dir.mkdir(exist_ok=True)

        # Source database file - ensure absolute path
        db_name = settings.DATABASES['default']['NAME']
        db_path = Path(db_name)

        # If path is not absolute, make it relative to BASE_DIR
        if not db_path.is_absolute():
            db_path = Path(settings.BASE_DIR) / db_path

        print(f"Attempting to backup database from: {db_path}")
        print(f"Database path exists: {db_path.exists()}")
        print(f"Database path is absolute: {db_path.is_absolute()}")

        if not db_path.exists():
            error_msg = f"Database file not found at: {db_path}"
            print(error_msg)
            return False, error_msg, None

        # Create backup filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'db_backup_{timestamp}.sqlite3'
        backup_path = backups_dir / backup_filename

        # Copy database file
        shutil.copy2(db_path, backup_path)

        print(f"Database backup created: {backup_path}")
        return True, "Backup created successfully", backup_path

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"Error creating backup: {str(e)}")
        print(f"Traceback: {error_detail}")
        return False, str(e), None