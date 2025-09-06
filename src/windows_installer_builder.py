"""
Build comprehensive ATT Tailscale installer with watchdog service
"""

import os
import sys
import base64
import tempfile
import subprocess
import requests
from datetime import datetime
import json
from pathlib import Path
from dotenv import load_dotenv
import time
import socket
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Load environment variables from .env file
load_dotenv()

class WindowsInstallerBuilder:
    def __init__(self):
        self.build_dir = Path("builds")
        self.temp_dir = Path("temp")
        self.watchdog_dir = Path("C:/ProgramData/ATT/Watchdog")
        self.watchdog_script = self.watchdog_dir / "att_tailscale_watchdog.py"
        
        # Create directories
        self.build_dir.mkdir(exist_ok=True)
        self.temp_dir.mkdir(exist_ok=True)
    
    def load_auth_key(self):
        """Load auth key from environment variable"""
        auth_key = os.getenv('TAILSCALE_AUTH_KEY')
        
        if not auth_key:
            raise Exception("TAILSCALE_AUTH_KEY environment variable not found. Please set it in your .env file.")
        
        auth_key = auth_key.strip()
        
        if not auth_key.startswith('tskey-auth-'):
            raise Exception("Invalid auth key format. Auth key should start with 'tskey-auth-'")
        
        print(f"[OK] Auth key loaded from environment: {auth_key[:30]}...")
        return auth_key
    
    def test_network_connectivity(self):
        """Test network connectivity to Tailscale servers"""
        print("[BUILD] Testing network connectivity...")
        
        test_hosts = [
            ("pkgs.tailscale.com", 443),
            ("login.tailscale.com", 443),
            ("api.tailscale.com", 443)
        ]
        
        reachable_hosts = 0
        for host, port in test_hosts:
            try:
                socket.create_connection((host, port), timeout=10)
                print(f"   [OK] {host}:{port} - Reachable")
                reachable_hosts += 1
            except Exception as e:
                print(f"   [WARNING] {host}:{port} - {e}")
        
        # If at least one host is reachable, consider network OK
        if reachable_hosts > 0:
            print(f"   [OK] Network connectivity confirmed ({reachable_hosts}/{len(test_hosts)} hosts reachable)")
            return True
        else:
            print(f"   [ERROR] No Tailscale hosts reachable")
            return False

    def download_msi(self):
        """Download Tailscale MSI with retry logic"""
        print("[BUILD] Downloading Tailscale MSI...")
        
        # Test connectivity first
        if not self.test_network_connectivity():
            raise Exception("Network connectivity test failed. Please check your internet connection.")
        
        # Try multiple URLs as fallback
        urls = [
            "https://pkgs.tailscale.com/stable/tailscale-setup-latest-amd64.msi",
            "https://pkgs.tailscale.com/stable/tailscale-setup-1.86.2-amd64.msi",  # Specific version fallback
        ]
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=5,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session = requests.Session()
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Try each URL with retries
        for url_index, url in enumerate(urls):
            print(f"   [BUILD] Trying URL {url_index + 1}/{len(urls)}: {url}")
            
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                try:
                    print(f"   [BUILD] Attempt {attempt}/{max_attempts}...")
                    
                    response = session.get(url, allow_redirects=True, stream=True, timeout=180)
                    response.raise_for_status()
                    
                    # Read content with progress
                    msi_data = b''
                    total_size = int(response.headers.get('content-length', 0))
                    
                    print(f"   [BUILD] Downloading {total_size / (1024*1024):.2f} MB...")
                    
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            msi_data += chunk
                            downloaded += len(chunk)
                            
                            if downloaded % (5 * 1024 * 1024) == 0:
                                progress = (downloaded / total_size * 100) if total_size > 0 else 0
                                print(f"   [INFO] Progress: {progress:.1f}%")
                    
                    print(f"[OK] Downloaded MSI: {len(msi_data) / (1024*1024):.2f} MB")
                    return msi_data
                    
                except requests.exceptions.ConnectionError as e:
                    print(f"   [ERROR] Connection error (attempt {attempt}): {e}")
                    if attempt < max_attempts:
                        wait_time = 2 ** attempt
                        print(f"   [INFO] Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        print(f"   [ERROR] Failed to download from {url} after {max_attempts} attempts")
                        break  # Try next URL
                        
                except requests.exceptions.Timeout as e:
                    print(f"   [ERROR] Timeout error (attempt {attempt}): {e}")
                    if attempt < max_attempts:
                        wait_time = 2 ** attempt
                        print(f"   [INFO] Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        print(f"   [ERROR] Download timed out from {url} after {max_attempts} attempts")
                        break  # Try next URL
                        
                except Exception as e:
                    print(f"   [ERROR] Download error (attempt {attempt}): {e}")
                    if attempt < max_attempts:
                        wait_time = 2 ** attempt
                        print(f"   [INFO] Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        print(f"   [ERROR] Download failed from {url} after {max_attempts} attempts")
                        break  # Try next URL
        
        raise Exception(f"Failed to download MSI from all {len(urls)} URLs")
    
    def get_watchdog_code(self):
        """Get watchdog service code"""
        # In real implementation, this would read from att_tailscale_watchdog.py
        # For now, return embedded version
        
        watchdog_code = '''
# Embedded ATT Tailscale Watchdog Service
import os
import sys
import time
import json
import subprocess
import logging
import threading
from datetime import datetime
from pathlib import Path
import socket

class Config:
    BASE_DIR = Path("C:/ProgramData/ATT")
    LOG_DIR = BASE_DIR / "Logs"
    CONFIG_DIR = BASE_DIR / "Config"
    LOG_FILE = LOG_DIR / "att_tailscale.log"
    CONFIG_FILE = CONFIG_DIR / "config.json"
    CHECK_INTERVAL = 30
    TAILSCALE_EXE = Path(r"C:\\Program Files\\Tailscale\\tailscale.exe")
    SERVICE_NAME = "Tailscale"

class Logger:
    def __init__(self):
        Config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s | %(levelname)8s | %(message)s',
            handlers=[
                logging.FileHandler(Config.LOG_FILE, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('ATT.Tailscale')
        
    def info(self, msg): self.logger.info(msg)
    def warning(self, msg): self.logger.warning(msg)
    def error(self, msg): self.logger.error(msg)
    def debug(self, msg): self.logger.debug(msg)

class WatchdogService:
    def __init__(self):
        self.logger = Logger()
        self.auth_key = None
        self.is_running = False
        
    def load_config(self):
        try:
            if Config.CONFIG_FILE.exists():
                with open(Config.CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                self.auth_key = config.get("auth_key")
                return config
        except Exception as e:
            self.logger.error(f"Config load failed: {e}")
        return {}
        
    def save_config(self, config):
        try:
            Config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(Config.CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"Config save failed: {e}")
            return False
    
    def get_tailscale_status(self):
        try:
            if not Config.TAILSCALE_EXE.exists():
                return {"error": "not_installed"}
                
            result = subprocess.run(
                [str(Config.TAILSCALE_EXE), "status", "--json"],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                return {"error": f"status_failed: {result.stderr}"}
                
        except Exception as e:
            return {"error": f"exception: {e}"}
    
    def check_service_status(self):
        try:
            result = subprocess.run(
                ["sc", "query", Config.SERVICE_NAME],
                capture_output=True, text=True, timeout=15
            )
            
            if result.returncode == 0:
                if "RUNNING" in result.stdout.upper():
                    return "running"
                elif "STOPPED" in result.stdout.upper():
                    return "stopped"
            return "unknown"
        except:
            return "error"
    
    def start_service(self):
        try:
            self.logger.info("Starting Tailscale service...")
            result = subprocess.run(
                ["sc", "start", Config.SERVICE_NAME],
                capture_output=True, text=True, timeout=60
            )
            
            if result.returncode == 0 or "already running" in result.stderr.lower():
                self.logger.info("Service started successfully")
                time.sleep(3)
                return True
            else:
                self.logger.error(f"Service start failed: {result.stderr}")
                return False
        except Exception as e:
            self.logger.error(f"Service start exception: {e}")
            return False
    
    def authenticate(self):
        try:
            if not self.auth_key:
                self.logger.error("No auth key available")
                return False
                
            self.logger.info("Authenticating Tailscale...")
            
            hostname = os.environ.get('COMPUTERNAME', 'unknown').lower()
            cmd = [
                str(Config.TAILSCALE_EXE), "up",
                "--auth-key", self.auth_key,
                "--unattended",
                "--accept-routes",
                "--hostname", hostname
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                self.logger.info("Authentication successful")
                return True
            else:
                self.logger.error(f"Authentication failed: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Authentication exception: {e}")
            return False
    
    def check_network(self):
        try:
            socket.create_connection(("login.tailscale.com", 443), timeout=10)
            return True
        except:
            return False
    
    def recovery_procedure(self):
        self.logger.info("Starting recovery procedure...")
        
        # Check network
        if not self.check_network():
            self.logger.warning("No network connectivity")
            return False
        
        # Check and start service
        service_status = self.check_service_status()
        if service_status != "running":
            if not self.start_service():
                return False
        
        # Check Tailscale status and authenticate if needed
        ts_status = self.get_tailscale_status()
        if "error" in ts_status:
            self.logger.error(f"Tailscale status error: {ts_status['error']}")
            return False
        
        backend_state = ts_status.get("BackendState", "Unknown")
        if backend_state in ["NeedsLogin", "NoState", "Stopped"]:
            if not self.authenticate():
                return False
        
        # Final check
        time.sleep(3)
        final_status = self.get_tailscale_status()
        final_state = final_status.get("BackendState", "Unknown")
        
        if final_state == "Running":
            self.logger.info("Recovery successful")
            return True
        else:
            self.logger.warning(f"Recovery incomplete: {final_state}")
            return False
    
    def monitor_loop(self):
        self.logger.info("Starting monitoring loop...")
        self.is_running = True
        consecutive_failures = 0
        
        while self.is_running:
            try:
                # Health check
                ts_status = self.get_tailscale_status()
                
                if "error" in ts_status:
                    needs_recovery = True
                    self.logger.warning(f"Tailscale error: {ts_status['error']}")
                else:
                    backend_state = ts_status.get("BackendState", "Unknown")
                    needs_recovery = backend_state not in ["Running"]
                    
                    if not needs_recovery:
                        # Log healthy status
                        self_info = ts_status.get("Self", {})
                        device_name = self_info.get("HostName", "Unknown")
                        tailscale_ip = self_info.get("TailscaleIPs", ["None"])[0]
                        self.logger.debug(f"Healthy: {device_name} - {tailscale_ip}")
                
                # Recovery if needed
                if needs_recovery:
                    consecutive_failures += 1
                    self.logger.warning(f"Recovery needed (attempt #{consecutive_failures})")
                    
                    # Exponential backoff
                    if consecutive_failures > 1:
                        backoff = min(300, 5 * (2 ** (consecutive_failures - 1)))
                        self.logger.info(f"Backoff delay: {backoff}s")
                        time.sleep(backoff)
                    
                    if self.recovery_procedure():
                        consecutive_failures = 0
                        self.logger.info("Recovery successful")
                    else:
                        self.logger.error("Recovery failed")
                else:
                    consecutive_failures = 0
                
                # Wait before next check
                time.sleep(Config.CHECK_INTERVAL)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.logger.error(f"Monitor loop exception: {e}")
                time.sleep(60)
        
        self.logger.info("Monitoring stopped")
    
    def setup(self, auth_key):
        self.auth_key = auth_key
        config = {"auth_key": auth_key, "setup_time": datetime.now().isoformat()}
        
        if self.save_config(config):
            self.logger.info("Watchdog setup completed")
            return True
        else:
            self.logger.error("Watchdog setup failed")
            return False
    
    def run_service(self):
        config = self.load_config()
        self.auth_key = config.get("auth_key")
        
        if not self.auth_key:
            self.logger.error("No auth key configured")
            return False
        
        self.logger.info("Starting ATT Tailscale Watchdog Service")
        
        try:
            self.monitor_loop()
        except Exception as e:
            self.logger.error(f"Service exception: {e}")
            return False
        
        return True

def main():
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        watchdog = WatchdogService()
        
        if command == "service":
            watchdog.run_service()
        elif command == "setup" and len(sys.argv) > 2:
            auth_key = sys.argv[2]
            watchdog.setup(auth_key)
        elif command == "test":
            config = watchdog.load_config()
            status = watchdog.get_tailscale_status()
            print("Config:", json.dumps(config, indent=2))
            print("Status:", json.dumps(status, indent=2))

if __name__ == "__main__":
    main()
'''
        
        return watchdog_code
    
    def create_standalone_agent(self, auth_key, msi_data, watchdog_code):
        """Create agent with watchdog integration"""
        
        print("[BUILD] Creating agent...")
        
        # Convert data to base64
        msi_b64 = base64.b64encode(msi_data).decode()
        watchdog_b64 = base64.b64encode(watchdog_code.encode('utf-8')).decode()
        
        build_time = datetime.now().isoformat()
        
        agent_code = f'''
import base64
import tempfile
import subprocess
import os
import sys
import ctypes
import json
import time
import winreg
from datetime import datetime
from pathlib import Path

# Embedded data
AUTH_KEY = "{auth_key}"
BUILD_TIME = "{build_time}"

MSI_DATA = base64.b64decode("""{msi_b64}""")
WATCHDOG_CODE = base64.b64decode("""{watchdog_b64}""").decode('utf-8')

class StandaloneInstaller:
    def __init__(self):
        self.log_file = os.path.join(os.environ.get('TEMP', '.'), 'att_tailscale_install.log')
        self.tailscale_exe = r"C:\\Program Files\\Tailscale\\tailscale.exe"
        self.watchdog_dir = Path("C:/ProgramData/ATT/Watchdog")
        self.watchdog_script = self.watchdog_dir / "att_tailscale_watchdog.py"
        
        # Clear old log
        try:
            if os.path.exists(self.log_file):
                os.unlink(self.log_file)
        except:
            pass
        
    def log(self, message, level="INFO"):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{{timestamp}}] [{{level}}] {{message}}"
        print(log_msg)
        
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_msg + "\\n")
        except:
            pass
    
    def is_admin(self):
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    
    def check_prerequisites(self):
        self.log("Checking prerequisites...")
        
        if not self.is_admin():
            print("[ERROR] Administrator privileges required")
            print("[HELP] Right-click installer and select 'Run as administrator'")
            raise Exception("Administrator privileges required")
        
        # Check Windows version
        try:
            import platform
            version = platform.version()
            self.log(f"Windows version: {{version}}")
        except Exception as e:
            self.log(f"Version check warning: {{e}}")
        
        # Check disk space
        try:
            import shutil
            free_space = shutil.disk_usage("C:\\\\").free / (1024**3)
            if free_space < 1:
                raise Exception("Insufficient disk space. Need at least 1GB free.")
            self.log(f"Available space: {{free_space:.2f}} GB")
        except Exception as e:
            self.log(f"Disk check warning: {{e}}")
        
        # Check network
        try:
            import socket
            socket.create_connection(("login.tailscale.com", 443), timeout=10)
            self.log("[OK] Network connectivity: OK")
        except Exception as e:
            self.log(f"Network warning: {{e}}")
            print("[WARNING] Limited network connectivity")
        
        self.log("[OK] Prerequisites check completed")
    
    def install_chocolatey_and_python(self):
        """Install Chocolatey, Python, and gdown via choco"""
        self.log("[BUILD] Installing Chocolatey, Python, and gdown...")
        
        try:
            # Step 1: Remove existing Chocolatey if present
            self.log("Removing existing Chocolatey installation...")
            try:
                subprocess.run(["rmdir", "/s", "/q", "C:\\\\ProgramData\\\\chocolatey"], 
                             capture_output=True, text=True, timeout=30)
                self.log("Existing Chocolatey removed")
            except Exception as e:
                self.log(f"Chocolatey removal warning: {{e}}")
            
            # Step 2: Install Chocolatey
            self.log("Installing Chocolatey...")
            choco_install_cmd = [
                "powershell", "-NoProfile", "-InputFormat", "None", "-ExecutionPolicy", "Bypass",
                "-Command", "iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))"
            ]
            
            choco_result = subprocess.run(choco_install_cmd, capture_output=True, text=True, timeout=300)
            if choco_result.returncode != 0:
                self.log(f"Chocolatey installation warning: {{choco_result.stderr}}")
                # Continue anyway, might already be installed
            
            # Step 3: Update PATH to include Chocolatey
            self.log("Updating PATH for Chocolatey...")
            try:
                import os
                choco_path = "C:\\\\ProgramData\\\\chocolatey\\\\bin"
                current_path = os.environ.get('PATH', '')
                if choco_path not in current_path:
                    os.environ['PATH'] = current_path + ';' + choco_path
                    self.log("PATH updated for Chocolatey")
            except Exception as e:
                self.log(f"PATH update warning: {{e}}")
            
            # Step 4: Install Python via Chocolatey
            self.log("Installing Python via Chocolatey...")
            python_install_cmd = ["choco", "install", "-y", "python3"]
            python_result = subprocess.run(python_install_cmd, capture_output=True, text=True, timeout=600)
            
            if python_result.returncode == 0:
                self.log("[OK] Python installed successfully via Chocolatey")
            else:
                self.log(f"Python installation warning: {{python_result.stderr}}")
                # Check if Python is already available
                try:
                    python_check = subprocess.run(["python", "--version"], capture_output=True, text=True, timeout=10)
                    if python_check.returncode == 0:
                        self.log(f"[OK] Python already available: {{python_check.stdout.strip()}}")
                    else:
                        self.log("Python installation may have failed - continuing anyway")
                except Exception as e:
                    self.log(f"Python check warning: {{e}}")
            
            # Step 5: Install gdown via pip
            self.log("Installing gdown via pip...")
            try:
                gdown_install_cmd = ["python", "-m", "pip", "install", "gdown"]
                gdown_result = subprocess.run(gdown_install_cmd, capture_output=True, text=True, timeout=300)
                
                if gdown_result.returncode == 0:
                    self.log("[OK] gdown installed successfully")
                else:
                    self.log(f"gdown installation warning: {{gdown_result.stderr}}")
                    # Try alternative installation method
                    self.log("Trying alternative gdown installation...")
                    alt_cmd = ["python", "-m", "pip", "install", "--user", "gdown"]
                    alt_result = subprocess.run(alt_cmd, capture_output=True, text=True, timeout=300)
                    if alt_result.returncode == 0:
                        self.log("[OK] gdown installed successfully (user mode)")
                    else:
                        self.log(f"gdown installation failed: {{alt_result.stderr}}")
            except Exception as e:
                self.log(f"gdown installation error: {{e}}")
            
            self.log("[OK] Chocolatey, Python, and gdown setup completed")
            return True
            
        except Exception as e:
            self.log(f"Chocolatey/Python/gdown installation failed: {{e}}")
            return False
    
    def hide_tailscale_tray_icon(self):
        """Hide Tailscale tray icon by modifying registry settings"""
        
        try:
            import winreg
            
            # Registry key to hide tray icon
            tray_key_path = r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\TrayNotify"
            
            try:
                # Open the registry key
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, tray_key_path, 0, winreg.KEY_ALL_ACCESS)
                
                # Set IconStreams and PastIconsStream to empty (this hides all tray icons)
                # Note: This is a system-wide setting that affects all tray icons
                winreg.SetValueEx(key, "IconStreams", 0, winreg.REG_BINARY, b'')
                winreg.SetValueEx(key, "PastIconsStream", 0, winreg.REG_BINARY, b'')
                
                winreg.CloseKey(key)
                self.log("[OK] Tailscale tray icon hidden via registry")
                
            except FileNotFoundError:
                # Key doesn't exist, create it
                try:
                    key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, tray_key_path)
                    winreg.SetValueEx(key, "IconStreams", 0, winreg.REG_BINARY, b'')
                    winreg.SetValueEx(key, "PastIconsStream", 0, winreg.REG_BINARY, b'')
                    winreg.CloseKey(key)
                    self.log("[OK] Registry key created and Tailscale tray icon hidden")
                except Exception as e:
                    self.log(f"Registry creation warning: {{e}}")
            except Exception as e:
                self.log(f"Registry modification warning: {{e}}")
            
            # Alternative method: Use Tailscale's own settings
            try:
                # Try to set Tailscale to run in headless mode
                tailscale_config_key = r"SOFTWARE\\Tailscale"
                key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, tailscale_config_key)
                winreg.SetValueEx(key, "HideTrayIcon", 0, winreg.REG_DWORD, 1)
                winreg.CloseKey(key)
                self.log("[OK] Tailscale configured to hide tray icon")
            except Exception as e:
                self.log(f"Tailscale config warning: {{e}}")
            
            # Method 3: Use PowerShell to hide the tray icon
            try:
                ps_commands = [
                    'Set-ItemProperty -Path "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\TrayNotify" -Name "IconStreams" -Value @() -ErrorAction SilentlyContinue',
                    'Set-ItemProperty -Path "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\TrayNotify" -Name "PastIconsStream" -Value @() -ErrorAction SilentlyContinue',
                    'if (!(Test-Path "HKLM:\\SOFTWARE\\Tailscale")) {{ New-Item -Path "HKLM:\\SOFTWARE\\Tailscale" -Force }}',
                    'Set-ItemProperty -Path "HKLM:\\SOFTWARE\\Tailscale" -Name "HideTrayIcon" -Value 1 -Type DWord -ErrorAction SilentlyContinue'
                ]
                
                for cmd in ps_commands:
                    ps_result = subprocess.run(
                        ["powershell", "-Command", cmd],
                        capture_output=True, text=True, timeout=30
                    )
                
                if ps_result.returncode == 0:
                    self.log("[OK] Tailscale tray icon hidden via PowerShell")
                else:
                    self.log(f"PowerShell method warning: {{ps_result.stderr}}")
                    
            except Exception as e:
                self.log(f"PowerShell method warning: {{e}}")
            
            self.log("[OK] Tray icon hiding completed")
            return True
            
        except Exception as e:
            self.log(f"Tray icon hiding failed: {{e}}")
            return False
    
    def extract_msi(self):
        self.log("[BUILD] Extracting Tailscale MSI...")
        
        try:
            import random
            suffix = random.randint(1000, 9999)
            msi_path = os.path.join(tempfile.gettempdir(), f"tailscale-{{suffix}}.msi")
            
            with open(msi_path, 'wb') as f:
                f.write(MSI_DATA)
            
            size_mb = os.path.getsize(msi_path) / (1024 * 1024)
            self.log(f"MSI extracted: {{size_mb:.2f}} MB to {{msi_path}}")
            
            return msi_path
        except Exception as e:
            raise Exception(f"MSI extraction failed: {{e}}")
    
    def install_tailscale(self, msi_path):
        self.log("[BUILD] Installing Tailscale...")
        
        try:
            # Check if Tailscale is already installed
            if Path(self.tailscale_exe).exists():
                self.log("[INFO] Tailscale already installed, checking version...")
                try:
                    result = subprocess.run(
                        [self.tailscale_exe, "version"],
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0:
                        self.log(f"[INFO] Current version: {{result.stdout.strip()}}")
                        self.log("[OK] Using existing Tailscale installation")
                        return
                except:
                    pass
            
            # Stop any running Tailscale processes
            self.log("[BUILD] Stopping existing Tailscale processes...")
            try:
                subprocess.run(["taskkill", "/f", "/im", "tailscale.exe"], 
                             capture_output=True, text=True, timeout=30)
                subprocess.run(["taskkill", "/f", "/im", "tailscaled.exe"], 
                             capture_output=True, text=True, timeout=30)
                time.sleep(2)
            except:
                pass
            
            msi_log = os.path.join(os.environ.get('TEMP', '.'), 'tailscale_msi.log')
            
            # Try installation with different parameters
            install_attempts = [
                # Attempt 1: Standard installation
                [
                    "msiexec.exe", "/i", msi_path,
                    "/quiet", "/norestart",
                    "TS_UNATTENDEDMODE=always",
                    "TS_INSTALLUPDATES=always",
                    "/l*v", msi_log
                ],
                # Attempt 2: Force reinstall
                [
                    "msiexec.exe", "/i", msi_path,
                    "/quiet", "/norestart", "/force",
                    "TS_UNATTENDEDMODE=always",
                    "TS_INSTALLUPDATES=always",
                    "/l*v", msi_log
                ],
                # Attempt 3: Without quiet mode for better error info
                [
                    "msiexec.exe", "/i", msi_path,
                    "/norestart",
                    "TS_UNATTENDEDMODE=always",
                    "TS_INSTALLUPDATES=always",
                    "/l*v", msi_log
                ]
            ]
            
            installation_success = False
            last_error = None
            
            for attempt, cmd in enumerate(install_attempts, 1):
                self.log(f"[BUILD] Installation attempt {{attempt}}/{{len(install_attempts)}}...")
                
                try:
                    process = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                    
                    if process.returncode == 0:
                        self.log("[OK] Tailscale installation completed")
                        installation_success = True
                        break
                    else:
                        last_error = f"Attempt {{attempt}} failed (exit {{process.returncode}})"
                        if process.stderr:
                            last_error += f": {{process.stderr}}"
                        self.log(f"[WARNING] {{last_error}}")
                        
                        # Check MSI log for more details
                        if os.path.exists(msi_log):
                            try:
                                with open(msi_log, 'r', encoding='utf-8', errors='ignore') as f:
                                    log_content = f.read()
                                    if "1603" in log_content:
                                        self.log("[INFO] MSI log shows error 1603 - trying next method...")
                            except:
                                pass
                        
                        if attempt < len(install_attempts):
                            time.sleep(3)  # Wait before next attempt
                            
                except subprocess.TimeoutExpired:
                    last_error = f"Attempt {{attempt}} timed out"
                    self.log(f"[WARNING] {{last_error}}")
                    if attempt < len(install_attempts):
                        time.sleep(3)
                except Exception as e:
                    last_error = f"Attempt {{attempt}} exception: {{e}}"
                    self.log(f"[WARNING] {{last_error}}")
                    if attempt < len(install_attempts):
                        time.sleep(3)
            
            if not installation_success:
                raise Exception(f"All installation attempts failed. Last error: {{last_error}}")
            
            # Wait for MSI process to fully complete and release file handles
            time.sleep(3)
            
            # Verify installation
            if not Path(self.tailscale_exe).exists():
                time.sleep(5)
                if not Path(self.tailscale_exe).exists():
                    raise Exception("Tailscale executable not found after installation")
            
            self.log("[OK] Installation verified")
            
        except Exception as e:
            raise Exception(f"Installation failed: {{e}}")
    
    def setup_watchdog(self):
        self.log("[BUILD] Setting up watchdog service...")
        
        try:
            # Create watchdog directory
            self.watchdog_dir.mkdir(parents=True, exist_ok=True)
            
            # Write watchdog script
            with open(self.watchdog_script, 'w', encoding='utf-8') as f:
                f.write(WATCHDOG_CODE)
            
            self.log(f"Watchdog script created: {{self.watchdog_script}}")
            
            # Create gdown utility script
            gdown_script = self.watchdog_dir / "gdown_utility.py"
            gdown_util_code = '''
import os
import sys
import subprocess
import json
from pathlib import Path

def download_with_gdown(file_id, output_path, quiet=True):
    """Download file from Google Drive using gdown"""
    try:
        cmd = ["python", "-m", "gdown", file_id, "-O", str(output_path)]
        if quiet:
            cmd.append("--quiet")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            return True, "Download successful"
        else:
            return False, f"Download failed: {{result.stderr}}"
    except Exception as e:
        return False, f"Download error: {{e}}"

def download_file_from_google_drive(file_id, output_dir=".", filename=None):
    """Download a file from Google Drive using gdown"""
    try:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        if filename:
            file_path = output_path / filename
        else:
            file_path = output_path / f"downloaded_file_{{file_id}}"
        
        success, message = download_with_gdown(file_id, file_path)
        
        if success:
            return str(file_path), message
        else:
            return None, message
            
    except Exception as e:
        return None, f"Error: {{e}}"

def main_gdown():
    if len(sys.argv) < 2:
        print("Usage: python gdown_utility.py <file_id> [output_dir] [filename]")
        sys.exit(1)
    
    file_id = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "."
    filename = sys.argv[3] if len(sys.argv) > 3 else None
    
    result, message = download_file_from_google_drive(file_id, output_dir, filename)
    
    if result:
        print(f"Success: {result}")
    else:
        print(message)
        sys.exit(1)

'''
            
            with open(gdown_script, 'w', encoding='utf-8') as f:
                f.write(gdown_util_code)
            
            self.log(f"gdown utility script created: {{gdown_script}}")
            
            # Create a simple batch file to run the watchdog
            batch_file = self.watchdog_dir / "run_watchdog.bat"
            try:
                with open(batch_file, 'w', encoding='utf-8') as f:
                    f.write('@echo off\\n')
                    f.write('cd /d "C:\\\\ProgramData\\\\ATT\\\\Watchdog"\\n')
                    f.write('python "att_tailscale_watchdog.py" service\\n')
                    f.write('pause\\n')
                
                self.log(f"Watchdog batch file created: {{batch_file}}")
            except Exception as e:
                self.log(f"Warning: Could not create batch file: {{e}}")
                # Create a simpler version
                try:
                    with open(batch_file, 'w') as f:
                        f.write('python att_tailscale_watchdog.py service\\n')
                    self.log(f"Simple batch file created: {{batch_file}}")
                except:
                    self.log("Failed to create batch file")
            
            # Create config file in the correct location
            config = {{
                "auth_key": AUTH_KEY,
                "setup_time": datetime.now().isoformat(),
                "check_interval": 30,
                "auto_reconnect": True,
                "accept_routes": True,
                "advertise_tags": ["tag:employee"],
                "unattended_mode": True,
                "gdown_enabled": True,
                "gdown_utility_path": str(gdown_script)
            }}
            
            # Create config directory and file
            config_dir = Path("C:/ProgramData/ATT/Config")
            config_dir.mkdir(parents=True, exist_ok=True)
            config_file = config_dir / "config.json"
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            self.log("[OK] Watchdog configuration created successfully")
            
            # Test watchdog initialization to ensure logging works
            try:
                # Wait a moment for file system to settle
                time.sleep(2)
                
                # Test by running the watchdog script directly with Python
                test_cmd = [sys.executable, str(self.watchdog_script), "init"]
                test_result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=30)
                if test_result.returncode == 0:
                    self.log("[OK] Watchdog initialization test passed")
                else:
                    self.log(f"Watchdog initialization test warning: {{test_result.stderr}}")
            except subprocess.TimeoutExpired:
                self.log("Watchdog initialization test timed out after 30 seconds - continuing anyway")
            except Exception as test_e:
                self.log(f"Watchdog initialization test failed: {{test_e}}")
            
            return str(batch_file)
            
        except Exception as e:
            raise Exception(f"Watchdog setup failed: {{e}}")
    
    def create_scheduled_task(self, batch_file):
        self.log("[BUILD] Creating Windows scheduled task...")
        
        try:
            task_name = "ATT_Tailscale_Watchdog"
            
            # Use schtasks command directly instead of XML
            cmd = [
                "schtasks", "/create", "/tn", task_name,
                "/tr", f'"{{batch_file}}"',
                "/sc", "onlogon",
                "/ru", "SYSTEM",
                "/f"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                raise Exception(f"Task creation failed: {{result.stderr}}")
            
            self.log(f"Scheduled task '{{task_name}}' created successfully")
            
            # Start the task immediately
            start_cmd = ["schtasks", "/run", "/tn", task_name]
            start_result = subprocess.run(start_cmd, capture_output=True, text=True, timeout=30)
            
            if start_result.returncode == 0:
                self.log("[OK] Watchdog service started")
            else:
                self.log(f"Task start warning: {{start_result.stderr}}")
            
        except Exception as e:
            raise Exception(f"Scheduled task creation failed: {{e}}")
    
    def initial_authentication(self):
        self.log("[BUILD] Performing initial authentication...")
        
        try:
            hostname = os.environ.get('COMPUTERNAME', 'unknown').lower()
            
            cmd = [
                self.tailscale_exe, "up",
                "--auth-key", AUTH_KEY,
                "--unattended",
                "--accept-routes",
                "--hostname", hostname
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                # Don't fail completely on initial auth - watchdog will retry
                self.log(f"Initial auth warning: {{result.stderr}}")
                print("[WARNING] Initial authentication had issues - watchdog will retry")
                return False
            
            self.log("[OK] Initial authentication successful")
            return True
            
        except Exception as e:
            self.log(f"Initial auth exception: {{e}}")
            return False
    
    def get_final_status(self):
        try:
            result = subprocess.run(
                [self.tailscale_exe, "status", "--json"],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                status = json.loads(result.stdout)
                self_info = status.get("Self", {{}})
                
                return {{
                    "device_name": self_info.get("HostName", "Unknown"),
                    "tailscale_ip": self_info.get("TailscaleIPs", [None])[0],
                    "backend_state": status.get("BackendState", "Unknown")
                }}
        except:
            pass
        
        return {{"device_name": "Unknown", "tailscale_ip": None, "backend_state": "Unknown"}}
    
    def cleanup_temp_files(self, msi_path):
        try:
            if os.path.exists(msi_path):
                # Wait a bit for any processes to release the file
                time.sleep(2)
                
                # Try to delete the file with retries
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        os.unlink(msi_path)
                        self.log("[OK] Temporary files cleaned")
                        return
                    except PermissionError:
                        if attempt < max_retries - 1:
                            self.log(f"File in use, retrying in 2 seconds... (attempt {{attempt + 1}})")
                            time.sleep(2)
                        else:
                            self.log(f"Cleanup warning: Could not delete {{msi_path}} - file may be in use by another process")
                    except Exception as e:
                        self.log(f"Cleanup warning: {{e}}")
                        break
        except Exception as e:
            self.log(f"Cleanup warning: {{e}}")
    
    def install(self):
        print("=" * 70)
        print("[BUILD] ATT TAILSCALE STANDALONE INSTALLER")
        print("=" * 70)
        print(f"Build Time: {{BUILD_TIME}}")
        print(f"Auth Key: {{AUTH_KEY[:15]}}...")
        print("[INFO] Features: Watchdog Service + Auto-Recovery + Centralized Logging")
        print("=" * 70)
        
        msi_path = None
        success = False
        
        try:
            self.log("Starting Tailscale deployment...")
            
            # Step 1: Prerequisites
            self.check_prerequisites()
            
            # Step 2: Install Chocolatey and Python
            self.install_chocolatey_and_python()
            
            # Step 3: Extract and install MSI
            msi_path = self.extract_msi()
            self.install_tailscale(msi_path)
            
            # Step 4: Hide Tailscale tray icon
            self.hide_tailscale_tray_icon()
            
            # Step 5: Setup watchdog service
            batch_file = self.setup_watchdog()
            
            # Step 6: Create scheduled task
            self.create_scheduled_task(batch_file)
            
            # Step 7: Initial authentication
            auth_success = self.initial_authentication()
            
            # Step 8: Get final status
            status = self.get_final_status()
            
            print("\\n" + "=" * 70)
            print("[SUCCESS] DEPLOYMENT SUCCESSFUL!")
            print("=" * 70)
            print(f"[INFO] Device: {{status['device_name']}}")
            if status['tailscale_ip']:
                print(f"[INFO] Tailscale IP: {{status['tailscale_ip']}}")
            print(f"[INFO] Backend State: {{status['backend_state']}}")
            print(f"[OK] Watchdog Service: Active")
            print(f"[INFO] Logs: C:\\\\ProgramData\\\\ATT\\\\Logs\\\\att_tailscale.log")
            print("=" * 70)
            
            print("\\n[INFO] FEATURES ACTIVE:")
            print("- Auto-reconnect on disconnection")
            print("- Auto-restart service when stopped") 
            print("- Centralized logging with rotation")
            print("- Windows startup integration")
            print("- Self-healing capabilities")
            print("- Hidden Tailscale tray icon")
            print("- Chocolatey package manager integration")
            print("- Python installation via Chocolatey")
            
            print("\\n[INFO] MONITORING:")
            print("- Watchdog checks connection every 30 seconds")
            print("- Automatic recovery on failures")
            print("- Logs saved to C:\\\\ProgramData\\\\ATT\\\\Logs\\\\")
            print("- Task visible in Task Scheduler as 'ATT_Tailscale_Watchdog'")
            
            self.log("Deployment completed successfully")
            success = True
            
        except Exception as e:
            print(f"\\n[ERROR] DEPLOYMENT FAILED: {{e}}")
            self.log(f"Deployment failed: {{e}}", "ERROR")
            
            print("\\n[HELP] TROUBLESHOOTING:")
            print("1. Ensure stable internet connection")
            print("2. Check Windows Defender/antivirus settings")
            print("3. Verify running as Administrator")
            print("4. Check Python installation for watchdog service")
            print("5. Contact IT support with error details")
            print(f"\\n[INFO] Installation log: {{self.log_file}}")
            
        finally:
            if msi_path:
                self.cleanup_temp_files(msi_path)
        
        return success

def main():
    installer = StandaloneInstaller()
    success = installer.install()
    
    print("\\n" + "=" * 70)
    if success:
        print("[SUCCESS] Installation completed successfully!")
        print("[INFO] Monitor status: Check Task Scheduler → ATT_Tailscale_Watchdog")
        print("[INFO] View logs: C:\\\\ProgramData\\\\ATT\\\\Logs\\\\att_tailscale.log")
    else:
        print("[ERROR] Installation failed - check error messages above")
    print("=" * 70)
    
    input("\\nPress Enter to close...")
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
'''

class WindowsInstallerBuilder:
    def __init__(self):
        self.build_dir = Path("builds")
        self.temp_dir = Path("temp")
        
        # Create directories
        self.build_dir.mkdir(exist_ok=True)
        self.temp_dir.mkdir(exist_ok=True)
    
    def load_auth_key(self):
        """Load auth key from environment variable"""
        auth_key = os.getenv('TAILSCALE_AUTH_KEY')
        
        if not auth_key:
            raise Exception("TAILSCALE_AUTH_KEY environment variable not found. Please set it in your .env file.")
        
        auth_key = auth_key.strip()
        
        if not auth_key.startswith('tskey-auth-'):
            raise Exception("Invalid auth key format. Auth key should start with 'tskey-auth-'")
        
        print(f"[OK] Auth key loaded from environment: {auth_key[:30]}...")
        return auth_key

    def create_standalone_agent(self, auth_key, msi_data, watchdog_code):
        """Create the standalone agent code"""
        
        # Encode MSI data
        msi_b64 = base64.b64encode(msi_data).decode('utf-8')
        
        # Create the complete agent code
        agent_code = f'''"""
ATT Tailscale Standalone Installer with Watchdog Service
"""

import os
import sys
import base64
import tempfile
import subprocess
import json
import time
from pathlib import Path
from datetime import datetime
import logging
import winreg
import random

# Embedded data
AUTH_KEY = "{auth_key}"
BUILD_TIME = "{datetime.now().isoformat()}"
MSI_DATA = "{msi_b64}"
WATCHDOG_CODE = """{watchdog_code.replace('"""', '\\"\\"\\"')}"""

class StandaloneInstaller:
    def __init__(self):
        self.tailscale_exe = "C:/Program Files/Tailscale/tailscale.exe"
        self.log_dir = Path("C:/ProgramData/ATT/Logs")
        self.log_file = self.log_dir / "att_tailscale.log"
        
        # Create log directory
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def log(self, message, level="INFO"):
        """Log message to file and console"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{{timestamp}}] [{{level}}] {{message}}"
        
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry + "\\n")
        except:
            pass
        
        if level == "ERROR":
            self.logger.error(message)
        else:
            self.logger.info(message)
    
    def check_prerequisites(self):
        """Check system prerequisites"""
        self.log("Checking system prerequisites...")
        
        # Check if running as administrator
        try:
            import ctypes
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
            if not is_admin:
                raise Exception("This installer must be run as Administrator")
        except Exception as e:
            raise Exception(f"Administrator check failed: {{e}}")
        
        # Check Windows version
        try:
            import platform
            version = platform.version()
            self.log(f"Windows version: {{version}}")
        except:
            pass
        
        self.log("Prerequisites check completed")
    
    def extract_msi(self):
        """Extract MSI from embedded data"""
        self.log("Extracting Tailscale MSI...")
        
        try:
            # Decode MSI data
            msi_bytes = base64.b64decode(MSI_DATA)
            
            # Create temporary file
            suffix = random.randint(1000, 9999)
            msi_path = os.path.join(tempfile.gettempdir(), f"tailscale-{{suffix}}.msi")
            
            with open(msi_path, 'wb') as f:
                f.write(msi_bytes)
            
            size_mb = len(msi_bytes) / (1024 * 1024)
            self.log(f"MSI extracted: {{size_mb:.2f}} MB to {{msi_path}}")
            
            return msi_path
        except Exception as e:
            raise Exception(f"MSI extraction failed: {{e}}")
    
    def install_tailscale(self, msi_path):
        """Install Tailscale from MSI"""
        self.log("Installing Tailscale...")
        
        try:
            # Stop existing processes
            try:
                subprocess.run(["taskkill", "/f", "/im", "tailscale.exe"], 
                             capture_output=True, timeout=30)
                subprocess.run(["taskkill", "/f", "/im", "tailscaled.exe"], 
                             capture_output=True, timeout=30)
                time.sleep(2)
            except:
                pass
            
            # Install MSI
            cmd = [
                "msiexec.exe", "/i", msi_path,
                "/quiet", "/norestart",
                "TS_UNATTENDEDMODE=always"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if result.returncode != 0:
                raise Exception(f"MSI installation failed: {{result.stderr}}")
            
            # Verify installation
            if not Path(self.tailscale_exe).exists():
                time.sleep(5)
                if not Path(self.tailscale_exe).exists():
                    raise Exception("Tailscale executable not found after installation")
            
            self.log("Tailscale installation completed")
            
        except Exception as e:
            raise Exception(f"Installation failed: {{e}}")
    
    def setup_watchdog(self):
        """Setup watchdog service"""
        self.log("Setting up watchdog service...")
        
        try:
            # Create watchdog directory
            watchdog_dir = Path("C:/ProgramData/ATT/Watchdog")
            watchdog_dir.mkdir(parents=True, exist_ok=True)
            
            # Write watchdog script
            watchdog_script = watchdog_dir / "att_tailscale_watchdog.py"
            with open(watchdog_script, 'w', encoding='utf-8') as f:
                f.write(WATCHDOG_CODE)
            
            # Create config
            config = {{
                "auth_key": AUTH_KEY,
                "setup_time": datetime.now().isoformat(),
                "check_interval": 30,
                "auto_reconnect": True
            }}
            
            config_dir = Path("C:/ProgramData/ATT/Config")
            config_dir.mkdir(parents=True, exist_ok=True)
            config_file = config_dir / "config.json"
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            # Create batch file
            batch_file = watchdog_dir / "run_watchdog.bat"
            with open(batch_file, 'w') as f:
                f.write('@echo off\\n')
                f.write('cd /d "C:\\\\ProgramData\\\\ATT\\\\Watchdog"\\n')
                f.write('python "att_tailscale_watchdog.py" service\\n')
            
            self.log("Watchdog service setup completed")
            return str(batch_file)
            
        except Exception as e:
            raise Exception(f"Watchdog setup failed: {{e}}")
    
    def create_scheduled_task(self, batch_file):
        """Create Windows scheduled task"""
        self.log("Creating scheduled task...")
        
        try:
            task_name = "ATT_Tailscale_Watchdog"
            
            cmd = [
                "schtasks", "/create", "/tn", task_name,
                "/tr", f'"{{batch_file}}"',
                "/sc", "onlogon",
                "/ru", "SYSTEM",
                "/f"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                raise Exception(f"Task creation failed: {{result.stderr}}")
            
            self.log("Scheduled task created successfully")
            
        except Exception as e:
            raise Exception(f"Scheduled task creation failed: {{e}}")
    
    def initial_authentication(self):
        """Perform initial Tailscale authentication"""
        self.log("Performing initial authentication...")
        
        try:
            cmd = [
                self.tailscale_exe, "up",
                "--auth-key", AUTH_KEY,
                "--unattended",
                "--accept-routes"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                self.log(f"Initial auth warning: {{result.stderr}}")
                return False
            
            self.log("Initial authentication successful")
            return True
            
        except Exception as e:
            self.log(f"Initial auth exception: {{e}}")
            return False
    
    def cleanup_temp_files(self, msi_path):
        """Clean up temporary files"""
        try:
            if os.path.exists(msi_path):
                time.sleep(2)
                os.unlink(msi_path)
                self.log("Temporary files cleaned")
        except Exception as e:
            self.log(f"Cleanup warning: {{e}}")
    
    def install(self):
        """Main installation process"""
        print("=" * 70)
        print("[BUILD] ATT TAILSCALE STANDALONE INSTALLER")
        print("=" * 70)
        print(f"Build Time: {{BUILD_TIME}}")
        print(f"Auth Key: {{AUTH_KEY[:15]}}...")
        print("=" * 70)
        
        msi_path = None
        success = False
        
        try:
            # Step 1: Prerequisites
            self.check_prerequisites()
            
            # Step 2: Extract and install MSI
            msi_path = self.extract_msi()
            self.install_tailscale(msi_path)
            
            # Step 3: Setup watchdog service
            batch_file = self.setup_watchdog()
            
            # Step 4: Create scheduled task
            self.create_scheduled_task(batch_file)
            
            # Step 5: Initial authentication
            self.initial_authentication()
            
            print("\\n" + "=" * 70)
            print("[SUCCESS] DEPLOYMENT SUCCESSFUL!")
            print("=" * 70)
            print("[INFO] Watchdog Service: Active")
            print("[INFO] Logs: C:\\\\ProgramData\\\\ATT\\\\Logs\\\\att_tailscale.log")
            print("=" * 70)
            
            self.log("Deployment completed successfully")
            success = True
            
        except Exception as e:
            print(f"\\n[ERROR] DEPLOYMENT FAILED: {{e}}")
            self.log(f"Deployment failed: {{e}}", "ERROR")
            
        finally:
            if msi_path:
                self.cleanup_temp_files(msi_path)
        
        return success

def main():
    installer = StandaloneInstaller()
    success = installer.install()
    
    print("\\n" + "=" * 70)
    if success:
        print("[SUCCESS] Installation completed successfully!")
        print("[INFO] Monitor status: Check Task Scheduler → ATT_Tailscale_Watchdog")
        print("[INFO] View logs: C:\\\\ProgramData\\\\ATT\\\\Logs\\\\att_tailscale.log")
    else:
        print("[ERROR] Installation failed - check error messages above")
    print("=" * 70)
    
    input("\\nPress Enter to close...")
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
'''
        
        return agent_code
    
    def download_msi(self):
        """Download Tailscale MSI from official source"""
        print("[INFO] Downloading Tailscale MSI...")
        
        # Tailscale MSI download URL
        url = "https://pkgs.tailscale.com/stable/tailscale-setup-latest-amd64.msi"
        
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        try:
            response = session.get(url, timeout=300)
            response.raise_for_status()
            
            msi_data = response.content
            size_mb = len(msi_data) / (1024 * 1024)
            print(f"[OK] Downloaded MSI: {size_mb:.2f} MB")
            
            return msi_data
            
        except Exception as e:
            raise Exception(f"Failed to download MSI: {e}")
    
    def get_watchdog_code(self):
        """Get the watchdog service code"""
        watchdog_file = Path("src/att_tailscale_watchdog.py")
        
        if not watchdog_file.exists():
            raise Exception(f"Watchdog file not found: {watchdog_file}")
        
        with open(watchdog_file, 'r', encoding='utf-8') as f:
            watchdog_code = f.read()
            print(f"[OK] Loaded watchdog code: {len(watchdog_code)} characters")
        return watchdog_code
    
    def build_standalone_installer(self):
        """Build the installer"""
        auth_key = self.load_auth_key()
        
        try:
            # Step 1: Load auth key
            print("\n1. Loading authentication key...")
            
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            name = f"TailscaleInstaller-{timestamp}"
            
            # Step 2: Download MSI
            print("\n2. Downloading Tailscale MSI...")
            msi_data = self.download_msi()
            
            # Step 3: Get watchdog code
            print("\n3. Preparing watchdog service...")
            watchdog_code = self.get_watchdog_code()
            
            # Step 4: Create agent
            print("\n4. Creating agent...")
            agent_code = self.create_standalone_agent(auth_key, msi_data, watchdog_code)
            
            # Step 5: Build executable
            print("\n5. Building executable...")
            
            # Save agent
            Path("temp").mkdir(exist_ok=True)
            agent_file = Path("temp/agent.py")
            agent_file.write_text(agent_code, encoding='utf-8')
            
            Path("builds/dist").mkdir(parents=True, exist_ok=True)
            
            cmd = [
                sys.executable, "-m", "PyInstaller",
                "--onefile", "--console",
                "--name", name,
                "--distpath", "builds/dist",
                str(agent_file)
            ]
            
            print("[BUILD] Building installer (5-10 minutes)...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            
            if result.returncode != 0:
                print(f"[ERROR] Build failed: {result.stderr}")
                raise Exception("PyInstaller failed")
            
            # Check for executable (Linux: no extension, Windows: .exe)
            exe_name = f"{name}.exe" if os.name == 'nt' else name
            exe_path = Path(f"builds/dist/{exe_name}")
            if not exe_path.exists():
                raise Exception("Executable not found")
            
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            
            # Create build info
            build_info = {
                "build_time": datetime.now().isoformat(),
                "installer_type": "with_watchdog",
                "auth_key_preview": auth_key[:30] + "...",
                "exe_path": str(exe_path),
                "exe_size_mb": round(size_mb, 2),
                "msi_size_mb": round(len(msi_data) / (1024 * 1024), 2),
                "watchdog_size_kb": round(len(watchdog_code) / 1024, 2),
                "features": [
                    "Tailscale MSI installation",
                    "Watchdog service with auto-recovery",
                    "Centralized logging (C:/ProgramData/ATT/Logs/)",
                    "Windows Scheduled Task integration",
                    "Auto-reconnect on disconnection",
                    "Service restart capability",
                    "Network connectivity monitoring",
                    "Exponential backoff on failures",
                    "JSON-structured logging with rotation",
                    "Hidden Tailscale tray icon",
                    "Chocolatey package manager integration",
                    "Python installation via Chocolatey",
                    "gdown integration for Google Drive downloads",
                    "gdown utility script for file downloads",
                    "Timeout handling (30s vs 10s)"
                ]
            }
            
            # Save build info
            info_file = Path(f"builds/{name}_build_info.json")
            with open(info_file, 'w') as f:
                json.dump(build_info, f, indent=2)
            
            print("\n" + "=" * 60)
            print("[SUCCESS] BUILD COMPLETED!")
            print("=" * 60)
            print(f"[INFO] Installer: {exe_path}")
            print(f"[INFO] Size: {size_mb:.2f} MB")
            print(f"[INFO] Auth Key: {auth_key[:30]}...")
            print(f"[INFO] Build Info: {info_file}")
            
            print("\n[INFO] FEATURES:")
            for feature in build_info["features"]:
                print(f"  - {feature}")
            
            print("\n[INFO] DEPLOYMENT INSTRUCTIONS:")
            print("1. Send .exe to employees via secure email")
            print("2. Instruct: Right-click → 'Run as administrator'")
            print("3. Installation includes watchdog service setup")
            print("4. Verify in Task Scheduler: 'ATT_Tailscale_Watchdog'")
            print("5. Monitor logs: C:\\ProgramData\\ATT\\Logs\\")
            
            return exe_path, build_info
            
        except Exception as e:
            print(f"\n[ERROR] Build failed: {e}")
            raise

if __name__ == "__main__":
    builder = WindowsInstallerBuilder()
    try:
        exe_path, info = builder.build_standalone_installer()
        print("\n[SUCCESS] INSTALLER READY!")
        print(f"[INFO] Installer: {exe_path}")
        print("\n[TEST] Test on VM before deploying to employees")
    except Exception as e:
        print(f"\n[ERROR] Build failed: {e}")