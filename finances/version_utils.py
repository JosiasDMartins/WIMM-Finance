# finances/version_utils.py

import re
from typing import Tuple, Optional


class Version:
    """
    Parses and compares semantic versions with alpha/beta support.
    
    Examples:
        1.0.0
        1.0.1
        1.1.1
        2.0.0
        1.0.0-alpha1
        1.0.0-alpha2
        1.0.0-beta1
        1.0.0-beta2
    
    Comparison rules:
        - alpha1 < alpha2
        - alpha2 < beta1
        - beta1 < beta2
        - beta2 < 1.0.0 (release)
        - 2.0.0-beta1 < 2.0.0
    """
    
    def __init__(self, version_string: str):
        self.original = version_string
        self.major, self.minor, self.patch, self.pre_release, self.pre_release_num = self._parse(version_string)
    
    def _parse(self, version_string: str) -> Tuple[int, int, int, Optional[str], Optional[int]]:
        """
        Parses version string into components.
        
        Returns:
            (major, minor, patch, pre_release_type, pre_release_number)
        """
        # Pattern: major.minor.patch[-alpha/beta][number]
        pattern = r'^(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta)(\d+)?)?$'
        match = re.match(pattern, version_string.strip())
        
        if not match:
            raise ValueError(f"Invalid version format: {version_string}")
        
        major = int(match.group(1))
        minor = int(match.group(2))
        patch = int(match.group(3))
        pre_release = match.group(4)  # 'alpha' or 'beta' or None
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
    Compare two version strings.
    
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


def needs_update(current_version: str, target_version: str) -> bool:
    """
    Checks if an update is needed.
    
    Returns:
        True if current_version < target_version
    """
    try:
        return Version(current_version) < Version(target_version)
    except ValueError:
        # If version parsing fails, assume update is needed
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
    ]
    
    print("Version Comparison Tests:")
    print("-" * 50)
    for v1, v2, expected_less in test_cases:
        result = Version(v1) < Version(v2)
        status = "✓" if result == expected_less else "✗"
        print(f"{status} {v1} < {v2}: {result} (expected: {expected_less})")
