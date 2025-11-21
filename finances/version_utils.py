# finances/version_utils.py

import re
from typing import Tuple, Optional

# Testing flags
FORCE_UPDATE_FOR_TESTING = False  # Set to True to force update notifications even for equal versions
SKIP_LOCAL_UPDATE = False  # Set to True to skip local update checks and go directly to GitHub
FORCE_CONTAINER_UPDATE_SKIP = False  # Set to True to force web updates even when container update would be required

"""
Testing flags usage:

1. FORCE_UPDATE_FOR_TESTING = True
   - Forces update notification even if versions are equal
   - Useful for testing the update flow without changing versions
   - Example: Test with 1.0.0-alpha5 == 1.0.0-alpha5

2. SKIP_LOCAL_UPDATE = True
   - Skips local update verification completely
   - Goes directly to GitHub update check
   - Useful for testing GitHub updates without applying local updates first
   - Example: Test GitHub update flow even if local scripts are pending

3. FORCE_CONTAINER_UPDATE_SKIP = True
   - Forces web-based updates even when container update would normally be required
   - Bypasses the need_container_update.txt check from GitHub
   - DANGEROUS: Use only for testing! May cause issues if update truly requires container rebuild
   - Example: Test update flow on old versions without rebuilding container

IMPORTANT: All flags should be False in production!
"""


class Version:
    """
    Semantic version parser and comparator.
    Supports: major.minor.patch[-alpha/-beta][number]
    Examples: 1.0.0, 1.0.0-alpha1, 2.1.3-beta5
    
    Version comparison is case-insensitive for pre-release identifiers.
    """
    
    def __init__(self, version_string: str):
        self.original = version_string
        self.major, self.minor, self.patch, self.pre_release, self.pre_release_num = self._parse(version_string)
    
    @staticmethod
    def _parse(version_string: str) -> Tuple[int, int, int, Optional[str], Optional[int]]:
        """
        Parses a version string into components.
        Case-insensitive for pre-release identifiers (alpha/beta).
        """
        # Pattern: major.minor.patch[-alpha/-beta][number]
        # (?i) makes the pattern case-insensitive for alpha/beta
        pattern = r'^(\d+)\.(\d+)\.(\d+)(?:-((?i:alpha|beta))(\d+)?)?$'
        match = re.match(pattern, version_string.strip())
        
        if not match:
            raise ValueError(f"Invalid version format: {version_string}")
        
        major = int(match.group(1))
        minor = int(match.group(2))
        patch = int(match.group(3))
        pre_release = match.group(4).lower() if match.group(4) else None  # Convert to lowercase
        pre_release_num = int(match.group(5)) if match.group(5) else None
        
        return major, minor, patch, pre_release, pre_release_num
    
    def __lt__(self, other: 'Version') -> bool:
        """Less than comparison."""
        # Compare major.minor.patch first
        if (self.major, self.minor, self.patch) != (other.major, other.minor, other.patch):
            return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)
        
        # Same base version, compare pre-release
        # No pre-release (release) > any pre-release
        if self.pre_release is None and other.pre_release is None:
            return False  # Equal
        if self.pre_release is None:
            return False  # self is release, other is pre-release -> self is greater
        if other.pre_release is None:
            return True  # self is pre-release, other is release -> self is less
        
        # Both have pre-release: alpha < beta
        pre_release_order = {'alpha': 0, 'beta': 1}
        if self.pre_release != other.pre_release:
            return pre_release_order[self.pre_release] < pre_release_order[other.pre_release]
        
        # Same pre-release type, compare numbers
        self_num = self.pre_release_num or 0
        other_num = other.pre_release_num or 0
        return self_num < other_num
    
    def __le__(self, other: 'Version') -> bool:
        return self < other or self == other
    
    def __gt__(self, other: 'Version') -> bool:
        return not self <= other
    
    def __ge__(self, other: 'Version') -> bool:
        return not self < other
    
    def __eq__(self, other: 'Version') -> bool:
        return (self.major, self.minor, self.patch, self.pre_release, self.pre_release_num) == \
               (other.major, other.minor, other.patch, other.pre_release, other.pre_release_num)
    
    def __ne__(self, other: 'Version') -> bool:
        return not self == other
    
    def __str__(self) -> str:
        return self.original
    
    def __repr__(self) -> str:
        return f"Version('{self.original}')"


def compare_versions(version1: str, version2: str) -> int:
    """
    Compare two version strings (case-insensitive).
    
    Returns:
        -1 if version1 < version2
         0 if version1 == version2
         1 if version1 > version2
    """
    v1 = Version(version1)
    v2 = Version(version2)
    
    if v1 < v2:
        return -1
    elif v1 > v2:
        return 1
    else:
        return 0


def needs_update(current_version: str, target_version: str, force_for_testing: bool = None) -> bool:
    """
    Checks if an update is needed (case-insensitive).
    Only returns True if target version is GREATER than current version.
    Returns False if versions are equal (unless force_for_testing is True).
    
    Args:
        current_version: Current installed version
        target_version: Target/available version
        force_for_testing: Override to force update even if versions are equal.
                          If None, uses global FORCE_UPDATE_FOR_TESTING flag.
    
    Returns:
        True if current_version < target_version (or forced)
        False if current_version >= target_version
    """
    try:
        # Check force flag
        if force_for_testing is None:
            force_for_testing = FORCE_UPDATE_FOR_TESTING
        
        if force_for_testing:
            # In testing mode, always return True unless current is greater
            return Version(current_version) <= Version(target_version)
        
        # Normal mode: only update if target is greater
        return Version(current_version) < Version(target_version)
    except ValueError:
        # If version parsing fails, assume update is needed
        return True


def requires_container_update(current_version: str, target_version: str) -> bool:
    """
    Determines if the update requires a container rebuild.
    
    This function is now used as a fallback in github_utils.py.
    The actual container check is done by fetching need_container_update.txt from GitHub.
    
    Args:
        current_version: Current version string
        target_version: Target version string
    
    Returns:
        bool: True if container update is required
    """
    try:
        # Fallback minimum version that supports web updates
        min_web_update_version = Version("1.0.0-alpha4")
        current_ver = Version(current_version)
        
        # If current version is older than minimum, container update is required
        if current_ver < min_web_update_version:
            return True
        
        # All other updates can be done via web
        return False
        
    except ValueError:
        # If version parsing fails, assume container update is needed for safety
        return True


# Example usage and tests
if __name__ == "__main__":
    # Test cases
    test_cases = [
        ("1.0.0-alpha1", "1.0.0-alpha2", True),   # alpha1 < alpha2
        ("1.0.0-alpha2", "1.0.0-beta1", True),    # alpha < beta
        ("1.0.0-beta1", "1.0.0-beta2", True),     # beta1 < beta2
        ("1.0.0-beta2", "1.0.0", True),           # beta < release
        ("1.0.0", "1.0.1", True),                 # patch increment
        ("1.0.1", "1.1.0", True),                 # minor increment
        ("1.1.0", "2.0.0", True),                 # major increment
        ("2.0.0-beta1", "2.0.0", True),           # pre-release < release
        ("1.0.0", "1.0.0", False),                # equal
        ("2.0.0", "1.9.9", False),                # greater
        ("1.0.0-alpha5", "1.0.0-Alpha5", False),  # case insensitive - EQUAL
        ("1.0.0-ALPHA5", "1.0.0-alpha5", False),  # case insensitive - EQUAL
        ("1.0.0-Alpha5", "1.0.0-alpha6", True),   # case insensitive - less
    ]
    
    print("Version Comparison Tests:")
    print("-" * 50)
    for v1, v2, expected_less in test_cases:
        result = Version(v1) < Version(v2)
        status = "✓" if result == expected_less else "✗"
        print(f"{status} {v1} < {v2}: {result} (expected: {expected_less})")
    
    print("\n" + "=" * 50)
    print("Container Update Tests:")
    print("=" * 50)
    
    container_tests = [
        ("1.0.0-alpha1", "1.0.0-alpha5", True),   # Old version needs container
        ("1.0.0-alpha2", "1.0.0-alpha5", True),   # Old version needs container
        ("1.0.0-alpha3", "1.0.0-alpha5", True),   # Old version needs container
        ("1.0.0-alpha4", "1.0.0-alpha5", False),  # New version can web update
        ("1.0.0-alpha5", "1.0.0-alpha6", False),  # New version can web update
        ("1.0.0-beta1", "1.0.0", False),          # Beta can web update
        ("1.0.0", "1.1.0", False),                # Release can web update
    ]
    
    for current, target, expected_container in container_tests:
        result = requires_container_update(current, target)
        status = "✓" if result == expected_container else "✗"
        print(f"{status} {current} → {target}: Container={result} (expected: {expected_container})")
    
    print("\n" + "=" * 50)
    print("Force Testing Mode:")
    print("=" * 50)
    print(f"FORCE_UPDATE_FOR_TESTING = {FORCE_UPDATE_FOR_TESTING}")
    print(f"SKIP_LOCAL_UPDATE = {SKIP_LOCAL_UPDATE}")
    print("\nWith force=False (normal):")
    print(f"  1.0.0-alpha5 needs update to 1.0.0-alpha5? {needs_update('1.0.0-alpha5', '1.0.0-alpha5', force_for_testing=False)}")
    print("\nWith force=True (testing):")
    print(f"  1.0.0-alpha5 needs update to 1.0.0-alpha5? {needs_update('1.0.0-alpha5', '1.0.0-alpha5', force_for_testing=True)}")