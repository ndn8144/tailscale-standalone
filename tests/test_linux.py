# test_linux_phase2.py - Test Linux Phase 2 setup
"""
Test all components needed for Linux Phase 2 before building
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

def test_linux_environment():
    """Test Linux build environment"""
    print("\\n2. Testing Linux environment...")
    
    issues = []
    
    # Check if running on Linux
    if sys.platform != "linux":
        issues.append("Not running on Linux")
    else:
        print("[OK] Running on Linux")
    
    # Check Python version
    if sys.version_info < (3, 8):
        issues.append("Python 3.8+ required")
    else:
        print(f"[OK] Python version: {sys.version_info.major}.{sys.version_info.minor}")
    
    # Check required modules
    required_modules = ['base64', 'tempfile', 'subprocess', 'pathlib', 'json', 'requests']
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

def test_tailscale_download():
    """Test Tailscale download for Linux"""
    print("\\n3. Testing Tailscale download...")
    
    try:
        # Test the install script URL
        install_url = "https://tailscale.com/install.sh"
        
        response = requests.head(install_url, timeout=10, allow_redirects=True)
        
        if response.status_code == 200:
            print("[OK] Tailscale install script accessible")
            return True
        else:
            print(f"[ERROR] Tailscale download failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Tailscale download test failed: {e}")
        return False

def test_cryptography_module():
    """Test cryptography module for encryption"""
    print("\\n4. Testing cryptography module...")
    
    try:
        import cryptography
        from cryptography.fernet import Fernet
        
        # Test encryption/decryption
        key = Fernet.generate_key()
        f = Fernet(key)
        test_data = "test_auth_key"
        encrypted = f.encrypt(test_data.encode())
        decrypted = f.decrypt(encrypted).decode()
        
        if decrypted == test_data:
            print("[OK] Cryptography module working")
            return True
        else:
            print("[ERROR] Cryptography test failed")
            return False
            
    except ImportError:
        print("[ERROR] Cryptography module not installed")
        print("[INFO] Install with: pip install cryptography")
        return False
    except Exception as e:
        print(f"[ERROR] Cryptography test failed: {e}")
        return False

def test_linux_build():
    """Test Linux build process"""
    print("\\n5. Testing Linux build process...")
    
    try:
        # Test if we can import the Linux builder
        sys.path.insert(0, str(Path("src")))
        from linux_installer_builder import LinuxInstallerBuilder
        
        # Create a test builder
        builder = LinuxInstallerBuilder()
        
        # Test watchdog code generation
        watchdog_code = builder.get_linux_watchdog_code()
        if len(watchdog_code) > 1000:  # Basic size check
            print("[OK] Linux watchdog code generated")
            return True
        else:
            print("[ERROR] Linux watchdog code too short")
            return False
            
    except ImportError as e:
        print(f"[ERROR] Linux builder import failed: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Linux build test failed: {e}")
        return False

def main():
    """Main test function"""
    print("LINUX PHASE 2 SETUP TEST")
    print("=" * 50)
    
    results = []
    
    # Test 1: Auth key file
    auth_key, key_file = test_auth_key_file()
    results.append(auth_key is not None)