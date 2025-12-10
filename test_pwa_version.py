"""
Test script to demonstrate PWA version synchronization.

This script simulates what happens when the server version changes:
1. Shows current version
2. Allows you to change it
3. Shows how PWA will detect the change
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wimm_project.settings')
django.setup()

from finances.models import SystemVersion


def main():
    print("=" * 60)
    print("PWA Version Synchronization Test")
    print("=" * 60)
    print()

    # Get current version
    current_version = SystemVersion.get_current_version()
    print(f"📌 Current server version: {current_version}")
    print()

    print("When you change the version:")
    print("  1. manifest.json will return the new version")
    print("  2. serviceworker.js will use new cache name")
    print("  3. Installed PWA will show update notification")
    print("  4. User will be prompted to reinstall")
    print()

    print("Test URLs:")
    print(f"  - http://localhost:8000/manifest.json")
    print(f"  - http://localhost:8000/serviceworker.js")
    print()

    # Simulate version change
    response = input("Do you want to test version change? (y/n): ")
    if response.lower() == 'y':
        new_version = input("Enter new version (e.g., 1.4.3): ")

        # Update version in database
        version_obj = SystemVersion.objects.first()
        if version_obj:
            version_obj.version = new_version
            version_obj.save()
            print(f"✅ Version updated to {new_version}")
            print()
            print("Now:")
            print("  1. Reload the PWA app")
            print("  2. Check console for '[PWA] Version mismatch!' message")
            print("  3. You should see update notification modal")
        else:
            print("❌ No SystemVersion found in database")
    else:
        print("Test cancelled")

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
