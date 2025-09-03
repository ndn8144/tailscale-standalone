import os
import sys
import time
import json
import subprocess
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
import socket
import winreg
import tempfile
import schedule

# Configuration
class Config:
    # Paths
    BASE_DIR = Path("C:/ProgramData/ATT")
    LOG_DIR = BASE_DIR / "Logs"
    CONFIG_DIR = BASE_DIR / "Config"
    
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
    TAILSCALE_EXE = Path(r"C:\Program Files\Tailscale\tailscale.exe")
    SERVICE_NAME = "Tailscale"

class TailscaleLogger:
    """Centralized logging system"""
    
    def __init__(self):
        self.logger = None
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging with rotation"""
        
        # Create directories
        Config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        
        # Configure logging
        from logging.handlers import RotatingFileHandler
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)8s | %(funcName)15s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # File handler with rotation
        file_handler = RotatingFileHandler(
            Config.LOG_FILE,
            maxBytes=Config.LOG_MAX_SIZE,
            backupCount=Config.LOG_BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        
        # Configure root logger
        logging.basicConfig(
            level=logging.DEBUG,
            handlers=[file_handler, console_handler],
            force=True  # Force reconfiguration
        )
        
        self.logger = logging.getLogger('ATT.Tailscale')
        self.logger.info("=== ATT Tailscale Watchdog Started ===")
        
    def info(self, message, **kwargs):
        if self.logger:
            self.logger.info(message, extra=kwargs)
        else:
            print(f"[INFO] {message}")
        
    def warning(self, message, **kwargs):
        if self.logger:
            self.logger.warning(message, extra=kwargs)
        else:
            print(f"[WARNING] {message}")
        
    def error(self, message, **kwargs):
        if self.logger:
            self.logger.error(message, extra=kwargs)
        else:
            print(f"[ERROR] {message}")
        
    def debug(self, message, **kwargs):
        if self.logger:
            self.logger.debug(message, extra=kwargs)
        else:
            print(f"[DEBUG] {message}")

class ConfigManager:
    """Secure configuration management"""
    
    def __init__(self, logger):
        self.logger = logger
        Config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
    def load_config(self):
        """Load configuration from file"""
        try:
            if Config.CONFIG_FILE.exists():
                with open(Config.CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                self.logger.debug("Configuration loaded successfully")
                return config
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
        
        # Return default config
        return {
            "auth_key": None,
            "hostname": None,
            "last_auth": None,
            "check_interval": Config.CHECK_INTERVAL,
            "auto_reconnect": True,
            "accept_routes": True,
            "advertise_tags": ["tag:employee"],
            "unattended_mode": True
        }
    
    def save_config(self, config):
        """Save configuration to file"""
        try:
            with open(Config.CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            self.logger.debug("Configuration saved successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save config: {e}")
            return False

class TailscaleMonitor:
    """Core Tailscale monitoring and management"""
    
    def __init__(self, logger, config_manager):
        self.logger = logger
        self.config_manager = config_manager
        self.config = config_manager.load_config()
        self.consecutive_failures = 0
        self.last_successful_check = None
        self.is_running = False
        
    def get_tailscale_status(self):
        """Get current Tailscale status with improved error handling"""
        try:
            if not Config.TAILSCALE_EXE.exists():
                return {"error": "Tailscale not installed", "status": "not_installed"}
            
            result = subprocess.run(
                [str(Config.TAILSCALE_EXE), "status", "--json"],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                try:
                    status = json.loads(result.stdout)
                    self.logger.debug(f"Tailscale status retrieved successfully")
                    
                    # Add additional status information
                    backend_state = status.get("BackendState", "Unknown")
                    self_info = status.get("Self", {})
                    
                    # Check for disconnection indicators
                    is_connected = (
                        backend_state == "Running" and 
                        self_info.get("TailscaleIPs") and 
                        len(self_info.get("TailscaleIPs", [])) > 0
                    )
                    
                    status["is_connected"] = is_connected
                    status["has_ip"] = bool(self_info.get("TailscaleIPs"))
                    status["device_name"] = self_info.get("HostName", "Unknown")
                    
                    return status
                except json.JSONDecodeError as e:
                    return {"error": f"Invalid JSON response: {e}", "status": "json_error"}
            else:
                # Check for specific error conditions
                stderr_lower = result.stderr.lower()
                if "not running" in stderr_lower or "not logged in" in stderr_lower:
                    return {"error": "Tailscale not running or logged in", "status": "not_running"}
                elif "permission denied" in stderr_lower:
                    return {"error": "Permission denied - run as administrator", "status": "permission_denied"}
                else:
                    return {"error": f"Status check failed: {result.stderr}", "status": "error"}
                
        except subprocess.TimeoutExpired:
            return {"error": "Status check timed out", "status": "timeout"}
        except Exception as e:
            return {"error": f"Status check exception: {e}", "status": "exception"}
    
    def check_service_status(self):
        """Check Windows service status with improved detection"""
        try:
            result = subprocess.run(
                ["sc", "query", Config.SERVICE_NAME],
                capture_output=True, text=True, timeout=15
            )
            
            if result.returncode == 0:
                output = result.stdout.upper()
                if "RUNNING" in output:
                    return "running"
                elif "STOPPED" in output:
                    return "stopped"
                elif "START_PENDING" in output:
                    return "starting"
                elif "STOP_PENDING" in output:
                    return "stopping"
                elif "PAUSED" in output:
                    return "paused"
                else:
                    return "unknown"
            else:
                # Try alternative method using Get-Service PowerShell command
                try:
                    ps_cmd = f"Get-Service -Name '{Config.SERVICE_NAME}' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Status"
                    ps_result = subprocess.run(
                        ["powershell", "-Command", ps_cmd],
                        capture_output=True, text=True, timeout=10
                    )
                    if ps_result.returncode == 0:
                        status = ps_result.stdout.strip().upper()
                        if status == "RUNNING":
                            return "running"
                        elif status == "STOPPED":
                            return "stopped"
                except:
                    pass
                return "not_found"
                
        except Exception as e:
            self.logger.error(f"Service status check failed: {e}")
            return "error"
    
    def start_service(self):
        """Start Tailscale service with improved reliability"""
        try:
            self.logger.info("Starting Tailscale service...")
            
            # First check if service is already running
            current_status = self.check_service_status()
            if current_status == "running":
                self.logger.info("Tailscale service is already running")
                return True
            
            # Start the service
            result = subprocess.run(
                ["sc", "start", Config.SERVICE_NAME],
                capture_output=True, text=True, timeout=60
            )
            
            if result.returncode == 0 or "already running" in result.stderr.lower():
                self.logger.info("Tailscale service start command executed")
                
                # Wait and verify service actually started
                for attempt in range(10):  # Wait up to 30 seconds
                    time.sleep(3)
                    status = self.check_service_status()
                    if status == "running":
                        self.logger.info("Tailscale service started successfully")
                        return True
                    elif status == "starting":
                        self.logger.debug(f"Service starting... attempt {attempt + 1}")
                        continue
                    else:
                        self.logger.warning(f"Service status: {status} (attempt {attempt + 1})")
                
                # If we get here, service didn't start properly
                self.logger.error("Service did not start within expected time")
                return False
            else:
                self.logger.error(f"Failed to start service: {result.stderr}")
                
                # Try alternative method using PowerShell
                try:
                    self.logger.info("Trying PowerShell method to start service...")
                    ps_cmd = f"Start-Service -Name '{Config.SERVICE_NAME}' -ErrorAction Stop"
                    ps_result = subprocess.run(
                        ["powershell", "-Command", ps_cmd],
                        capture_output=True, text=True, timeout=30
                    )
                    if ps_result.returncode == 0:
                        time.sleep(5)
                        if self.check_service_status() == "running":
                            self.logger.info("Service started successfully via PowerShell")
                            return True
                except Exception as ps_e:
                    self.logger.error(f"PowerShell start failed: {ps_e}")
                
                return False
                
        except Exception as e:
            self.logger.error(f"Exception starting service: {e}")
            return False
    
    def authenticate_tailscale(self):
        """Authenticate Tailscale with stored auth key"""
        try:
            if not self.config.get("auth_key"):
                self.logger.error("No auth key configured")
                return False
            
            self.logger.info("Authenticating Tailscale...")
            
            # Build command
            cmd = [
                str(Config.TAILSCALE_EXE), "up",
                "--auth-key", self.config["auth_key"],
                "--unattended"
            ]
            
            # Add optional parameters
            if self.config.get("accept_routes", True):
                cmd.append("--accept-routes")
                
            if self.config.get("hostname"):
                cmd.extend(["--hostname", self.config["hostname"]])
            else:
                # Use computer name as hostname
                hostname = os.environ.get('COMPUTERNAME', 'unknown').lower()
                cmd.extend(["--hostname", hostname])
            
            # Execute authentication
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                self.logger.info("Tailscale authentication successful")
                
                # Update last auth time
                self.config["last_auth"] = datetime.now().isoformat()
                self.config_manager.save_config(self.config)
                
                # Wait a moment for the connection to establish
                time.sleep(5)
                
                # Verify the connection was established
                verify_status = self.get_tailscale_status()
                if verify_status.get("is_connected", False):
                    device_name = verify_status.get("device_name", "Unknown")
                    self.logger.info(f"Connection verified - Device: {device_name}")
                    return True
                else:
                    self.logger.warning("Authentication completed but connection not yet established")
                    return True  # Still consider it successful, connection might take time
                
            else:
                self.logger.error(f"Authentication failed: {result.stderr}")
                
                # Check for specific errors
                stderr_lower = result.stderr.lower()
                if "key expired" in stderr_lower:
                    self.logger.error("Auth key has expired - manual intervention required")
                elif "invalid key" in stderr_lower:
                    self.logger.error("Auth key is invalid - check configuration")
                elif "already authenticated" in stderr_lower:
                    self.logger.info("Already authenticated - checking connection status")
                    return True  # This is actually a success case
                
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("Authentication timed out")
            return False
        except Exception as e:
            self.logger.error(f"Authentication exception: {e}")
            return False
    
    def check_network_connectivity(self):
        """Check basic network connectivity"""
        try:
            # Test connectivity to Tailscale servers
            socket.create_connection(("login.tailscale.com", 443), timeout=10)
            return True
        except Exception:
            return False
    
    def detect_manual_shutdown(self):
        """Detect if Tailscale was manually stopped by user"""
        try:
            # Check if Tailscale process is running but service is stopped
            # This might indicate manual shutdown
            import psutil  # Optional dependency for process monitoring
            
            tailscale_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    if proc.info['name'] and 'tailscale' in proc.info['name'].lower():
                        tailscale_processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            service_status = self.check_service_status()
            
            # If service is stopped but processes are running, it might be manual shutdown
            if service_status == "stopped" and tailscale_processes:
                self.logger.warning("Detected potential manual Tailscale shutdown - processes running but service stopped")
                return True
                
            return False
            
        except ImportError:
            # psutil not available, skip this check
            return False
        except Exception as e:
            self.logger.debug(f"Manual shutdown detection failed: {e}")
            return False
    
    def recovery_procedure(self, status_info):
        """Execute recovery procedures based on current status"""
        
        self.logger.info("Starting recovery procedure...")
        recovery_steps = []
        
        try:
            # Step 1: Check for manual shutdown
            if self.detect_manual_shutdown():
                self.logger.info("Detected manual shutdown - will restart service")
                recovery_steps.append("manual_shutdown_detected")
            
            # Step 2: Check network connectivity
            if not self.check_network_connectivity():
                self.logger.warning("No internet connectivity - waiting for network")
                recovery_steps.append("network_wait")
                return False, recovery_steps
            
            # Step 3: Check if Tailscale is installed
            if not Config.TAILSCALE_EXE.exists():
                self.logger.error("Tailscale executable not found")
                recovery_steps.append("reinstall_required")
                return False, recovery_steps
            
            # Step 4: Check and start service
            service_status = self.check_service_status()
            self.logger.debug(f"Service status: {service_status}")
            
            if service_status in ["stopped", "not_found"]:
                recovery_steps.append("start_service")
                if not self.start_service():
                    self.logger.error("Failed to start Tailscale service")
                    return False, recovery_steps
            
            # Step 5: Check Tailscale status after service start
            time.sleep(2)
            current_status = self.get_tailscale_status()
            
            # Step 6: Authenticate if needed
            backend_state = current_status.get("BackendState", "Unknown")
            is_connected = current_status.get("is_connected", False)
            
            # Check if authentication is needed
            auth_needed = (
                backend_state in ["NeedsLogin", "NoState", "Stopped", "not_running"] or
                (backend_state == "Running" and not is_connected) or
                current_status.get("status") in ["not_running", "permission_denied"]
            )
            
            if auth_needed:
                recovery_steps.append("authenticate")
                if not self.authenticate_tailscale():
                    self.logger.error("Failed to authenticate Tailscale")
                    return False, recovery_steps
            
            # Step 7: Final status check
            time.sleep(3)
            final_status = self.get_tailscale_status()
            final_backend_state = final_status.get("BackendState", "Unknown")
            final_is_connected = final_status.get("is_connected", False)
            
            # Check if recovery was successful
            recovery_successful = (
                final_backend_state == "Running" and 
                final_is_connected and
                final_status.get("has_ip", False)
            )
            
            if recovery_successful:
                device_name = final_status.get("device_name", "Unknown")
                tailscale_ip = final_status.get("Self", {}).get("TailscaleIPs", ["Unknown"])[0]
                self.logger.info(f"Recovery successful - Tailscale connected: {device_name} ({tailscale_ip})")
                self.consecutive_failures = 0
                self.last_successful_check = datetime.now()
                recovery_steps.append("success")
                return True, recovery_steps
            else:
                self.logger.warning(f"Recovery incomplete - Backend: {final_backend_state}, Connected: {final_is_connected}")
                recovery_steps.append("partial_success")
                return False, recovery_steps
                
        except Exception as e:
            self.logger.error(f"Recovery procedure exception: {e}")
            recovery_steps.append("exception")
            return False, recovery_steps
    
    def perform_health_check(self):
        """Perform comprehensive health check"""
        
        health_status = {
            "timestamp": datetime.now().isoformat(),
            "tailscale_status": "unknown",
            "service_status": "unknown", 
            "network_connectivity": False,
            "auth_valid": False,
            "recovery_needed": False,
            "errors": []
        }
        
        try:
            # Check network connectivity
            health_status["network_connectivity"] = self.check_network_connectivity()
            
            # Check service status
            health_status["service_status"] = self.check_service_status()
            
            # Check Tailscale status
            ts_status = self.get_tailscale_status()
            
            if "error" in ts_status:
                health_status["errors"].append(ts_status["error"])
                health_status["tailscale_status"] = ts_status["status"]
            else:
                backend_state = ts_status.get("BackendState", "Unknown")
                health_status["tailscale_status"] = backend_state
                
                # Check if we have a valid connection
                if backend_state == "Running":
                    self_info = ts_status.get("Self", {})
                    if self_info.get("TailscaleIPs"):
                        health_status["auth_valid"] = True
                        
                        # Log successful connection details
                        device_name = self_info.get("HostName", "Unknown")
                        tailscale_ip = self_info.get("TailscaleIPs", ["Unknown"])[0]
                        
                        self.logger.debug(f"Healthy connection - Device: {device_name}, IP: {tailscale_ip}")
            
            # Determine if recovery is needed with improved conditions
            recovery_conditions = [
                # Tailscale backend issues
                health_status["tailscale_status"] in ["NeedsLogin", "NoState", "Stopped", "error", "timeout", "not_running", "permission_denied"],
                # Service issues
                health_status["service_status"] in ["stopped", "not_found", "error"],
                # Connection issues (has network but no valid auth/connection)
                not health_status["auth_valid"] and health_status["network_connectivity"],
                # Disconnected state (service running but no connection)
                health_status["service_status"] == "running" and health_status["tailscale_status"] == "Running" and not health_status["auth_valid"]
            ]
            
            health_status["recovery_needed"] = any(recovery_conditions)
            
            # Add specific recovery reasons for better logging
            recovery_reasons = []
            if health_status["tailscale_status"] in ["NeedsLogin", "NoState", "Stopped", "error", "timeout", "not_running", "permission_denied"]:
                recovery_reasons.append(f"tailscale_status: {health_status['tailscale_status']}")
            if health_status["service_status"] in ["stopped", "not_found", "error"]:
                recovery_reasons.append(f"service_status: {health_status['service_status']}")
            if not health_status["auth_valid"] and health_status["network_connectivity"]:
                recovery_reasons.append("no_valid_connection")
            if health_status["service_status"] == "running" and health_status["tailscale_status"] == "Running" and not health_status["auth_valid"]:
                recovery_reasons.append("disconnected_state")
            
            health_status["recovery_reasons"] = recovery_reasons
            
            # Log health status
            if health_status["recovery_needed"]:
                self.logger.warning(f"Health check failed - Recovery needed: {health_status}")
            else:
                self.logger.debug("Health check passed")
                
            return health_status
            
        except Exception as e:
            self.logger.error(f"Health check exception: {e}")
            health_status["errors"].append(str(e))
            health_status["recovery_needed"] = True
            return health_status
    
    def monitor_loop(self):
        """Main monitoring loop"""
        
        self.logger.info("Starting monitoring loop...")
        self.is_running = True
        
        while self.is_running:
            try:
                # Perform health check
                health_status = self.perform_health_check()
                
                # Execute recovery if needed
                if health_status["recovery_needed"]:
                    self.consecutive_failures += 1
                    recovery_reasons = health_status.get("recovery_reasons", ["unknown"])
                    
                    self.logger.warning(f"Recovery needed (failure #{self.consecutive_failures}) - Reasons: {', '.join(recovery_reasons)}")
                    
                    # Exponential backoff for consecutive failures
                    if self.consecutive_failures > 1:
                        backoff_delay = min(300, Config.RECONNECT_DELAY * (2 ** (self.consecutive_failures - 1)))
                        self.logger.info(f"Applying backoff delay: {backoff_delay} seconds")
                        time.sleep(backoff_delay)
                    
                    # Attempt recovery
                    success, recovery_steps = self.recovery_procedure(health_status)
                    
                    if success:
                        self.logger.info(f"Recovery successful after steps: {', '.join(recovery_steps)}")
                        self.consecutive_failures = 0
                        self.last_successful_check = datetime.now()
                    else:
                        self.logger.error(f"Recovery failed after steps: {', '.join(recovery_steps)}")
                        
                        # If we've had too many consecutive failures, increase check interval
                        if self.consecutive_failures >= Config.MAX_RETRIES:
                            self.logger.error(f"Max retries ({Config.MAX_RETRIES}) exceeded - increasing check interval to 5 minutes")
                            time.sleep(300)  # Wait 5 minutes before next attempt
                
                else:
                    # Successful health check
                    if self.consecutive_failures > 0:
                        self.logger.info("Health check successful after previous failures")
                    
                    self.consecutive_failures = 0
                    self.last_successful_check = datetime.now()
                
                # Wait before next check
                time.sleep(self.config.get("check_interval", Config.CHECK_INTERVAL))
                
            except KeyboardInterrupt:
                self.logger.info("Monitoring interrupted by user")
                break
            except Exception as e:
                self.logger.error(f"Monitor loop exception: {e}")
                time.sleep(60)  # Wait 1 minute before retry on exception
        
        self.logger.info("Monitoring loop ended")
    
    def stop(self):
        """Stop monitoring"""
        self.logger.info("Stopping monitor...")
        self.is_running = False

class TailscaleWatchdog:
    """Main watchdog service class"""
    
    def __init__(self):
        self.logger = TailscaleLogger()
        self.config_manager = ConfigManager(self.logger)
        self.monitor = TailscaleMonitor(self.logger, self.config_manager)
        self.monitor_thread = None
        
    def setup_auth_key(self, auth_key):
        """Setup auth key in configuration"""
        config = self.config_manager.load_config()
        config["auth_key"] = auth_key
        config["setup_time"] = datetime.now().isoformat()
        
        if self.config_manager.save_config(config):
            self.logger.info("Auth key configured successfully")
            self.monitor.config = config
            return True
        else:
            self.logger.error("Failed to save auth key configuration")
            return False
    
    def start_monitoring(self):
        """Start monitoring in background thread"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.logger.warning("Monitoring already running")
            return
        
        self.logger.info("Starting watchdog monitoring...")
        self.monitor_thread = threading.Thread(target=self.monitor.monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        return self.monitor_thread
    
    def stop_monitoring(self):
        """Stop monitoring"""
        if self.monitor:
            self.monitor.stop()
        
        if self.monitor_thread and self.monitor_thread.is_alive():
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
        
        if command == "service":
            # Run as service
            auth_key = sys.argv[2] if len(sys.argv) > 2 else None
            
            watchdog = TailscaleWatchdog()
            success = watchdog.run_service(auth_key)
            sys.exit(0 if success else 1)
        
        elif command == "test":
            # Test mode
            watchdog = TailscaleWatchdog()
            
            # Test health check
            health = watchdog.monitor.perform_health_check()
            print("Health Status:", json.dumps(health, indent=2))
            
            sys.exit(0)
        
        elif command == "setup":
            # Setup auth key
            if len(sys.argv) > 2:
                auth_key = sys.argv[2]
                watchdog = TailscaleWatchdog()
                
                if watchdog.setup_auth_key(auth_key):
                    print("✅ Auth key configured successfully")
                    sys.exit(0)
                else:
                    print("❌ Failed to configure auth key")
                    sys.exit(1)
            else:
                print("Usage: python att_tailscale_watchdog.py setup <auth_key>")
                sys.exit(1)
        
        elif command == "init":
            # Initialize logging and test basic functionality
            watchdog = TailscaleWatchdog()
            watchdog.logger.info("Watchdog initialization test completed")
            print("✅ Watchdog initialized successfully")
            print(f"Log file: {Config.LOG_FILE}")
            sys.exit(0)
    
    # Default: run interactive mode
    print("ATT Tailscale Watchdog")
    print("Usage:")
    print("  python att_tailscale_watchdog.py service [auth_key]  - Run as service")
    print("  python att_tailscale_watchdog.py setup <auth_key>    - Setup auth key")
    print("  python att_tailscale_watchdog.py test               - Test current status")
    print("  python att_tailscale_watchdog.py init               - Initialize and test logging")

if __name__ == "__main__":
    main()