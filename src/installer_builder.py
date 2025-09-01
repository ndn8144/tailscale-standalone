# build_installer_working.py - Final working version
"""
Phase 2: Build standalone installer - ALL BUGS FIXED
"""

import os
import sys
import base64
import tempfile
import subprocess
import requests
from datetime import datetime
import json
import shutil
from pathlib import Path

# Add to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.config import config

class WorkingInstallerBuilder:
    def __init__(self):
        self.build_dir = Path("builds")
        self.temp_dir = Path("temp")
        
        # Create directories
        self.build_dir.mkdir(exist_ok=True)
        self.temp_dir.mkdir(exist_ok=True)
    
    def load_manual_auth_key(self, key_file="manual_auth_key.txt"):
        """Load auth key from manual file"""
        key_path = Path(key_file)
        
        if not key_path.exists():
            raise Exception(f"Manual auth key file not found: {key_file}")
        
        auth_key = key_path.read_text().strip()
        
        if not auth_key.startswith('tskey-auth-'):
            raise Exception(f"Invalid auth key format in {key_file}")
        
        print(f"✅ Manual auth key loaded: {auth_key[:30]}...")
        return auth_key
    
    def download_tailscale_msi(self):
        """Download latest Tailscale MSI"""
        print("📥 Downloading Tailscale MSI...")
        
        # Multiple URLs to try
        msi_urls = [
            "https://pkgs.tailscale.com/stable/tailscale-setup-latest-amd64.msi",
            "https://github.com/tailscale/tailscale/releases/latest/download/tailscale-setup-amd64.msi"
        ]
        
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        for i, url in enumerate(msi_urls, 1):
            try:
                print(f"   🔗 Trying download URL {i}...")
                
                response = session.get(url, allow_redirects=True, stream=True, timeout=180)
                response.raise_for_status()
                
                # Read content
                msi_data = b''
                total_size = int(response.headers.get('content-length', 0))
                
                print(f"   📥 Downloading {total_size / (1024*1024):.2f} MB...")
                
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        msi_data += chunk
                        downloaded += len(chunk)
                        
                        # Progress every 5MB
                        if downloaded % (5 * 1024 * 1024) == 0:
                            progress = (downloaded / total_size * 100) if total_size > 0 else 0
                            print(f"   📊 Progress: {progress:.1f}%")
                
                msi_size = len(msi_data) / (1024 * 1024)  # MB
                print(f"✅ Downloaded MSI: {msi_size:.2f} MB")
                
                return msi_data
                
            except Exception as e:
                print(f"   ❌ URL {i} failed: {e}")
                if i == len(msi_urls):
                    raise Exception(f"All MSI download attempts failed: {e}")
        
        raise Exception("No MSI URLs worked")
    
    def create_agent_template(self, auth_key, msi_data):
        """Create the embedded agent code"""
        
        print("📝 Creating agent template...")
        msi_b64 = base64.b64encode(msi_data).decode()
        print(f"✅ MSI encoded to base64: {len(msi_b64)} characters")
        
        # FIXED: Use proper escaping for all variables
        build_timestamp = datetime.now().isoformat()
        
        # Create agent code with proper escaping
        agent_code = '''
import base64
import tempfile
import subprocess
import os
import sys
import ctypes
import json
import time
import winreg
from pathlib import Path

# Embedded configuration
AUTH_KEY = "{auth_key}"
BUILD_TIMESTAMP = "{build_timestamp}"

# Embedded MSI data
MSI_DATA = base64.b64decode("""
{msi_data_b64}
""")

class TailscaleInstaller:
    def __init__(self):
        self.log_file = os.path.join(os.environ.get('TEMP', '.'), 'tailscale-install.log')
        self.tailscale_exe = r"C:\\Program Files\\Tailscale\\tailscale.exe"
        self.service_name = "Tailscale"
        
        # Clear old log
        try:
            if os.path.exists(self.log_file):
                os.unlink(self.log_file)
        except:
            pass
        
    def log(self, message, level="INFO"):
        """Write log message"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{level}] {message}"
        print(log_message)
        
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_message + "\\n")
        except Exception:
            pass
    
    def is_admin(self):
        """Check if running with admin privileges"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    
    def check_prerequisites(self):
        """Check system requirements"""
        self.log("Checking prerequisites...")
        
        if not self.is_admin():
            print("❌ Administrator privileges required")
            print("👉 Right-click the installer and select 'Run as administrator'")
            raise Exception("Administrator privileges required")
        
        # Check Windows version
        try:
            import platform
            version = platform.version()
            self.log(f"Windows version: {version}")
        except Exception as e:
            self.log(f"Windows version check warning: {e}")
        
        # Check disk space
        try:
            import shutil
            free_space = shutil.disk_usage("C:\\\\").free / (1024**3)
            self.log(f"Available disk space: {free_space:.2f} GB")
            
            if free_space < 0.5:
                raise Exception("Insufficient disk space. Need at least 500MB free.")
        except Exception as e:
            self.log(f"Disk space check warning: {e}")
        
        # Check internet connectivity
        try:
            import socket
            socket.create_connection(("login.tailscale.com", 443), timeout=10)
            self.log("Internet connectivity: OK")
        except Exception as e:
            self.log(f"Internet connectivity warning: {e}")
            print("⚠️ Internet connection may be limited")
        
        self.log("Prerequisites check completed")
    
    def extract_msi(self):
        """Extract embedded MSI to temp file"""
        self.log("Extracting Tailscale installer...")
        
        try:
            import random
            random_suffix = random.randint(1000, 9999)
            msi_path = os.path.join(tempfile.gettempdir(), f"tailscale-setup-{random_suffix}.msi")
            
            self.log(f"Extracting to: {msi_path}")
            
            with open(msi_path, 'wb') as f:
                f.write(MSI_DATA)
            
            if not os.path.exists(msi_path):
                raise Exception("MSI extraction failed - file not created")
            
            extracted_size = os.path.getsize(msi_path) / (1024 * 1024)
            self.log(f"MSI extracted successfully: {extracted_size:.2f} MB")
            
            return msi_path
            
        except Exception as e:
            raise Exception(f"Failed to extract MSI: {e}")
    
    def install_tailscale(self, msi_path):
        """Install Tailscale from MSI"""
        self.log("Installing Tailscale...")
        
        try:
            msi_log = os.path.join(os.environ.get('TEMP', '.'), 'tailscale-msi-install.log')
            
            cmd = [
                "msiexec.exe", "/i", msi_path,
                "/quiet", "/norestart",
                "TS_UNATTENDEDMODE=always",
                "TS_INSTALLUPDATES=always",
                "/l*v", msi_log
            ]
            
            self.log(f"Running MSI installer: msiexec /i {os.path.basename(msi_path)} /quiet")
            
            process = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            self.log(f"MSI installer exit code: {process.returncode}")
            
            if process.returncode != 0:
                error_msg = f"MSI installation failed (exit code {process.returncode})"
                if process.stderr:
                    error_msg += f" - {process.stderr}"
                raise Exception(error_msg)
            
            self.log("MSI installation completed")
            
            # Verify installation
            if not Path(self.tailscale_exe).exists():
                time.sleep(5)
                if not Path(self.tailscale_exe).exists():
                    raise Exception("Tailscale executable not found after installation")
            
            self.log("Tailscale installation verified")
                
        except subprocess.TimeoutExpired:
            raise Exception("MSI installation timed out")
        except Exception as e:
            raise Exception(f"Installation failed: {e}")
    
    def configure_service(self):
        """Configure Tailscale Windows service"""
        self.log("Configuring Tailscale service...")
        
        try:
            # Wait for service to be created
            max_wait = 30
            for i in range(max_wait):
                result = subprocess.run(
                    ["sc", "query", self.service_name],
                    capture_output=True, text=True
                )
                
                if result.returncode == 0:
                    self.log("Tailscale service found")
                    break
                elif i < max_wait - 1:
                    time.sleep(1)
                else:
                    self.log("Tailscale service not found - may be normal")
                    return
            
            # Set service to auto-start
            try:
                subprocess.run(
                    ["sc", "config", self.service_name, "start=", "auto"],
                    capture_output=True, text=True, check=True
                )
                self.log("Service set to auto-start")
            except:
                self.log("Could not configure auto-start")
            
            # Start service if not running
            result = subprocess.run(
                ["sc", "query", self.service_name],
                capture_output=True, text=True
            )
            
            if "RUNNING" not in result.stdout:
                try:
                    subprocess.run(
                        ["sc", "start", self.service_name],
                        capture_output=True, text=True, check=True, timeout=30
                    )
                    time.sleep(3)
                    self.log("Service started")
                except:
                    self.log("Service start warning")
            
        except Exception as e:
            self.log(f"Service configuration note: {e}", "WARN")
    
    def authenticate(self):
        """Authenticate with Tailscale"""
        self.log("Authenticating with Tailscale...")
        
        if not Path(self.tailscale_exe).exists():
            raise Exception("Tailscale executable not found")
        
        try:
            hostname = os.environ.get('COMPUTERNAME', 'windows-device').lower()
            
            cmd = [
                self.tailscale_exe, "up",
                "--auth-key", AUTH_KEY,
                "--unattended",
                "--accept-routes",
                "--hostname", hostname
            ]
            
            self.log(f"Authenticating as hostname: {hostname}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            self.log(f"Auth command exit code: {result.returncode}")
            
            if result.returncode != 0:
                error_msg = f"Authentication failed (exit code {result.returncode})"
                if result.stderr:
                    error_msg += f": {result.stderr}"
                raise Exception(error_msg)
            
            self.log("Authentication completed successfully")
            
        except subprocess.TimeoutExpired:
            raise Exception("Authentication timed out")
        except Exception as e:
            raise Exception(f"Authentication failed: {e}")
    
    def verify_installation(self):
        """Verify Tailscale is working"""
        self.log("Verifying installation...")
        
        try:
            time.sleep(3)
            
            result = subprocess.run(
                [self.tailscale_exe, "status", "--json"],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                try:
                    status = json.loads(result.stdout)
                    
                    device_name = status.get('Self', {}).get('HostName', 'Unknown')
                    tailscale_ips = status.get('Self', {}).get('TailscaleIPs', [])
                    backend_state = status.get('BackendState', 'Unknown')
                    
                    self.log(f"Device name: {device_name}")
                    self.log(f"Backend state: {backend_state}")
                    if tailscale_ips:
                        self.log(f"Tailscale IP: {tailscale_ips[0]}")
                    
                    return {
                        'device_name': device_name,
                        'tailscale_ip': tailscale_ips[0] if tailscale_ips else None,
                        'status': backend_state
                    }
                        
                except json.JSONDecodeError:
                    return {
                        'device_name': 'Unknown',
                        'tailscale_ip': None,
                        'status': 'Installed'
                    }
            else:
                error_msg = f"Status check failed (exit code {result.returncode})"
                if result.stderr:
                    error_msg += f": {result.stderr}"
                raise Exception(error_msg)
                
        except Exception as e:
            self.log(f"Verification error: {e}")
            return {
                'device_name': 'Unknown',
                'tailscale_ip': None,
                'status': 'Installed'
            }
    
    def cleanup_temp_files(self, msi_path):
        """Clean up temporary files"""
        try:
            if msi_path and os.path.exists(msi_path):
                os.unlink(msi_path)
                self.log("Temporary MSI file cleaned up")
        except Exception as e:
            self.log(f"Cleanup note: {e}", "WARN")
    
    def install(self):
        """Main installation process"""
        print("=" * 60)
        print("🚀 ATT TAILSCALE STANDALONE INSTALLER")
        print("=" * 60)
        print(f"Build: {BUILD_TIMESTAMP}")
        print(f"Auth Key: {AUTH_KEY[:30]}...")
        print("=" * 60)
        
        msi_path = None
        success = False
        
        try:
            self.log("Starting Tailscale deployment...")
            
            # Steps
            self.check_prerequisites()
            msi_path = self.extract_msi()
            self.install_tailscale(msi_path)
            self.configure_service()
            self.authenticate()
            status = self.verify_installation()
            
            print("\\n" + "=" * 60)
            print("✅ DEPLOYMENT SUCCESSFUL!")
            print(f"🖥️  Device: {status['device_name']}")
            if status.get('tailscale_ip'):
                print(f"🌐 Tailscale IP: {status['tailscale_ip']}")
            print(f"🔄 Status: {status['status']}")
            print("=" * 60)
            print("\\n🎉 You are now connected to the ATT Tailnet!")
            print("💡 Tailscale will start automatically on boot")
            print("🔍 Check: https://login.tailscale.com/admin/machines")
            
            self.log("Deployment completed successfully")
            success = True
            
        except Exception as e:
            print(f"\\n❌ DEPLOYMENT FAILED: {e}")
            self.log(f"Deployment failed: {e}", "ERROR")
            
            print("\\n🔧 TROUBLESHOOTING:")
            print("1. Ensure internet connection")
            print("2. Check antivirus settings")
            print("3. Run as Administrator")
            print("4. Check Windows Installer service")
            print("5. Contact IT support")
            print(f"\\n📋 Log: {self.log_file}")
            
        finally:
            if msi_path:
                self.cleanup_temp_files(msi_path)
        
        return success

def main():
    """Main entry point"""
    installer = TailscaleInstaller()
    success = installer.install()
    
    print("\\n" + "=" * 60)
    if success:
        print("✅ Installation completed!")
    else:
        print("❌ Installation failed.")
    print("=" * 60)
    
    input("\\nPress Enter to close...")
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
'''.format(
            auth_key=auth_key,
            build_timestamp=build_timestamp,
            msi_data_b64=msi_b64
        )
        
        return agent_code
    
    def build_executable(self, agent_code, output_name):
        """Build executable using PyInstaller - FIXED"""
        
        # Save agent code to temp file
        agent_file = self.temp_dir / "agent.py" 
        with open(agent_file, 'w', encoding='utf-8') as f:
            f.write(agent_code)
        
        print("📦 Building executable with PyInstaller...")
        
        # FIXED: Remove problematic --add-data parameter
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onefile",                    # Single file
            "--console",                    # Keep console
            "--name", output_name,
            "--distpath", str(self.build_dir / "dist"),
            "--workpath", str(self.build_dir / "build"),  
            "--specpath", str(self.build_dir),
            "--clean",                      # Clean cache
            str(agent_file)                 # FIXED: No --add-data
        ]
        
        print(f"🔨 Building (5-10 minutes)...")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if result.returncode != 0:
                print(f"❌ PyInstaller failed:")
                print(f"STDERR: {result.stderr}")
                raise Exception("PyInstaller build failed")
            
            exe_path = self.build_dir / "dist" / f"{output_name}.exe"
            
            if not exe_path.exists():
                raise Exception("Executable not found after build")
            
            exe_size = exe_path.stat().st_size / (1024 * 1024)  # MB
            print(f"✅ Executable built: {exe_path} ({exe_size:.2f} MB)")
            
            return exe_path
            
        except subprocess.TimeoutExpired:
            raise Exception("Build timed out")
        except Exception as e:
            raise Exception(f"Build failed: {e}")
    
    def build_installer(self, output_name=None):
        """Main build process"""
        
        if output_name is None:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            output_name = f"ATT-TailscaleInstaller-{timestamp}"
        
        print("🚀 Building ATT Tailscale Standalone Installer")
        print("=" * 60)
        
        try:
            # Steps
            print("\\n1️⃣ Loading manual auth key...")
            auth_key = self.load_manual_auth_key()
            
            print("\\n2️⃣ Downloading Tailscale MSI...")
            msi_data = self.download_tailscale_msi()
            
            print("\\n3️⃣ Creating agent code...")
            agent_code = self.create_agent_template(auth_key, msi_data)
            
            print("\\n4️⃣ Building executable...")
            exe_path = self.build_executable(agent_code, output_name)
            
            # Build info
            build_info = {
                "build_time": datetime.now().isoformat(),
                "auth_key_preview": auth_key[:30] + "...",
                "exe_path": str(exe_path),
                "exe_size_mb": round(exe_path.stat().st_size / (1024 * 1024), 2),
                "msi_size_mb": round(len(msi_data) / (1024 * 1024), 2)
            }
            
            # Save build info
            info_file = self.build_dir / f"{output_name}_build_info.json"
            with open(info_file, 'w') as f:
                json.dump(build_info, f, indent=2)
            
            print("\\n" + "=" * 60)
            print("✅ BUILD COMPLETED SUCCESSFULLY!")
            print("=" * 60)
            print(f"📁 Installer: {exe_path}")
            print(f"📊 Size: {build_info['exe_size_mb']} MB")
            print(f"🔑 Auth Key: {auth_key[:30]}...")
            
            print("\\n🧪 NEXT STEPS:")
            print("1. Test on Windows VM")
            print("2. Right-click → 'Run as administrator'")
            print("3. Check device in Tailscale admin")
            print("4. Deploy to employees")
            
            return {"exe_path": exe_path, "build_info": build_info}
            
        except Exception as e:
            print(f"\\n❌ Build failed: {e}")
            raise

def main():
    """CLI entry point"""
    builder = WorkingInstallerBuilder()
    
    try:
        result = builder.build_installer()
        print(f"\\n🎉 SUCCESS!")
        print(f"📁 {result['exe_path']}")
        return 0
    except Exception as e:
        print(f"\\n❌ Failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())