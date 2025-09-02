import os
import sys
import base64
import subprocess
import requests
from datetime import datetime
import json
from pathlib import Path

# Add to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

class SimpleBuild:
    def __init__(self):
        self.build_dir = Path("builds")
        self.temp_dir = Path("temp")
        
        # Create directories
        self.build_dir.mkdir(exist_ok=True)
        self.temp_dir.mkdir(exist_ok=True)
    
    def load_auth_key(self):
        """Load auth key"""
        key_file = Path("manual_auth_key.txt")
        if not key_file.exists():
            raise Exception("manual_auth_key.txt not found")
        
        auth_key = key_file.read_text().strip()
        if not auth_key.startswith('tskey-auth-'):
            raise Exception("Invalid auth key format")
        
        print(f"✅ Auth key loaded: {auth_key[:30]}...")
        return auth_key
    
    def download_msi(self):
        """Download Tailscale MSI"""
        print("📥 Downloading Tailscale MSI...")
        
        url = "https://pkgs.tailscale.com/stable/tailscale-setup-latest-amd64.msi"
        
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
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
                
                if downloaded % (5 * 1024 * 1024) == 0:
                    progress = (downloaded / total_size * 100) if total_size > 0 else 0
                    print(f"   📊 Progress: {progress:.1f}%")
        
        print(f"✅ Downloaded MSI: {len(msi_data) / (1024*1024):.2f} MB")
        return msi_data
    
    def create_agent(self, auth_key, msi_data):
        """Create agent code - SIMPLE VERSION"""
        
        print("📝 Creating agent...")
        
        # Convert MSI to base64
        msi_b64 = base64.b64encode(msi_data).decode()
        
        # Get current timestamp
        now = datetime.now().isoformat()
        
        # Create agent code by string concatenation (avoid template issues)
        agent_code = 'import base64\nimport tempfile\nimport subprocess\nimport os\nimport sys\nimport ctypes\nimport json\nimport time\nfrom pathlib import Path\n\n'
        
        # Add embedded data
        agent_code += f'AUTH_KEY = "{auth_key}"\n'
        agent_code += f'BUILD_TIME = "{now}"\n'
        agent_code += f'MSI_DATA = base64.b64decode("""\n{msi_b64}\n""")\n\n'
        
        # Add installer class
        agent_code += '''
class Installer:
    def __init__(self):
        self.log_file = os.path.join(os.environ.get('TEMP', '.'), 'tailscale-install.log')
        self.tailscale_exe = r"C:\\Program Files\\Tailscale\\tailscale.exe"
    
    def log(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {message}"
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
    
    def extract_msi(self):
        self.log("Extracting MSI...")
        import random
        suffix = random.randint(1000, 9999)
        msi_path = os.path.join(tempfile.gettempdir(), f"tailscale-{suffix}.msi")
        
        with open(msi_path, 'wb') as f:
            f.write(MSI_DATA)
        
        size_mb = os.path.getsize(msi_path) / (1024 * 1024)
        self.log(f"MSI extracted: {size_mb:.2f} MB")
        return msi_path
    
    def install_msi(self, msi_path):
        self.log("Installing Tailscale...")
        
        cmd = [
            "msiexec.exe", "/i", msi_path,
            "/quiet", "/norestart",
            "TS_UNATTENDEDMODE=always"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode != 0:
            raise Exception(f"MSI install failed: code {result.returncode}")
        
        self.log("MSI installation completed")
        
        # Verify
        if not Path(self.tailscale_exe).exists():
            time.sleep(5)
            if not Path(self.tailscale_exe).exists():
                raise Exception("Tailscale.exe not found after install")
    
    def authenticate(self):
        self.log("Authenticating...")
        
        hostname = os.environ.get('COMPUTERNAME', 'windows').lower()
        
        cmd = [
            self.tailscale_exe, "up",
            "--auth-key", AUTH_KEY,
            "--unattended",
            "--accept-routes",
            "--hostname", hostname
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            raise Exception(f"Auth failed: code {result.returncode}")
        
        self.log("Authentication successful")
    
    def get_status(self):
        try:
            result = subprocess.run(
                [self.tailscale_exe, "status", "--json"],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                status = json.loads(result.stdout)
                device_name = status.get('Self', {}).get('HostName', 'Unknown')
                tailscale_ips = status.get('Self', {}).get('TailscaleIPs', [])
                backend_state = status.get('BackendState', 'Unknown')
                
                return {
                    'name': device_name,
                    'ip': tailscale_ips[0] if tailscale_ips else None,
                    'state': backend_state
                }
        except:
            pass
        
        return {'name': 'Unknown', 'ip': None, 'state': 'Unknown'}
    
    def cleanup(self, msi_path):
        try:
            if os.path.exists(msi_path):
                os.unlink(msi_path)
        except:
            pass
    
    def run(self):
        print("="*60)
        print("🚀 ATT TAILSCALE INSTALLER")
        print("="*60)
        print(f"Build: {BUILD_TIME}")
        print(f"Key: {AUTH_KEY[:30]}...")
        print("="*60)
        
        if not self.is_admin():
            print("❌ Run as Administrator required!")
            input("Press Enter to exit...")
            return False
        
        msi_path = None
        try:
            self.log("Starting deployment...")
            
            # Extract MSI
            msi_path = self.extract_msi()
            
            # Install
            self.install_msi(msi_path)
            
            # Authenticate
            self.authenticate()
            
            # Get status
            status = self.get_status()
            
            print("\\n" + "="*60)
            print("✅ SUCCESS!")
            print(f"🖥️  Device: {status['name']}")
            if status['ip']:
                print(f"🌐 IP: {status['ip']}")
            print(f"🔄 State: {status['state']}")
            print("="*60)
            print("\\n🎉 Connected to ATT Tailnet!")
            print("💡 Tailscale starts automatically on boot")
            
            return True
            
        except Exception as e:
            print(f"\\n❌ FAILED: {e}")
            print("\\n🔧 Troubleshooting:")
            print("1. Check internet connection")
            print("2. Disable antivirus temporarily")
            print("3. Run as Administrator")
            print("4. Contact IT support")
            return False
            
        finally:
            if msi_path:
                self.cleanup(msi_path)

def main():
    installer = Installer()
    success = installer.run()
    
    input("\\nPress Enter to close...")
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
'''
        
        print(f"✅ Agent created: {len(agent_code)} characters")
        return agent_code
    
    def build_exe(self, agent_code, name):
        """Build with PyInstaller"""
        
        # Save agent
        agent_file = self.temp_dir / "agent.py"
        with open(agent_file, 'w', encoding='utf-8') as f:
            f.write(agent_code)
        
        print("📦 Building with PyInstaller...")
        
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onefile",
            "--console", 
            "--name", name,
            "--distpath", str(self.build_dir / "dist"),
            "--workpath", str(self.build_dir / "build"),
            "--specpath", str(self.build_dir),
            "--clean",
            str(agent_file)
        ]
        
        print("🔨 Building (5-10 minutes)...")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode != 0:
            print(f"❌ Build failed:")
            print(result.stderr)
            raise Exception("PyInstaller failed")
        
        exe_path = self.build_dir / "dist" / f"{name}.exe"
        
        if not exe_path.exists():
            raise Exception("Executable not found")
        
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"✅ Built: {exe_path} ({size_mb:.2f} MB)")
        
        return exe_path
    
    def build(self):
        """Main build process"""
        
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        name = f"ATT-TailscaleInstaller-{timestamp}"
        
        print("🚀 Simple Tailscale Installer Build")
        print("="*50)
        
        try:
            # Load auth key
            print("1️⃣ Loading auth key...")
            auth_key = self.load_auth_key()
            
            # Download MSI
            print("\\n2️⃣ Downloading MSI...")
            msi_data = self.download_msi()
            
            # Create agent
            print("\\n3️⃣ Creating agent...")
            agent_code = self.create_agent(auth_key, msi_data)
            
            # Build executable
            print("\\n4️⃣ Building executable...")
            exe_path = self.build_exe(agent_code, name)
            
            # Done
            print("\\n" + "="*50)
            print("✅ BUILD SUCCESS!")
            print("="*50)
            print(f"📁 File: {exe_path}")
            print(f"📊 Size: {exe_path.stat().st_size / (1024*1024):.2f} MB")
            print(f"🔑 Key: {auth_key[:30]}...")
            
            print("\\n🧪 NEXT STEPS:")
            print("1. Test on Windows VM")
            print("2. Run as Administrator")
            print("3. Check Tailscale admin console")
            print("4. Deploy to employees")
            
            return exe_path
            
        except Exception as e:
            print(f"\\n❌ Build failed: {e}")
            raise

if __name__ == "__main__":
    builder = SimpleBuild()
    try:
        result = builder.build()
        print("\\n🎉 Ready to deploy!")
    except Exception as e:
        print(f"\\n💥 Failed: {e}")