# test_phase2_setup.py - Test Phase 2 setup
"""
Test all components needed for Phase 2 before building
"""

import os
import sys
import subprocess
from pathlib import Path
import requests
import tempfile

def load_env_file():
    """Load environment variables from .env file"""
    env_file = Path(".env")
    if env_file.exists():
        env_vars = {}
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip('"\'')
                    env_vars[key.strip()] = value
        return env_vars
    return {}

def test_auth_key_file():
    """Test auth key from various sources"""
    print("1. Testing auth key...")
    
    # Priority order: .env file, then manual files
    sources = [
        ("Environment variable", lambda: os.getenv('TAILSCALE_AUTH_KEY')),
        (".env file", lambda: load_env_file().get('TAILSCALE_AUTH_KEY')),
        ("manual_auth_key.txt", lambda: Path("manual_auth_key.txt").read_text().strip() if Path("manual_auth_key.txt").exists() else None),
        ("auth_key.txt", lambda: Path("auth_key.txt").read_text().strip() if Path("auth_key.txt").exists() else None),
    ]
    
    for source_name, get_key_func in sources:
        try:
            auth_key = get_key_func()
            if auth_key and auth_key.startswith('tskey-auth-'):
                print(f"[OK] Auth key found: {source_name}")
                print(f"   Preview: {auth_key[:30]}...")
                return auth_key, source_name
            elif auth_key:
                print(f"[ERROR] Invalid auth key format in {source_name}")
        except Exception as e:
            print(f"[ERROR] Error reading {source_name}: {e}")
    
    print("[ERROR] No valid auth key found")
    print("[INFO] Create one of these:")
    print("   • .env file: echo 'TAILSCALE_AUTH_KEY=tskey-auth-your-key' > .env")
    print("   • Manual file: echo 'tskey-auth-your-key' > manual_auth_key.txt")
    print("   • Environment: export TAILSCALE_AUTH_KEY='tskey-auth-your-key'")
    return None, None

def test_pyinstaller():
    """Test PyInstaller installation"""
    print("\n2. Testing PyInstaller...")
    
    try:
        result = subprocess.run([sys.executable, "-m", "PyInstaller", "--version"], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"[OK] PyInstaller installed: {version}")
            return True
        else:
            print("[ERROR] PyInstaller not working properly")
            return False
    except FileNotFoundError:
        print("[ERROR] PyInstaller not installed")
        print("[INFO] Install with: pip install pyinstaller")
        return False
    except Exception as e:
        print(f"[ERROR] PyInstaller test failed: {e}")
        return False

def test_msi_download():
    """Test Tailscale MSI download"""
    print("\n3. Testing Tailscale MSI download...")
    
    try:
        msi_url = "https://pkgs.tailscale.com/stable/tailscale-setup-latest-amd64.msi"
        
        # Test HEAD request with redirects allowed
        response = requests.head(msi_url, timeout=10, allow_redirects=True)
        
        if response.status_code == 200:
            size = int(response.headers.get('content-length', 0)) / (1024 * 1024)
            print(f"[OK] MSI download accessible: {size:.2f} MB")
            return True
        else:
            print(f"[ERROR] MSI download failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[ERROR] MSI download test failed: {e}")
        return False

def test_build_environment():
    """Test build environment"""
    print("\n4. Testing build environment...")
    
    issues = []
    
    # Check Python version
    if sys.version_info < (3, 8):
        issues.append("Python 3.8+ required")
    else:
        print(f"[OK] Python version: {sys.version_info.major}.{sys.version_info.minor}")
    
    # Check required modules
    required_modules = ['base64', 'tempfile', 'subprocess', 'pathlib', 'json']
    missing_modules = []
    
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        issues.append(f"Missing modules: {missing_modules}")
    else:
        print("[OK] Required Python modules available")
    
    # Check disk space
    try:
        import shutil
        free_space = shutil.disk_usage('.').free / (1024**3)  # GB
        if free_space < 1:
            issues.append(f"Low disk space: {free_space:.2f} GB")
        else:
            print(f"[OK] Disk space: {free_space:.2f} GB")
    except Exception:
        issues.append("Could not check disk space")
    
    # Check temp directory
    try:
        temp_dir = Path(tempfile.gettempdir())
        if temp_dir.exists() and os.access(temp_dir, os.W_OK):
            print(f"[OK] Temp directory writable: {temp_dir}")
        else:
            issues.append("Temp directory not writable")
    except Exception:
        issues.append("Could not check temp directory")
    
    if issues:
        print(f"[ERROR] Environment issues: {issues}")
        return False
    
    return True

def test_simple_build():
    """Test simple executable build"""
    print("\n5. Testing simple build process...")
    
    try:
        # Create minimal test script
        test_script = Path("test_build.py")
        test_script.write_text('''
import sys
print("Hello from test executable!")
input("Press Enter to exit...")
sys.exit(0)
''')
        
        # Try to build it
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onefile", "--console", "--name", "test_build",
            "--distpath", "test_dist",
            "--workpath", "test_build_temp",  
            "--specpath", "test_spec",
            str(test_script)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            # Check for executable (Linux: no extension, Windows: .exe)
            exe_name = "test_build.exe" if os.name == 'nt' else "test_build"
            exe_path = Path("test_dist") / exe_name
            
            if exe_path.exists():
                size = exe_path.stat().st_size / (1024 * 1024)
                print(f"[OK] Test build successful: {size:.2f} MB")
                
                # Cleanup
                import shutil
                for cleanup_path in ["test_dist", "test_build_temp", "test_spec", "test_build.py"]:
                    path = Path(cleanup_path)
                    if path.exists():
                        if path.is_file():
                            path.unlink()
                        else:
                            shutil.rmtree(path)
                
                return True
            else:
                print(f"[ERROR] Test executable not created: {exe_path}")
                print(f"   Available files in test_dist: {list(Path('test_dist').iterdir()) if Path('test_dist').exists() else 'Directory not found'}")
                return False
        else:
            print(f"[ERROR] Test build failed:")
            print(f"   STDOUT: {result.stdout}")
            print(f"   STDERR: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("[ERROR] Test build timed out")
        return False
    except Exception as e:
        print(f"[ERROR] Test build error: {e}")
        return False

def main():
    """Main test function"""
    print("[TEST] PHASE 2 SETUP TEST")
    print("=" * 50)
    
    results = []
    
    # Test 1: Auth key file
    auth_key, key_file = test_auth_key_file()
    results.append(auth_key is not None)
    
    # Test 2: PyInstaller
    pyinstaller_ok = test_pyinstaller()
    results.append(pyinstaller_ok)
    
    # Test 3: MSI download
    msi_ok = test_msi_download()
    results.append(msi_ok)
    
    # Test 4: Build environment
    env_ok = test_build_environment()
    results.append(env_ok)
    
    # Test 5: Simple build
    if all(results):
        build_ok = test_simple_build()
        results.append(build_ok)
    else:
        print("\n5. Skipping build test due to previous failures")
        results.append(False)
    
    print("\n" + "=" * 50)
    print("[INFO] TEST RESULTS")
    print("=" * 50)
    
    test_names = [
        "Auth Key File",
        "PyInstaller", 
        "MSI Download",
        "Build Environment",
        "Simple Build"
    ]
    
    for i, (test_name, result) in enumerate(zip(test_names, results), 1):
        status = "[OK] PASS" if result else "[ERROR] FAIL"
        print(f"{i}. {test_name:<20} {status}")
    
    if all(results):
        print("\n[SUCCESS] ALL TESTS PASSED!")
        print("[BUILD] Ready to build ATT Tailscale installer!")
        
        print("\n[INFO] NEXT STEPS:")
        print("1. Run: python build_installer.py")
        print("2. Wait 5-10 minutes for build to complete")
        print("3. Test .exe on clean Windows VM")
        print("4. Deploy to pilot users")
        
        return True
    else:
        failed_tests = [name for name, result in zip(test_names, results) if not result]
        print(f"\n[ERROR] FAILED TESTS: {', '.join(failed_tests)}")
        
        print("\n[HELP] FIX THESE ISSUES:")
        if not results[0]:  # Auth key
            print("   • Create manual_auth_key.txt with your auth key")
        if not results[1]:  # PyInstaller
            print("   • Install PyInstaller: pip install pyinstaller")
        if not results[2]:  # MSI download
            print("   • Check internet connection")
        if not results[3]:  # Environment
            print("   • Check Python version and disk space")
        if not results[4]:  # Build
            print("   • Fix above issues and try again")
        
        return False

if __name__ == "__main__":
    success = main()
    
    input("\nPress Enter to exit...")
    sys.exit(0 if success else 1)