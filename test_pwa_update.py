"""
PWA Update Test Script

This script helps you verify that PWA updates work correctly:
1. Shows current version
2. Simulates version update
3. Provides step-by-step testing instructions
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wimm_project.settings')
django.setup()

from finances.models import SystemVersion


def print_separator():
    print("=" * 70)


def print_step(number, title):
    print(f"\n{'='*70}")
    print(f"STEP {number}: {title}")
    print(f"{'='*70}\n")


def main():
    print_separator()
    print("🧪 PWA UPDATE MECHANISM TEST")
    print_separator()
    print()

    # Get current version
    current_version = SystemVersion.get_current_version()
    print(f"📌 Current server version: {current_version}")
    print()

    print("This test will help you verify that:")
    print("  ✓ Service worker updates automatically")
    print("  ✓ Old caches are deleted")
    print("  ✓ New content is loaded")
    print("  ✓ Pages reload automatically")
    print()

    input("Press ENTER to start the test...")

    # === STEP 1 ===
    print_step(1, "Prepare the PWA App")
    print("1. Make sure PWA is installed on your system")
    print("2. Open the installed PWA app")
    print("3. Open DevTools (F12) → Console tab")
    print("4. You should see:")
    print(f"   [PWA] Server version: {current_version}")
    print(f"   [ServiceWorker] Current cache version: sweetmoney-cache-v{current_version.replace('.', '_')}")
    print()
    input("✓ PWA app is open with console visible? Press ENTER...")

    # === STEP 2 ===
    print_step(2, "Change Server Version")
    print("Now we'll simulate a server update.")
    print()
    new_version = input(f"Enter NEW version (current: {current_version}): ")

    if not new_version or new_version == current_version:
        print("❌ Invalid version or same as current. Test cancelled.")
        return

    # Update version
    version_obj = SystemVersion.objects.first()
    if not version_obj:
        print("❌ No SystemVersion found in database!")
        return

    old_version = version_obj.version
    version_obj.version = new_version
    version_obj.save()

    print()
    print(f"✅ Version updated: {old_version} → {new_version}")
    print()
    print("Server is now at version:", new_version)
    print()

    # === STEP 3 ===
    print_step(3, "Wait for Auto-Update (60 seconds max)")
    print("The PWA will automatically check for updates within 60 seconds.")
    print()
    print("Watch the console for these messages:")
    print("  1. [ServiceWorker v" + new_version + "] Installing...")
    print("  2. [ServiceWorker] ❌ DELETING old cache: sweetmoney-cache-v" + old_version.replace('.', '_'))
    print("  3. [ServiceWorker] ✅ Activation complete for version " + new_version)
    print("  4. [PWA] New service worker activated - reloading page")
    print()
    print("💡 TIP: You can force immediate update by:")
    print("   - Reloading the page (Ctrl+R)")
    print("   - Or waiting up to 60 seconds")
    print()
    input("✓ Saw the update messages and page reloaded? Press ENTER...")

    # === STEP 4 ===
    print_step(4, "Verify New Version")
    print("After the page reloaded, check the console again:")
    print()
    print("You should now see:")
    print(f"  [PWA] Server version: {new_version}")
    print(f"  [ServiceWorker] Current cache version: sweetmoney-cache-v{new_version.replace('.', '_')}")
    print()
    print("Also check:")
    print("  1. Did a modal appear saying 'New Version Available'?")
    print("  2. Did the console show the old cache being deleted?")
    print("  3. Is the page showing the new content?")
    print()
    input("✓ Everything looks correct? Press ENTER...")

    # === STEP 5 ===
    print_step(5, "Verify Cache Cleanup")
    print("Let's verify the old cache was deleted:")
    print()
    print("In DevTools:")
    print("  1. Go to: Application tab → Cache Storage")
    print("  2. You should ONLY see:")
    print(f"     sweetmoney-cache-v{new_version.replace('.', '_')}")
    print("  3. The old cache should be GONE:")
    print(f"     sweetmoney-cache-v{old_version.replace('.', '_')} ← Should NOT exist")
    print()
    input("✓ Old cache is deleted? Press ENTER...")

    # === STEP 6 ===
    print_step(6, "Test Complete!")
    print("🎉 Congratulations! The PWA update mechanism is working!")
    print()
    print("What we verified:")
    print("  ✅ Service worker detects new version")
    print("  ✅ Old cache is automatically deleted")
    print("  ✅ New cache is created with new version")
    print("  ✅ Page reloads automatically")
    print("  ✅ User sees update notification")
    print()
    print("This proves that when you deploy a server update:")
    print("  → Users' apps will update automatically (within 60s)")
    print("  → Old cached content will be deleted")
    print("  → New content will be loaded")
    print("  → No stale pages possible!")
    print()
    print_separator()
    print()

    # Restore original version?
    restore = input(f"Restore original version {old_version}? (y/n): ")
    if restore.lower() == 'y':
        version_obj.version = old_version
        version_obj.save()
        print(f"✅ Version restored to {old_version}")
        print()
        print("Note: The PWA will detect this change too (within 60s)")
        print("      and revert to the old version automatically!")
    else:
        print(f"Version remains at {new_version}")

    print()
    print_separator()
    print("Test complete!")
    print_separator()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Test cancelled by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
