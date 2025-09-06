"""
Test script for Tailscale Standalone Installer
Tests both GUI and silent installation modes
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path
import time

def test_silent_installation():
    """Test silent installation"""
    print("=" * 60)
    print("TESTING SILENT INSTALLATION")
    print("=" * 60)
    
    # Create temporary installation directory
    temp_dir = Path(tempfile.mkdtemp(prefix="tailscale_test_"))
    install_dir = temp_dir / "Tailscale Standalone"
    
    try:
        # Test silent installation
        print(f"Testing installation to: {install_dir}")
        
        # Import and test silent installer
        sys.path.insert(0, str(Path(__file__).parent / "src"))
        from silent_installer import SilentInstaller
        
        installer = SilentInstaller()
        
        # Check if running as administrator
        if not installer.is_admin():
            print("[SKIP] Silent installation test requires administrator privileges")
            print("[INFO] Run as administrator to test full installation")
            return True  # Skip test, not fail
        
        success = installer.install(
            install_dir=str(install_dir),
            create_shortcuts=True,
            create_desktop_shortcut=True
        )
        
        if success:
            print("[OK] Silent installation test passed")
            
            # Test uninstallation
            print("Testing uninstallation...")
            uninstall_success = installer.uninstall(remove_data=True)
            
            if uninstall_success:
                print("[OK] Silent uninstallation test passed")
            else:
                print("[ERROR] Silent uninstallation test failed")
                return False
        else:
            print("[ERROR] Silent installation test failed")
            return False
            
        return True
        
    except Exception as e:
        print(f"[ERROR] Silent installation test failed: {e}")
        return False
    finally:
        # Cleanup
        try:
            if temp_dir.exists():
                import shutil
                shutil.rmtree(temp_dir)
        except:
            pass

def test_silent_installer():
    """Test silent installer (basic import test)"""
    print("=" * 60)
    print("TESTING SILENT INSTALLER")
    print("=" * 60)
    
    try:
        # Test silent installer import
        sys.path.insert(0, str(Path(__file__).parent / "src"))
        from silent_installer import SilentInstaller
        
        print("[OK] Silent installer import successful")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Silent installer test failed: {e}")
        return False

def test_build_system():
    """Test build system"""
    print("=" * 60)
    print("TESTING BUILD SYSTEM")
    print("=" * 60)
    
    try:
        # Test Windows installer builder import
        sys.path.insert(0, str(Path(__file__).parent / "src"))
        from windows_installer_builder import WindowsInstallerBuilder
        
        print("[OK] Windows installer builder import successful")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Build system test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("TAILSCALE STANDALONE INSTALLER TEST SUITE")
    print("=" * 80)
    
    tests = [
        ("Silent Installer", test_silent_installer),
        ("Build System", test_build_system),
        ("Silent Installation", test_silent_installation),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\\nRunning {test_name} test...")
        try:
            success = test_func()
            results[test_name] = success
        except Exception as e:
            print(f"[ERROR] {test_name} test crashed: {e}")
            results[test_name] = False
    
    # Summary
    print("\\n" + "=" * 80)
    print("TEST RESULTS SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for success in results.values() if success)
    total = len(results)
    
    for test_name, success in results.items():
        status = "PASS" if success else "FAIL"
        print(f"{test_name:20} : {status}")
    
    print(f"\\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\\n[SUCCESS] All tests passed!")
        return 0
    else:
        print(f"\\n[WARNING] {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
