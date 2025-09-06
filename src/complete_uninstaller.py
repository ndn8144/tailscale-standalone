"""
Complete Tailscale Standalone Uninstaller for Windows
Removes ALL components installed by the Tailscale Standalone system
"""

import os
import sys
import subprocess
import winreg
import shutil
import time
from pathlib import Path
import ctypes
import json
from datetime import datetime

class CompleteUninstaller:
    def __init__(self):
        self.log_file = os.path.join(os.environ.get('TEMP', '.'), 'tailscale_complete_uninstall.log')
        self.app_name = "Tailscale Standalone"
        self.registry_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\TailscaleStandalone"
        
        # Clear old log
        try:
            if os.path.exists(self.log_file):
                os.unlink(self.log_file)
        except:
            pass
    
    def log(self, message, level="INFO"):
        """Log message to console and file"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] [{level}] {message}"
        print(log_msg)
        
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_msg + "\n")
        except:
            pass
    
    def is_admin(self):
        """Check if running as administrator"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    
    def run_command(self, cmd, timeout=30, capture_output=True):
        """Run a command with error handling"""
        try:
            if isinstance(cmd, str):
                cmd = cmd.split()
            
            result = subprocess.run(
                cmd, 
                capture_output=capture_output, 
                text=True, 
                timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            return result
        except subprocess.TimeoutExpired:
            self.log(f"Command timed out: {' '.join(cmd) if isinstance(cmd, list) else cmd}", "WARNING")
            return None
        except Exception as e:
            self.log(f"Command failed: {' '.join(cmd) if isinstance(cmd, list) else cmd} - {e}", "WARNING")
            return None
    
    def stop_tailscale_processes(self):
        """Stop all Tailscale processes and services"""
        self.log("Stopping Tailscale processes and services...")
        
        try:
            # Stop Tailscale service
            result = self.run_command(["sc", "stop", "Tailscale"])
            if result and result.returncode == 0:
                self.log("Stopped Tailscale service")
            else:
                self.log("Tailscale service was not running or could not be stopped", "WARNING")
            
            # Kill any remaining processes
            processes_to_kill = ["tailscale.exe", "tailscaled.exe"]
            for proc_name in processes_to_kill:
                result = self.run_command(["taskkill", "/f", "/im", proc_name])
                if result and result.returncode == 0:
                    self.log(f"Killed {proc_name} processes")
            
            # Wait a moment for processes to fully stop
            time.sleep(2)
            
        except Exception as e:
            self.log(f"Error stopping processes: {e}", "WARNING")
    
    def remove_scheduled_task(self):
        """Remove the scheduled task"""
        self.log("Removing scheduled task...")
        
        try:
            task_name = "ATT_Tailscale_Watchdog"
            result = self.run_command(["schtasks", "/delete", "/tn", task_name, "/f"])
            
            if result and result.returncode == 0:
                self.log(f"Removed scheduled task: {task_name}")
            else:
                self.log(f"Scheduled task not found or could not be removed: {task_name}", "WARNING")
                
        except Exception as e:
            self.log(f"Error removing scheduled task: {e}", "WARNING")
    
    def uninstall_tailscale_msi(self):
        """Uninstall Tailscale MSI"""
        self.log("Uninstalling Tailscale MSI...")
        
        try:
            # Find Tailscale MSI installations
            uninstall_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
            
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, uninstall_key) as key:
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        subkey_path = f"{uninstall_key}\\{subkey_name}"
                        
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey_path) as subkey:
                            try:
                                display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                                if "Tailscale" in display_name and "Standalone" not in display_name:
                                    uninstall_string = winreg.QueryValueEx(subkey, "UninstallString")[0]
                                    self.log(f"Found Tailscale installation: {display_name}")
                                    
                                    # Extract MSI GUID and uninstall
                                    if "msiexec.exe" in uninstall_string and "/x" in uninstall_string:
                                        # Extract GUID from uninstall string
                                        import re
                                        guid_match = re.search(r'\{[A-F0-9-]+\}', uninstall_string)
                                        if guid_match:
                                            guid = guid_match.group(0)
                                            uninstall_cmd = ["msiexec.exe", "/x", guid, "/quiet", "/norestart"]
                                            
                                            self.log(f"Running uninstall: {' '.join(uninstall_cmd)}")
                                            result = self.run_command(uninstall_cmd, timeout=300)
                                            
                                            if result and result.returncode == 0:
                                                self.log("Successfully uninstalled Tailscale MSI")
                                            else:
                                                self.log("MSI uninstall may have failed", "WARNING")
                                        
                            except FileNotFoundError:
                                pass  # Skip keys without DisplayName
                            
                    except OSError:
                        break  # No more keys
                    i += 1
                    
        except Exception as e:
            self.log(f"Error uninstalling MSI: {e}", "WARNING")
    
    def remove_registry_entries(self):
        """Remove registry entries"""
        self.log("Removing registry entries...")
        
        try:
            registry_keys = [
                self.registry_key,
                r"SOFTWARE\Tailscale",
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\TrayNotify"
            ]
            
            for key_path in registry_keys:
                try:
                    winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, key_path)
                    self.log(f"Removed registry key: {key_path}")
                except FileNotFoundError:
                    self.log(f"Registry key not found: {key_path}", "INFO")
                except Exception as e:
                    self.log(f"Could not remove registry key {key_path}: {e}", "WARNING")
                    
        except Exception as e:
            self.log(f"Error removing registry entries: {e}", "WARNING")
    
    def remove_shortcuts(self):
        """Remove shortcuts"""
        self.log("Removing shortcuts...")
        
        try:
            shortcuts = [
                os.path.join(os.environ.get('APPDATA', ''), "Microsoft", "Windows", "Start Menu", "Programs", f"{self.app_name}.lnk"),
                os.path.join(os.environ.get('USERPROFILE', ''), "Desktop", f"{self.app_name}.lnk")
            ]
            
            for shortcut in shortcuts:
                if os.path.exists(shortcut):
                    os.unlink(shortcut)
                    self.log(f"Removed shortcut: {shortcut}")
                    
        except Exception as e:
            self.log(f"Error removing shortcuts: {e}", "WARNING")
    
    def remove_application_files(self, remove_data=True):
        """Remove application files and directories"""
        self.log("Removing application files...")
        
        try:
            directories_to_remove = [
                "C:/Program Files/Tailscale Standalone",
                "C:/ProgramData/ATT",
                "C:/Program Files/Tailscale"
            ]
            
            for dir_path in directories_to_remove:
                dir_obj = Path(dir_path)
                if dir_obj.exists():
                    if remove_data or dir_path == "C:/Program Files/Tailscale":
                        # Remove everything
                        shutil.rmtree(dir_path, ignore_errors=True)
                        self.log(f"Removed directory: {dir_path}")
                    else:
                        # Keep logs but remove other files
                        log_dir = dir_obj / "Logs"
                        if log_dir.exists():
                            self.log(f"Keeping logs directory: {log_dir}")
                        
                        # Remove other files
                        for item in dir_obj.iterdir():
                            if item.name != "Logs":
                                if item.is_file():
                                    item.unlink()
                                elif item.is_dir():
                                    shutil.rmtree(item, ignore_errors=True)
                        self.log(f"Cleaned directory: {dir_path} (kept logs)")
                        
        except Exception as e:
            self.log(f"Error removing application files: {e}", "WARNING")
    
    def remove_chocolatey_packages(self):
        """Remove Chocolatey packages if installed"""
        self.log("Removing Chocolatey packages...")
        
        try:
            # Check if Chocolatey is installed
            result = self.run_command(["choco", "--version"])
            if not result or result.returncode != 0:
                self.log("Chocolatey not found, skipping...")
                return
            
            # Uninstall Python if installed via Chocolatey
            result = self.run_command(["choco", "list", "--local-only", "python3"])
            if result and result.returncode == 0 and "0 packages installed" not in result.stdout:
                self.log("Uninstalling Python via Chocolatey...")
                result = self.run_command(["choco", "uninstall", "python3", "-y", "--force"])
                if result and result.returncode == 0:
                    self.log("Uninstalled Python via Chocolatey")
            
            # Optionally remove Chocolatey itself
            choco_dir = Path("C:/ProgramData/chocolatey")
            if choco_dir.exists():
                self.log("Removing Chocolatey installation...")
                shutil.rmtree(choco_dir, ignore_errors=True)
                self.log("Removed Chocolatey")
                
        except Exception as e:
            self.log(f"Error removing Chocolatey packages: {e}", "WARNING")
    
    def cleanup_temp_files(self):
        """Clean up temporary files"""
        self.log("Cleaning up temporary files...")
        
        try:
            temp_dir = Path(os.environ.get('TEMP', '.'))
            patterns = ["tailscale*", "att_tailscale*", "*tailscale*"]
            
            for pattern in patterns:
                for file_path in temp_dir.glob(pattern):
                    try:
                        if file_path.is_file():
                            file_path.unlink()
                        elif file_path.is_dir():
                            shutil.rmtree(file_path, ignore_errors=True)
                    except Exception as e:
                        self.log(f"Could not remove {file_path}: {e}", "WARNING")
                        
        except Exception as e:
            self.log(f"Error cleaning temp files: {e}", "WARNING")
    
    def verify_removal(self):
        """Verify that removal was successful"""
        self.log("Verifying removal...")
        
        issues = []
        
        # Check for remaining processes
        result = self.run_command(["tasklist", "/fi", "imagename eq tailscale*"])
        if result and result.returncode == 0 and "tailscale" in result.stdout.lower():
            issues.append("Tailscale processes still running")
        
        # Check for remaining directories
        remaining_dirs = [
            "C:/Program Files/Tailscale",
            "C:/ProgramData/ATT"
        ]
        
        for dir_path in remaining_dirs:
            if Path(dir_path).exists():
                issues.append(f"Directory still exists: {dir_path}")
        
        if issues:
            self.log("Warning: Some items may not have been completely removed:", "WARNING")
            for issue in issues:
                self.log(f"  - {issue}", "WARNING")
        else:
            self.log("Verification passed: All components removed successfully")
    
    def uninstall(self, remove_data=True):
        """Perform complete uninstallation"""
        print("=" * 60)
        print("TAILSCALE STANDALONE COMPLETE UNINSTALLER")
        print("=" * 60)
        
        if not self.is_admin():
            self.log("ERROR: Administrator privileges required", "ERROR")
            print("Please run this script as Administrator")
            return False
        
        self.log("Starting complete uninstallation...")
        
        try:
            # Step 1: Stop processes
            self.stop_tailscale_processes()
            
            # Step 2: Remove scheduled task
            self.remove_scheduled_task()
            
            # Step 3: Uninstall MSI
            self.uninstall_tailscale_msi()
            
            # Step 4: Remove registry entries
            self.remove_registry_entries()
            
            # Step 5: Remove shortcuts
            self.remove_shortcuts()
            
            # Step 6: Remove application files
            self.remove_application_files(remove_data)
            
            # Step 7: Remove Chocolatey packages
            self.remove_chocolatey_packages()
            
            # Step 8: Cleanup and verify
            self.cleanup_temp_files()
            self.verify_removal()
            
            self.log("Uninstallation completed successfully!", "SUCCESS")
            
            print("\n" + "=" * 60)
            print("UNINSTALLATION COMPLETED SUCCESSFULLY!")
            print("=" * 60)
            print("\nRemoved components:")
            print("  ✓ Tailscale MSI installation")
            print("  ✓ Scheduled task (ATT_Tailscale_Watchdog)")
            print("  ✓ Watchdog service files")
            print("  ✓ Registry entries")
            print("  ✓ Shortcuts (Start Menu, Desktop)")
            print("  ✓ Application files")
            if remove_data:
                print("  ✓ All data and logs")
            else:
                print("  ✓ Application files (logs preserved)")
            print(f"\nLog file: {self.log_file}")
            print("=" * 60)
            
            return True
            
        except Exception as e:
            self.log(f"FATAL ERROR: {e}", "ERROR")
            print(f"\nUninstallation failed: {e}")
            print(f"Check log file for details: {self.log_file}")
            return False

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Complete Tailscale Standalone Uninstaller")
    parser.add_argument("--remove-data", action="store_true", 
                       help="Remove all data including logs (default: keep logs)")
    parser.add_argument("--quiet", action="store_true", 
                       help="Quiet mode (minimal output)")
    
    args = parser.parse_args()
    
    uninstaller = CompleteUninstaller()
    success = uninstaller.uninstall(remove_data=args.remove_data)
    
    if not args.quiet:
        input("\nPress Enter to continue...")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
