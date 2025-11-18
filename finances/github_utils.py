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
            # Read version from file (trim whitespace and newlines)
            version = response.text.strip()
            
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
    
    Args:
        current_version: Current version string
        target_version: Target version string (not used, kept for compatibility)
    
    Returns:
        bool: True if container update is required
    """
    try:
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


def download_and_extract_release(zipball_url: str) -> Tuple[bool, str]:
    """
    Downloads and extracts a GitHub release zipball to the project directory.
    
    Args:
        zipball_url: URL to the zipball archive
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        base_dir = Path(settings.BASE_DIR)
        temp_dir = base_dir / 'temp_update'
        temp_zip = base_dir / 'temp_release.zip'
        
        # Create temp directory if it doesn't exist
        temp_dir.mkdir(exist_ok=True)
        
        # Download the zipball
        print(f"Downloading release from: {zipball_url}")
        response = requests.get(zipball_url, stream=True, timeout=30)
        
        if response.status_code != 200:
            return False, f"Failed to download release. Status code: {response.status_code}"
        
        # Save to temp file
        with open(temp_zip, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print("Download complete. Extracting...")
        
        # Extract zipball
        with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Find the extracted directory (GitHub creates a directory with repo name + commit hash)
        extracted_dirs = [d for d in temp_dir.iterdir() if d.is_dir()]
        
        if not extracted_dirs:
            return False, "No directory found in extracted archive"
        
        extracted_dir = extracted_dirs[0]
        
        # Copy files from extracted directory to project root
        # Skip: .git, __pycache__, *.pyc, db.sqlite3, .env, backups, temp_*
        skip_patterns = {'.git', '__pycache__', 'db.sqlite3', '.env', 'backups', 'venv', 'env'}
        
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
                print(f"Updated: {rel_path}")
        
        # Cleanup
        shutil.rmtree(temp_dir)
        temp_zip.unlink()
        
        return True, "Release files updated successfully"
        
    except Exception as e:
        # Cleanup on error
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        if temp_zip.exists():
            temp_zip.unlink()
        
        return False, f"Error during update: {str(e)}"


def create_database_backup():
    """
    Creates a backup of the database.
    
    Returns:
        Tuple of (success: bool, backup_path: str or error_message: str)
    """
    try:
        from django.conf import settings
        import shutil
        from datetime import datetime
        
        # Create backups directory if it doesn't exist
        backups_dir = Path(settings.BASE_DIR) / 'backups'
        backups_dir.mkdir(exist_ok=True)
        
        # Source database file
        db_path = Path(settings.DATABASES['default']['NAME'])
        
        if not db_path.exists():
            return False, "Database file not found"
        
        # Create backup filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'db_backup_{timestamp}.sqlite3'
        backup_path = backups_dir / backup_filename
        
        # Copy database file
        shutil.copy2(db_path, backup_path)
        
        print(f"Database backup created: {backup_path}")
        return True, str(backup_filename)
        
    except Exception as e:
        print(f"Error creating backup: {str(e)}")
        return False, str(e)