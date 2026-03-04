"""
Interception Driver Setup & Verification
Ensures the interception driver is installed and functioning.
"""

import os
import sys
import subprocess
import ctypes
import shutil


def is_admin():
    """Check if running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def check_interception_installed():
    """Check if interception driver is installed."""
    try:
        import interception
        ctx = interception.auto_capture_devices()
        print("[OK] Interception driver is installed and functional.")
        return True
    except ImportError:
        print("[ERROR] interception-python package not installed.")
        print("  Run: pip install interception-python")
        return False
    except Exception as e:
        if "driver" in str(e).lower():
            print("[ERROR] Interception driver not installed on system.")
            return False
        print(f"[WARNING] Interception check returned: {e}")
        return True


def install_interception_driver():
    """Guide user through interception driver installation."""
    print("\n" + "=" * 60)
    print("INTERCEPTION DRIVER INSTALLATION")
    print("=" * 60)
    print()
    print("The Interception driver is required for hardware-level input.")
    print("This makes all mouse/keyboard inputs appear as real hardware events.")
    print()
    print("Steps:")
    print("1. Download from: https://github.com/oblitum/Interception/releases")
    print("2. Extract the archive")
    print("3. Run 'install-interception.exe /install' as Administrator")
    print("4. Restart your computer")
    print("5. Run this setup script again to verify")
    print()

    if is_admin():
        answer = input("Do you have the interception installer ready? (y/n): ").strip().lower()
        if answer == 'y':
            path = input("Enter full path to install-interception.exe: ").strip().strip('"')
            if os.path.exists(path):
                try:
                    result = subprocess.run(
                        [path, "/install"],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    print(result.stdout)
                    if result.returncode == 0:
                        print("[OK] Driver installed. Please restart your computer.")
                    else:
                        print(f"[ERROR] Installation failed: {result.stderr}")
                except Exception as e:
                    print(f"[ERROR] Failed to run installer: {e}")
            else:
                print(f"[ERROR] File not found: {path}")
    else:
        print("[WARNING] Please run this script as Administrator to install the driver.")
        print("  Right-click Command Prompt -> Run as Administrator")


def verify_python_packages():
    """Verify all required Python packages are installed."""
    required = [
        'numpy', 'cv2', 'PIL', 'win32gui', 'mss',
        'customtkinter', 'interception', 'scipy', 'easyocr',
        'rapidfuzz', 'psutil'
    ]

    missing = []
    for pkg in required:
        try:
            __import__(pkg)
            print(f"  [OK] {pkg}")
        except ImportError:
            print(f"  [MISSING] {pkg}")
            missing.append(pkg)

    return missing


def create_directory_structure():
    """Create all required directories."""
    dirs = [
        'assets/templates/inventory',
        'assets/templates/interfaces',
        'assets/templates/objects',
        'assets/templates/npcs',
        'assets/templates/random_events',
        'assets/templates/icons',
        'assets/templates/minimap',
        'assets/models',
        'assets/fonts',
        'assets/color_profiles',
        'data',
        'logs',
        'profiles',
    ]

    for d in dirs:
        os.makedirs(d, exist_ok=True)
        print(f"  [OK] {d}")


def main():
    print("=" * 60)
    print("OSRS AUTOMATION SUITE - SETUP")
    print("=" * 60)
    print()

    print("[1] Checking directory structure...")
    create_directory_structure()
    print()

    print("[2] Checking Python packages...")
    missing = verify_python_packages()
    if missing:
        pkg_map = {
            'cv2': 'opencv-python',
            'PIL': 'Pillow',
            'win32gui': 'pywin32',
        }
        install_names = [pkg_map.get(p, p) for p in missing]
        print(f"\n  Install missing: pip install {' '.join(install_names)}")
    print()

    print("[3] Checking Interception driver...")
    if not check_interception_installed():
        install_interception_driver()
    print()

    print("[4] Setup complete!")
    if not missing and check_interception_installed():
        print("  All systems ready. Run 'python main.py' to start.")
    else:
        print("  Please resolve the issues above before running the suite.")


if __name__ == "__main__":
    main()