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
            handlers=[file_handler, console_handler]
        )
        
        self.logger = logging.getLogger('ATT.Tailscale')
        self.logger.info("=== ATT Tailscale Watchdog Started ===")
        
    def info(self, message, **kwargs):
        self.logger.info(message, extra=kwargs)
        
    def warning(self, message, **kwargs):
        self.logger.warning(message, extra=kwargs)
        
    def error(self, message, **kwargs):
        self.logger.error(message, extra=kwargs)
        
    def debug(self, message, **kwargs):
        self.logger.debug(message, extra=kwargs)

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
        """Get current Tailscale status"""
        try:
            if not Config.TAILSCALE_EXE.exists():
                return {"error": "Tailscale not installed", "status": "not_installed"}
            
            result = subprocess.run(
                [str(Config.TAILSCALE_EXE), "status", "--json"],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                status = json.loads(result.stdout)
                self.logger.debug(f"Tailscale status retrieved successfully")
                return status
            else:
                return {"error": f"Status check failed: {result.stderr}", "status": "error"}
                
        except subprocess.TimeoutExpired:
            return {"error": "Status check timed out", "status": "timeout"}
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON response: {e}", "status": "json_error"}
        except Exception as e:
            return {"error": f"Status check exception: {e}", "status": "exception"}
    
    def check_service_status(self):
        """Check Windows service status"""
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
                else:
                    return "unknown"
            else:
                return "not_found"
                
        except Exception as e:
            self.logger.error(f"Service status check failed: {e}")
            return "error"
    
    def start_service(self):
        """Start Tailscale service"""
        try:
            self.logger.info("Starting Tailscale service...")
            
            result = subprocess.run(
                ["sc", "start", Config.SERVICE_NAME],
                capture_output=True, text=True, timeout=60
            )
            
            if result.returncode == 0 or "already running" in result.stderr.lower():
                self.logger.info("Tailscale service started successfully")
                time.sleep(3)  # Wait for service to initialize
                return True
            else:
                self.logger.error(f"Failed to start service: {result.stderr}")
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
                
                return True
            else:
                self.logger.error(f"Authentication failed: {result.stderr}")
                
                # Check for specific errors
                if "key expired" in result.stderr.lower():
                    self.logger.error("Auth key has expired - manual intervention required")
                elif "invalid key" in result.stderr.lower():
                    self.logger.error("Auth key is invalid - check configuration")
                
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
    
    def recovery_procedure(self, status_info):
        """Execute recovery procedures based on current status"""
        
        self.logger.info("Starting recovery procedure...")
        recovery_steps = []
        
        try:
            # Step 1: Check network connectivity
            if not self.check_network_connectivity():
                self.logger.warning("No internet connectivity - waiting for network")
                recovery_steps.append("network_wait")
                return False, recovery_steps
            
            # Step 2: Check if Tailscale is installed
            if not Config.TAILSCALE_EXE.exists():
                self.logger.error("Tailscale executable not found")
                recovery_steps.append("reinstall_required")
                return False, recovery_steps
            
            # Step 3: Check and start service
            service_status = self.check_service_status()
            self.logger.debug(f"Service status: {service_status}")
            
            if service_status in ["stopped", "not_found"]:
                recovery_steps.append("start_service")
                if not self.start_service():
                    self.logger.error("Failed to start Tailscale service")
                    return False, recovery_steps
            
            # Step 4: Check Tailscale status after service start
            time.sleep(2)
            current_status = self.get_tailscale_status()
            
            # Step 5: Authenticate if needed
            backend_state = current_status.get("BackendState", "Unknown")
            
            if backend_state in ["NeedsLogin", "NoState", "Stopped"]:
                recovery_steps.append("authenticate")
                if not self.authenticate_tailscale():
                    self.logger.error("Failed to authenticate Tailscale")
                    return False, recovery_steps
            
            # Step 6: Final status check
            time.sleep(3)
            final_status = self.get_tailscale_status()
            final_backend_state = final_status.get("BackendState", "Unknown")
            
            if final_backend_state == "Running":
                self.logger.info("Recovery successful - Tailscale is running")
                self.consecutive_failures = 0
                self.last_successful_check = datetime.now()
                recovery_steps.append("success")
                return True, recovery_steps
            else:
                self.logger.warning(f"Recovery incomplete - Backend state: {final_backend_state}")
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
            
            # Determine if recovery is needed
            recovery_conditions = [
                health_status["tailscale_status"] in ["NeedsLogin", "NoState", "Stopped", "error", "timeout"],
                health_status["service_status"] in ["stopped", "not_found"],
                not health_status["auth_valid"] and health_status["network_connectivity"]
            ]
            
            health_status["recovery_needed"] = any(recovery_conditions)
            
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
                    
                    self.logger.warning(f"Recovery needed (failure #{self.consecutive_failures})")
                    
                    # Exponential backoff for consecutive failures
                    if self.consecutive_failures > 1:
                        backoff_delay = min(300, Config.RECONNECT_DELAY * (2 ** (self.consecutive_failures - 1)))
                        self.logger.info(f"Applying backoff delay: {backoff_delay} seconds")
                        time.sleep(backoff_delay)
                    
                    # Attempt recovery
                    success, recovery_steps = self.recovery_procedure(health_status)
                    
                    if success:
                        self.logger.info(f"Recovery successful after {recovery_steps}")
                        self.consecutive_failures = 0
                        self.last_successful_check = datetime.now()
                    else:
                        self.logger.error(f"Recovery failed: {recovery_steps}")
                        
                        # If we've had too many consecutive failures, increase check interval
                        if self.consecutive_failures >= Config.MAX_RETRIES:
                            self.logger.error(f"Max retries ({Config.MAX_RETRIES}) exceeded - increasing check interval")
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
    
    # Default: run interactive mode
    print("ATT Tailscale Watchdog")
    print("Usage:")
    print("  python att_tailscale_watchdog.py service [auth_key]  - Run as service")
    print("  python att_tailscale_watchdog.py setup <auth_key>    - Setup auth key")
    print("  python att_tailscale_watchdog.py test               - Test current status")

if __name__ == "__main__":
    main()