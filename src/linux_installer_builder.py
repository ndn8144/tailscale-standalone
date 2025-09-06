"""
Build comprehensive ATT Tailscale installer for Linux with watchdog service
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

# Load environment variables from .env file
load_dotenv()

class LinuxInstallerBuilder:
    def __init__(self):
        self.build_dir = Path("builds")
        self.temp_dir = Path("temp")
        self.linux_build_dir = self.build_dir / "linux"
        self.install_dir = Path("/opt/att/tailscale")
        self.service_user = "tailscale"
        
        # Create directories
        self.build_dir.mkdir(exist_ok=True)
        self.temp_dir.mkdir(exist_ok=True)
        self.linux_build_dir.mkdir(exist_ok=True)
    
    def load_auth_key(self):
        """Load auth key from environment variable"""
        auth_key = os.getenv('TAILSCALE_AUTH_KEY')
        
        if not auth_key:
            raise Exception("TAILSCALE_AUTH_KEY environment variable not found. Please set it in your .env file.")
        
        auth_key = auth_key.strip()
        
        if not auth_key.startswith('tskey-auth-'):
            raise Exception("Invalid auth key format. Auth key should start with 'tskey-auth-'")
        
        print(f"Auth key loaded from environment: {auth_key[:30]}...")
        return auth_key
    
    def get_linux_watchdog_code(self):
        """Get Linux watchdog service code"""
        
        watchdog_code = '''#!/usr/bin/env python3
"""
ATT Tailscale Watchdog Service for Linux
Auto-reconnect, service restart, centralized logging, startup integration
"""

import os
import sys
import time
import json
import subprocess
import logging
import logging.handlers
import signal
import threading
from datetime import datetime, timedelta
from pathlib import Path
import socket
import hashlib
import base64
from cryptography.fernet import Fernet

class Config:
    # Paths
    BASE_DIR = Path("/opt/att/tailscale")
    LOG_DIR = BASE_DIR / "logs"
    CONFIG_DIR = BASE_DIR / "config"
    
    # Files
    LOG_FILE = LOG_DIR / "att_tailscale.log"
    CONFIG_FILE = CONFIG_DIR / "config.json"
    AUTH_KEY_FILE = CONFIG_DIR / "auth_key.encrypted"
    
    # Settings
    CHECK_INTERVAL = 30  # seconds
    RECONNECT_DELAY = 5   # seconds
    MAX_RETRIES = 5
    LOG_MAX_SIZE = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5
    
    # Tailscale paths
    TAILSCALE_CMD = "/usr/bin/tailscale"
    TAILSCALED_SERVICE = "tailscaled"

class TailscaleLogger:
    """Centralized logging with rotation"""
    
    def __init__(self):
        Config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        self.logger = logging.getLogger('ATT.Tailscale')
        self.logger.setLevel(logging.INFO)
        
        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            Config.LOG_FILE,
            maxBytes=Config.LOG_MAX_SIZE,
            backupCount=Config.LOG_BACKUP_COUNT,
            encoding='utf-8'
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def info(self, msg): self.logger.info(msg)
    def warning(self, msg): self.logger.warning(msg)
    def error(self, msg): self.logger.error(msg)
    def debug(self, msg): self.logger.debug(msg)

class ConfigManager:
    """Configuration management with encryption"""
    
    def __init__(self):
        self.logger = TailscaleLogger()
        self.encryption_key = self._get_or_create_key()
    
    def _get_or_create_key(self):
        """Get or create encryption key"""
        key_file = Config.CONFIG_DIR / "encryption.key"
        
        if key_file.exists():
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            Config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(key_file, 'wb') as f:
                f.write(key)
            os.chmod(key_file, 0o600)
            return key
    
    def encrypt_auth_key(self, auth_key):
        """Encrypt auth key"""
        f = Fernet(self.encryption_key)
        encrypted = f.encrypt(auth_key.encode())
        return base64.b64encode(encrypted).decode()
    
    def decrypt_auth_key(self, encrypted_key):
        """Decrypt auth key"""
        f = Fernet(self.encryption_key)
        encrypted = base64.b64decode(encrypted_key.encode())
        return f.decrypt(encrypted).decode()
    
    def save_config(self, config):
        """Save configuration"""
        try:
            Config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            
            # Encrypt auth key if present
            if 'auth_key' in config:
                encrypted_key = self.encrypt_auth_key(config['auth_key'])
                config['auth_key_encrypted'] = encrypted_key
                del config['auth_key']
            
            with open(Config.CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            
            os.chmod(Config.CONFIG_FILE, 0o600)
            return True
        except Exception as e:
            self.logger.error(f"Failed to save config: {e}")
            return False
    
    def load_config(self):
        """Load configuration"""
        try:
            if not Config.CONFIG_FILE.exists():
                return {}
            
            with open(Config.CONFIG_FILE, 'r') as f:
                config = json.load(f)
            
            # Decrypt auth key if present
            if 'auth_key_encrypted' in config:
                config['auth_key'] = self.decrypt_auth_key(config['auth_key_encrypted'])
                del config['auth_key_encrypted']
            
            return config
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            return {}

class TailscaleMonitor:
    """Core Tailscale monitoring and management"""
    
    def __init__(self):
        self.logger = TailscaleLogger()
        self.config_manager = ConfigManager()
        self.is_running = False
        self.consecutive_failures = 0
        self.last_successful_check = None
    
    def check_network_connectivity(self):
        """Check internet connectivity"""
        try:
            socket.create_connection(("login.tailscale.com", 443), timeout=10)
            return True
        except:
            return False
    
    def get_tailscale_status(self):
        """Get Tailscale status"""
        try:
            result = subprocess.run(
                [Config.TAILSCALE_CMD, "status", "--json"],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                status = json.loads(result.stdout)
                return {
                    "success": True,
                    "data": status,
                    "backend_state": status.get("BackendState", "Unknown"),
                    "is_connected": status.get("BackendState") == "Running"
                }
            else:
                return {
                    "success": False,
                    "error": f"Status command failed: {result.stderr}",
                    "backend_state": "Error",
                    "is_connected": False
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Exception: {e}",
                "backend_state": "Error",
                "is_connected": False
            }
    
    def check_service_status(self):
        """Check systemd service status"""
        try:
            result = subprocess.run(
                ["systemctl", "is-active", Config.TAILSCALED_SERVICE],
                capture_output=True, text=True, timeout=10
            )
            return result.stdout.strip()
        except:
            return "unknown"
    
    def start_service(self):
        """Start Tailscale service"""
        try:
            self.logger.info("Starting Tailscale service...")
            result = subprocess.run(
                ["systemctl", "start", Config.TAILSCALED_SERVICE],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                time.sleep(3)  # Wait for service to start
                self.logger.info("Service started successfully")
                return True
            else:
                self.logger.error(f"Service start failed: {result.stderr}")
                return False
        except Exception as e:
            self.logger.error(f"Service start exception: {e}")
            return False
    
    def authenticate(self, auth_key):
        """Authenticate with Tailscale"""
        try:
            if not auth_key:
                self.logger.error("No auth key provided")
                return False
            
            self.logger.info("Authenticating Tailscale...")
            
            hostname = os.uname().nodename.lower()
            cmd = [
                Config.TAILSCALE_CMD, "up",
                "--auth-key", auth_key,
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
    
    def recovery_procedure(self):
        """Execute recovery procedures"""
        self.logger.info("Starting recovery procedure...")
        recovery_steps = []
        
        try:
            # Step 1: Check network connectivity
            if not self.check_network_connectivity():
                self.logger.warning("No internet connectivity - waiting for network")
                recovery_steps.append("network_wait")
                return False, recovery_steps
            
            # Step 2: Check and start service
            service_status = self.check_service_status()
            if service_status != "active":
                recovery_steps.append("start_service")
                if not self.start_service():
                    self.logger.error("Failed to start Tailscale service")
                    return False, recovery_steps
            
            # Step 3: Check Tailscale status
            time.sleep(2)
            current_status = self.get_tailscale_status()
            
            # Step 4: Authenticate if needed
            if not current_status["success"] or not current_status["is_connected"]:
                config = self.config_manager.load_config()
                auth_key = config.get("auth_key")
                
                if auth_key:
                    recovery_steps.append("authenticate")
                    if not self.authenticate(auth_key):
                        self.logger.error("Authentication failed")
                        return False, recovery_steps
                else:
                    self.logger.error("No auth key configured")
                    return False, recovery_steps
            
            # Step 5: Final verification
            time.sleep(3)
            final_status = self.get_tailscale_status()
            
            if final_status["success"] and final_status["is_connected"]:
                self.logger.info("Recovery successful")
                return True, recovery_steps
            else:
                self.logger.warning("Recovery incomplete")
                return False, recovery_steps
                
        except Exception as e:
            self.logger.error(f"Recovery procedure exception: {e}")
            return False, recovery_steps
    
    def monitor_loop(self):
        """Main monitoring loop"""
        self.logger.info("Starting monitoring loop...")
        self.is_running = True
        
        while self.is_running:
            try:
                # Health check
                status = self.get_tailscale_status()
                
                if status["success"] and status["is_connected"]:
                    # Healthy state
                    self.consecutive_failures = 0
                    self.last_successful_check = datetime.now()
                    
                    # Log healthy status periodically
                    if not self.last_successful_check or \
                       (datetime.now() - self.last_successful_check).seconds > 300:
                        self_info = status["data"].get("Self", {})
                        device_name = self_info.get("HostName", "Unknown")
                        tailscale_ip = self_info.get("TailscaleIPs", ["None"])[0]
                        self.logger.debug(f"Healthy: {device_name} - {tailscale_ip}")
                else:
                    # Unhealthy state - trigger recovery
                    self.consecutive_failures += 1
                    self.logger.warning(f"Tailscale unhealthy (attempt #{self.consecutive_failures})")
                    
                    # Exponential backoff
                    if self.consecutive_failures > 1:
                        backoff = min(300, 5 * (2 ** (self.consecutive_failures - 1)))
                        self.logger.info(f"Backoff delay: {backoff}s")
                        time.sleep(backoff)
                    
                    # Execute recovery
                    success, steps = self.recovery_procedure()
                    if success:
                        self.consecutive_failures = 0
                        self.logger.info("Recovery successful")
                    else:
                        self.logger.error(f"Recovery failed: {steps}")
                
                # Wait before next check
                time.sleep(Config.CHECK_INTERVAL)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.logger.error(f"Monitor loop exception: {e}")
                time.sleep(60)
        
        self.logger.info("Monitoring stopped")
    
    def start_monitoring(self):
        """Start monitoring in background thread"""
        if self.is_running:
            return None
        
        monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        monitor_thread.start()
        return monitor_thread
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.is_running = False

class TailscaleWatchdog:
    """Main watchdog service class"""
    
    def __init__(self):
        self.logger = TailscaleLogger()
        self.config_manager = ConfigManager()
        self.monitor = TailscaleMonitor()
        self.monitor_thread = None
    
    def setup_auth_key(self, auth_key):
        """Setup auth key"""
        try:
            config = {
                "auth_key": auth_key,
                "setup_time": datetime.now().isoformat(),
                "check_interval": 30,
                "auto_reconnect": True,
                "accept_routes": True,
                "unattended_mode": True
            }
            
            if self.config_manager.save_config(config):
                self.logger.info("Auth key configured successfully")
                return True
            else:
                self.logger.error("Failed to save auth key")
                return False
        except Exception as e:
            self.logger.error(f"Setup auth key exception: {e}")
            return False
    
    def start_monitoring(self):
        """Start monitoring"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            return self.monitor_thread
        
        self.monitor_thread = self.monitor.start_monitoring()
        return self.monitor_thread
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.monitor.stop_monitoring()
        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)
    
    def run_service(self, auth_key=None):
        """Run as service"""
        self.logger.info("Starting ATT Tailscale Watchdog Service")
        
        # Setup auth key if provided
        if auth_key:
            if not self.setup_auth_key(auth_key):
                return False
        
        # Verify auth key is configured
        config = self.config_manager.load_config()
        if not config.get("auth_key"):
            self.logger.error("No auth key configured - cannot start monitoring")
            return False
        
        # Start monitoring
        thread = self.start_monitoring()
        if not thread:
            return False
        
        try:
            # Keep service running
            while thread.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Service interrupted by user")
        except Exception as e:
            self.logger.error(f"Service exception: {e}")
        finally:
            self.stop_monitoring()
        
        self.logger.info("ATT Tailscale Watchdog Service stopped")
        return True

def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        watchdog = TailscaleWatchdog()
        
        if command == "service":
            watchdog.run_service()
        elif command == "setup" and len(sys.argv) > 2:
            auth_key = sys.argv[2]
            watchdog.run_service(auth_key)
        elif command == "test":
            config = watchdog.config_manager.load_config()
            status = watchdog.monitor.get_tailscale_status()
            print("Config:", json.dumps(config, indent=2))
            print("Status:", json.dumps(status, indent=2))
        else:
            print("Usage: tailscale-watchdog [service|setup <auth_key>|test]")
    else:
        print("Usage: tailscale-watchdog [service|setup <auth_key>|test]")

if __name__ == "__main__":
    main()
'''
        
        return watchdog_code
    
    def create_linux_installer_script(self, auth_key, watchdog_code):
        """Create Linux installer script"""
        
        print("Creating Linux installer script...")
        
        # Convert watchdog code to base64 for embedding
        watchdog_b64 = base64.b64encode(watchdog_code.encode('utf-8')).decode()
        
        build_time = datetime.now().isoformat()
        
        installer_script = f'''#!/bin/bash
# ATT Tailscale Linux Installer
# Auto-reconnect, service restart, centralized logging, startup integration

set -euo pipefail

# Configuration
EMBEDDED_AUTH_KEY="{auth_key}"
AUTH_KEY="${{1:-$EMBEDDED_AUTH_KEY}}"
INSTALL_DIR="/opt/att/tailscale"
SERVICE_USER="tailscale"
LOG_FILE="/var/log/tailscale-install.log"

# Colors for output
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
BLUE='\\033[0;34m'
NC='\\033[0m' # No Color

log() {{
    echo -e "${{GREEN}}[$(date '+%Y-%m-%d %H:%M:%S')]${{NC}} $1" | tee -a "$LOG_FILE"
}}

error() {{
    echo -e "${{RED}}[ERROR]${{NC}} $1" | tee -a "$LOG_FILE"
    exit 1
}}

warning() {{
    echo -e "${{YELLOW}}[WARNING]${{NC}} $1" | tee -a "$LOG_FILE"
}}

info() {{
    echo -e "${{BLUE}}[INFO]${{NC}} $1" | tee -a "$LOG_FILE"
}}

# Check if running as root
check_root() {{
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root (use sudo)"
    fi
}}

# Detect Linux distribution
detect_distro() {{
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        DISTRO="$ID"
        VERSION="$VERSION_ID"
    else
        error "Cannot detect Linux distribution"
    fi
    
    log "Detected: $DISTRO $VERSION"
}}

# Install Tailscale
install_tailscale() {{
    log "Installing Tailscale..."
    
    case "$DISTRO" in
        ubuntu|debian)
            curl -fsSL https://tailscale.com/install.sh | sh
            ;;
        centos|rhel|fedora)
            curl -fsSL https://tailscale.com/install.sh | sh
            ;;
        arch|manjaro)
            pacman -S --noconfirm tailscale
            ;;
        *)
            warning "Unsupported distribution: $DISTRO"
            info "Please install Tailscale manually: https://tailscale.com/download/linux"
            ;;
    esac
    
    # Enable and start Tailscale service
    systemctl enable tailscaled
    systemctl start tailscaled
    
    log "Tailscale installed successfully"
}}

# Create service user
create_service_user() {{
    if ! id "$SERVICE_USER" &>/dev/null; then
        log "Creating service user: $SERVICE_USER"
        useradd -r -s /bin/false -d "$INSTALL_DIR" "$SERVICE_USER"
    fi
}}

# Setup directories
setup_directories() {{
    log "Setting up directories..."
    
    mkdir -p "$INSTALL_DIR"/{{bin,config,logs,systemd}}
    chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
    chmod 755 "$INSTALL_DIR"
    chmod 700 "$INSTALL_DIR"/config
}}

# Install watchdog service
install_watchdog() {{
    log "Installing watchdog service..."
    
    # Decode and write watchdog script
    cat > "$INSTALL_DIR/bin/tailscale-watchdog" << 'EOF'
{watchdog_code}
EOF

    chmod +x "$INSTALL_DIR/bin/tailscale-watchdog"
    chown "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/bin/tailscale-watchdog"
}}

# Create systemd service
create_systemd_service() {{
    log "Creating systemd service..."
    
    cat > "$INSTALL_DIR/systemd/tailscale.service" << EOF
[Unit]
Description=ATT Tailscale Watchdog Service
After=network.target tailscaled.service
Wants=tailscaled.service

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/bin/tailscale-watchdog service
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security settings
NoNewPrivileges=false
PrivateTmp=true
ProtectSystem=false
ProtectHome=false
ReadWritePaths=$INSTALL_DIR

[Install]
WantedBy=multi-user.target
EOF

    # Copy to systemd directory
    cp "$INSTALL_DIR/systemd/tailscale.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable tailscale.service
    
    log "Systemd service created and enabled"
}}

# Install Python dependencies
install_python_deps() {{
    log "Installing Python dependencies..."
    
    # Check if pip3 is available
    if ! command -v pip3 &> /dev/null; then
        log "pip3 not found, installing Python pip..."
        
        case "$DISTRO" in
            ubuntu|debian)
                apt-get update -qq
                apt-get install -y python3-pip python3-venv python3-full
                ;;
            centos|rhel|fedora)
                if command -v dnf &> /dev/null; then
                    dnf install -y python3-pip python3-venv
                else
                    yum install -y python3-pip python3-venv
                fi
                ;;
            arch|manjaro)
                pacman -S --noconfirm python-pip python-venv
                ;;
            *)
                warning "Unsupported distribution for pip3 installation"
                info "Please install pip3 manually: python3-pip"
                ;;
        esac
    fi
    
    # Create virtual environment for the watchdog service
    log "Creating Python virtual environment..."
    python3 -m venv "$INSTALL_DIR/venv"
    
    # Activate virtual environment and install cryptography
    log "Installing cryptography in virtual environment..."
    "$INSTALL_DIR/venv/bin/pip" install --quiet cryptography
    
    # Update watchdog script to use virtual environment
    sed -i '1s|#!/usr/bin/env python3|#!/opt/att/tailscale/venv/bin/python|' "$INSTALL_DIR/bin/tailscale-watchdog"
    
    log "Python dependencies installed in virtual environment"
}}

# Setup authentication
setup_authentication() {{
    if [[ -z "$AUTH_KEY" ]]; then
        error "Auth key is required. Usage: $0 [auth_key] (or use embedded key)"
    fi
    
    log "Setting up authentication..."
    
    # Install Python dependencies first
    install_python_deps
    
    # Setup auth key
    sudo -u "$SERVICE_USER" "$INSTALL_DIR/bin/tailscale-watchdog" setup "$AUTH_KEY"
    
    log "Authentication configured"
}}

# Start services
start_services() {{
    log "Starting services..."
    
    # Start Tailscale with auth key
    sudo -u "$SERVICE_USER" tailscale up --auth-key="$AUTH_KEY" --accept-routes
    
    # Start watchdog service
    systemctl start tailscale.service
    
    log "Services started successfully"
}}

# Verify installation
verify_installation() {{
    log "Verifying installation..."
    
    # Check Tailscale status
    if tailscale status --json | grep -q '"BackendState":"Running"'; then
        log "[OK] Tailscale is running"
    else
        warning "[WARNING] Tailscale may not be fully connected"
    fi
    
    # Check watchdog service
    if systemctl is-active --quiet tailscale.service; then
        log "[OK] Watchdog service is active"
    else
        warning "[WARNING] Watchdog service is not active"
    fi
    
    # Show status
    info "Installation completed!"
    info "Tailscale status:"
    tailscale status
    info "Watchdog logs: $INSTALL_DIR/logs/att_tailscale.log"
    info "Service status: systemctl status tailscale.service"
}}

# Main installation process
main() {{
    echo "=========================================="
    echo "ATT Tailscale Linux Installer"
    echo "=========================================="
    echo "Features:"
    echo "  [OK] Auto-reconnect on network disconnect"
    echo "  [OK] Auto-restart Tailscale service"
    echo "  [OK] Centralized logging with rotation"
    echo "  [OK] Systemd startup integration"
    echo "  [OK] Self-healing capabilities"
    echo "=========================================="
    
    check_root
    detect_distro
    install_tailscale
    create_service_user
    setup_directories
    install_watchdog
    create_systemd_service
    setup_authentication
    start_services
    verify_installation
    
    echo "=========================================="
    echo "[SUCCESS] Installation completed successfully!"
    echo "=========================================="
}}

# Run main function
main "$@"
'''
        
        return installer_script
    
    def create_management_tools(self):
        """Create management tools"""
        
        # Management script
        manager_script = '''#!/bin/bash
# tailscale-manager.sh - Management tool

INSTALL_DIR="/opt/att/tailscale"
SERVICE_NAME="tailscale.service"

case "${1:-}" in
    status)
        echo "=== Tailscale Status ==="
        tailscale status
        echo ""
        echo "=== Watchdog Service ==="
        systemctl status "$SERVICE_NAME" --no-pager
        ;;
    logs)
        tail -f "$INSTALL_DIR/logs/att_tailscale.log"
        ;;
    restart)
        systemctl restart "$SERVICE_NAME"
        echo "Watchdog service restarted"
        ;;
    stop)
        systemctl stop "$SERVICE_NAME"
        echo "Watchdog service stopped"
        ;;
    start)
        systemctl start "$SERVICE_NAME"
        echo "Watchdog service started"
        ;;
    test)
        sudo -u tailscale "$INSTALL_DIR/bin/tailscale-watchdog" test
        ;;
    *)
        echo "Usage: $0 {status|logs|restart|stop|start|test}"
        exit 1
        ;;
esac
'''
        
        # Uninstaller script
        uninstaller_script = '''#!/bin/bash
# tailscale-uninstall.sh

set -euo pipefail

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root (use sudo)"
    exit 1
fi

log "Uninstalling ATT Tailscale..."

# Stop and disable services
systemctl stop tailscale.service 2>/dev/null || true
systemctl disable tailscale.service 2>/dev/null || true

# Remove systemd service file
rm -f /etc/systemd/system/tailscale.service
systemctl daemon-reload

# Remove installation directory
rm -rf /opt/att/tailscale

# Remove service user
userdel tailscale 2>/dev/null || true

# Optionally remove Tailscale (uncomment if needed)
# systemctl stop tailscaled
# systemctl disable tailscaled
# apt remove tailscale -y  # or equivalent for your distro

log "Uninstallation completed"
'''
        
        return manager_script, uninstaller_script
    
    def build_linux_installer(self):
        """Build the Linux installer package"""
        
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        package_name = f"TailscaleLinux-{timestamp}"
        
        print("Building ATT Tailscale Linux Installer")
        print("=" * 60)
        print("Features: Watchdog + Auto-Recovery + Centralized Logging + Systemd")
        
        try:
            # Step 1: Load auth key
            print("\\n1. Loading auth key...")
            auth_key = self.load_auth_key()
            
            # Step 2: Get watchdog code
            print("\\n2. Preparing watchdog service...")
            watchdog_code = self.get_linux_watchdog_code()
            print(f"Watchdog service: {len(watchdog_code)} characters")
            
            # Step 3: Create installer script
            print("\\n3. Creating installer script...")
            installer_script = self.create_linux_installer_script(auth_key, watchdog_code)
            
            # Step 4: Create management tools
            print("\\n4. Creating management tools...")
            manager_script, uninstaller_script = self.create_management_tools()
            
            # Step 5: Create package directory
            print("\\n5. Creating package...")
            package_dir = self.linux_build_dir / package_name
            package_dir.mkdir(exist_ok=True)
            
            # Write files
            installer_file = package_dir / "install.sh"
            installer_file.write_text(installer_script, encoding='utf-8')
            installer_file.chmod(0o755)
            
            manager_file = package_dir / "tailscale-manager.sh"
            manager_file.write_text(manager_script, encoding='utf-8')
            manager_file.chmod(0o755)
            
            uninstaller_file = package_dir / "uninstall.sh"
            uninstaller_file.write_text(uninstaller_script, encoding='utf-8')
            uninstaller_file.chmod(0o755)
            
            # Create README
            readme_content = f'''# ATT Tailscale Linux Installer

## Features
- [OK] Auto-reconnect on network disconnect
- [OK] Auto-restart Tailscale service
- [OK] Centralized logging with rotation
- [OK] Systemd startup integration
- [OK] Self-healing capabilities

## Installation
```bash
sudo ./install.sh "{auth_key[:30]}..."
```

## Management
```bash
# View status
sudo ./tailscale-manager.sh status

# View logs
sudo ./tailscale-manager.sh logs

# Restart service
sudo ./tailscale-manager.sh restart
```

## Uninstallation
```bash
sudo ./uninstall.sh
```

## Build Info
- Build Time: {datetime.now().isoformat()}
- Auth Key: {auth_key[:30]}...
- Watchdog Size: {len(watchdog_code) / 1024:.1f} KB
'''
            
            readme_file = package_dir / "README.md"
            readme_file.write_text(readme_content, encoding='utf-8')
            
            # Create build info
            build_info = {
                "build_time": datetime.now().isoformat(),
                "installer_type": "linux_with_watchdog",
                "auth_key_preview": auth_key[:30] + "...",
                "package_path": str(package_dir),
                "watchdog_size_kb": round(len(watchdog_code) / 1024, 2),
                "features": [
                    "Tailscale installation for multiple Linux distributions",
                    "Watchdog service with auto-recovery",
                    "Centralized logging (/opt/att/tailscale/logs/)",
                    "Systemd service integration",
                    "Auto-reconnect on disconnection",
                    "Service restart capability",
                    "Network connectivity monitoring",
                    "Exponential backoff on failures",
                    "Encrypted configuration storage",
                    "Management tools included"
                ]
            }
            
            # Save build info
            info_file = package_dir / "build_info.json"
            with open(info_file, 'w') as f:
                json.dump(build_info, f, indent=2)
            
            print("\\n" + "=" * 60)
            print("BUILD COMPLETED!")
            print("=" * 60)
            print(f"Package: {package_dir}")
            print(f"Auth Key: {auth_key[:30]}...")
            print(f"Build Info: {info_file}")
            
            print("\\nFEATURES:")
            for feature in build_info["features"]:
                print(f"  - {feature}")
            
            print("\\nDEPLOYMENT INSTRUCTIONS:")
            print("1. Copy package to Linux servers")
            print("2. Run: sudo ./install.sh")
            print("3. Verify: sudo ./tailscale-manager.sh status")
            print("4. Monitor: sudo ./tailscale-manager.sh logs")
            
            return package_dir, build_info
            
        except Exception as e:
            print(f"\\nBuild failed: {e}")
            raise

if __name__ == "__main__":
    builder = LinuxInstallerBuilder()
    try:
        package_dir, info = builder.build_linux_installer()
        print("\\nLINUX INSTALLER READY!")
        print(f"Package: {package_dir}")
        print("\\nTest on Linux VM before deploying to servers")
    except Exception as e:
        print(f"\\nBuild failed: {e}")