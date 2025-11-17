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
    
    Container updates are needed when:
    - Major version changes (1.x.x -> 2.x.x)
    - Dependencies change (requirements.txt modified)
    - System-level changes indicated in release notes
    
    Args:
        current_version: Current version string
        target_version: Target version string
    
    Returns:
        bool: True if container update is required
    """
    try:
        current_ver = Version(current_version)
        target_ver = Version(target_version)
        
        # Check for major version change
        if target_ver.major > current_ver.major:
            return True
        
        # For now, assume no container update needed for minor/patch updates
        # In the future, could check release notes for keywords like "container" or "docker"
        return False
        
    except ValueError:
        # If version parsing fails, assume container update is needed for safety
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
    Returns: (success: bool, message: str, backup_path: Path or None)
    """
    from pathlib import Path
    import shutil
    from datetime import datetime
    from django.conf import settings
    
    try:
        # Pega o caminho correto do banco de dados do Django settings
        db_path = Path(settings.DATABASES['default']['NAME'])
        
        if not db_path.exists():
            return False, "Database file not found", None
        
        # Cria diretório de backups se não existir
        backup_dir = Path(settings.BASE_DIR) / 'backups'
        backup_dir.mkdir(exist_ok=True)
        
        # Nome do arquivo de backup com timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'db_backup_{timestamp}.sqlite3'
        backup_path = backup_dir / backup_filename
        
        # Copia o banco de dados
        shutil.copy2(db_path, backup_path)
        
        return True, f"Backup created successfully: {backup_filename}", backup_path
        
    except Exception as e:
        return False, f"Failed to create backup: {str(e)}", None


