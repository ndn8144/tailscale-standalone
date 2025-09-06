"""
Tailscale Standalone Agent Template
This will be embedded into the final .exe
"""

AGENT_TEMPLATE = '''
import base64
import tempfile
import subprocess
import os
import sys
import ctypes
import json
import time
from pathlib import Path
import winreg

# Embedded configuration
AUTH_KEY = "{auth_key}"
TAILSCALE_VERSION = "{tailscale_version}"
INSTALL_TIMESTAMP = "{install_timestamp}"
BUILD_INFO = {build_info}

# Embedded MSI data (will be replaced during build)
MSI_DATA = base64.b64decode("""
{msi_data_b64}
""")

class TailscaleInstaller:
    def __init__(self):
        self.log_file = os.path.join(os.environ['TEMP'], 'tailscale-install.log')
        self.tailscale_exe = r"C:\\Program Files\\Tailscale\\tailscale.exe"
    
    def log(self, message, level="INFO"):
        """Write log message"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{level}] {message}"
        print(log_message)
        
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_message + "\\n")
        except:
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
            raise Exception("Administrator privileges required. Please run as Administrator.")
        
        # Check Windows version
        import platform
        version = platform.version()
        self.log(f"Windows version: {version}")
        
        # Check disk space (need ~200MB)
        import shutil
        free_space = shutil.disk_usage("C:\\\\").free / (1024**3)  # GB
        if free_space < 0.5:
            raise Exception("Insufficient disk space. Need at least 500MB free.")
        
        self.log("Prerequisites check passed")
    
    def extract_msi(self):
        """Extract embedded MSI to temp file"""
        self.log("Extracting Tailscale installer...")
        
        msi_path = os.path.join(tempfile.gettempdir(), f"tailscale-setup-{os.getpid()}.msi")
        
        with open(msi_path, 'wb') as f:
            f.write(MSI_DATA)
        
        msi_size = len(MSI_DATA) / (1024 * 1024)  # MB
        self.log(f"MSI extracted: {msi_size:.2f} MB -> {msi_path}")
        
        return msi_path
    
    def install_tailscale(self, msi_path):
        """Install Tailscale from MSI"""
        self.log("Installing Tailscale...")
        
        cmd = [
            "msiexec.exe", "/i", msi_path,
            "/quiet", "/norestart",
            "TS_UNATTENDEDMODE=always",
            "TS_INSTALLUPDATES=always",
            f"/l*v", os.path.join(os.environ['TEMP'], 'tailscale-msi.log')
        ]
        
        self.log(f"Running: {' '.join(cmd)}")
        
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if process.returncode != 0:
            error_msg = f"MSI installation failed (exit code {process.returncode})"
            if process.stderr:
                error_msg += f": {process.stderr}"
            raise Exception(error_msg)
        
        self.log("Tailscale installed successfully")
        
        # Verify installation
        if not Path(self.tailscale_exe).exists():
            raise Exception("Tailscale executable not found after installation")
    
    def configure_service(self):
        """Configure Tailscale Windows service"""
        self.log("Configuring Tailscale service...")
        
        import win32service
        import win32serviceutil
        
        service_name = "Tailscale"
        
        try:
            # Ensure service exists and is set to auto-start
            win32serviceutil.ChangeServiceConfig(
                None, service_name,
                win32service.SERVICE_AUTO_START
            )
            
            # Start service if not running
            if win32serviceutil.QueryServiceStatus(service_name)[1] != win32service.SERVICE_RUNNING:
                win32serviceutil.StartService(service_name)
                time.sleep(3)
            
            self.log("Service configured successfully")
            
        except Exception as e:
            self.log(f"Service configuration warning: {e}", "WARN")
    
    def authenticate(self):
        """Authenticate with Tailscale"""
        self.log("Authenticating with Tailscale...")
        
        if not Path(self.tailscale_exe).exists():
            raise Exception("Tailscale executable not found")
        
        cmd = [
            self.tailscale_exe, "up",
            "--auth-key", AUTH_KEY,
            "--unattended",
            "--advertise-tags", "tag:employee",
            "--accept-routes",
            "--hostname", os.environ.get('COMPUTERNAME', 'unknown').lower()
        ]
        
        self.log("Authenticating...")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            error_msg = f"Authentication failed (exit code {result.returncode})"
            if result.stderr:
                error_msg += f": {result.stderr}"
            raise Exception(error_msg)
        
        self.log("Authentication successful")
    
    def verify_installation(self):
        """Verify Tailscale is working"""
        self.log("Verifying installation...")
        
        try:
            # Get status
            result = subprocess.run(
                [self.tailscale_exe, "status", "--json"],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                status = json.loads(result.stdout)
                
                device_name = status.get('Self', {}).get('HostName', 'Unknown')
                tailscale_ips = status.get('Self', {}).get('TailscaleIPs', [])
                backend_state = status.get('BackendState', 'Unknown')
                
                self.log(f"Device: {device_name}")
                if tailscale_ips:
                    self.log(f"Tailscale IP: {tailscale_ips[0]}")
                self.log(f"Status: {backend_state}")
                
                if backend_state != "Running":
                    raise Exception(f"Tailscale not running properly. Status: {backend_state}")
                
                return {
                    'device_name': device_name,
                    'tailscale_ip': tailscale_ips[0] if tailscale_ips else None,
                    'status': backend_state
                }
            else:
                raise Exception(f"Status check failed: {result.stderr}")
                
        except json.JSONDecodeError:
            raise Exception("Invalid JSON response from Tailscale")
    
    def cleanup_temp_files(self, msi_path):
        """Clean up temporary files"""
        try:
            if os.path.exists(msi_path):
                os.unlink(msi_path)
                self.log("Temporary files cleaned up")
        except Exception as e:
            self.log(f"Cleanup warning: {e}", "WARN")
    
    def install(self):
        """Main installation process"""
        print("=" * 60)
        print("[BUILD] ATT TAILSCALE STANDALONE INSTALLER")
        print("=" * 60)
        
        msi_path = None
        
        try:
            self.log("Starting Tailscale deployment...")
            
            # Step 1: Check prerequisites
            self.check_prerequisites()
            
            # Step 2: Extract MSI
            msi_path = self.extract_msi()
            
            # Step 3: Install Tailscale
            self.install_tailscale(msi_path)
            
            # Step 4: Configure service
            self.configure_service()
            
            # Step 5: Authenticate
            self.authenticate()
            
            # Step 6: Verify
            status = self.verify_installation()
            
            print("\\n" + "=" * 60)
            print("[SUCCESS] DEPLOYMENT SUCCESSFUL!")
            print(f"[INFO] Device: {status['device_name']}")
            if status['tailscale_ip']:
                print(f"[INFO] Tailscale IP: {status['tailscale_ip']}")
            print("=" * 60)
            print("\\n[SUCCESS] You are now connected to the ATT Tailnet!")
            print("[INFO] Tailscale will start automatically on boot")
            
            self.log("Deployment completed successfully")
            
        except Exception as e:
            print(f"\\n[ERROR] DEPLOYMENT FAILED: {e}")
            self.log(f"Deployment failed: {e}", "ERROR")
            
            print("\\n[HELP] Troubleshooting:")
            print("1. Ensure you have internet connection")
            print("2. Check antivirus isn't blocking the installer")
            print("3. Try running again as Administrator")
            print("4. Contact IT support with this error message")
            print(f"\\n[INFO] Log file: {self.log_file}")
            
            return False
            
        finally:
            # Cleanup
            if msi_path:
                self.cleanup_temp_files(msi_path)
        
        return True

def main():
    installer = TailscaleInstaller()
    success = installer.install()
    
    input("\\nPress Enter to close...")
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
'''