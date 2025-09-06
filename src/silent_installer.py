"""
Silent installer for Tailscale Standalone
Provides command-line installation without GUI
"""

import os
import sys
import shutil
import winreg
import subprocess
import json
import argparse
from pathlib import Path
from datetime import datetime
import ctypes

class SilentInstaller:
    def __init__(self):
        self.app_name = "Tailscale Standalone"
        self.app_version = "1.0.0"
        self.app_publisher = "ATT"
        self.registry_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\TailscaleStandalone"
        
    def is_admin(self):
        """Check if running as administrator"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
            
    def log(self, message, level="INFO"):
        """Log message to console"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
        
    def install(self, install_dir=None, create_shortcuts=True, create_desktop_shortcut=True):
        """Perform silent installation"""
        try:
            if not self.is_admin():
                self.log("Administrator privileges required", "ERROR")
                return False
                
            # Set default installation directory
            if not install_dir:
                install_dir = Path("C:/Program Files/Tailscale Standalone")
            else:
                install_dir = Path(install_dir)
                
            self.log(f"Starting silent installation to: {install_dir}")
            
            # Step 1: Create installation directory
            self.log("Creating installation directory...")
            install_dir.mkdir(parents=True, exist_ok=True)
            
            # Step 2: Copy application files
            self.log("Copying application files...")
            self.copy_application_files(install_dir)
            
            # Step 3: Create shortcuts
            if create_shortcuts:
                self.log("Creating shortcuts...")
                self.create_shortcuts(install_dir, create_desktop_shortcut)
                
            # Step 4: Create registry entries
            self.log("Creating registry entries...")
            self.create_registry_entries(install_dir)
            
            # Step 5: Create uninstaller
            self.log("Creating uninstaller...")
            self.create_uninstaller(install_dir)
            
            self.log("Silent installation completed successfully!", "SUCCESS")
            return True
            
        except Exception as e:
            self.log(f"Silent installation failed: {e}", "ERROR")
            return False
            
    def uninstall(self, remove_data=False):
        """Perform silent uninstallation"""
        try:
            if not self.is_admin():
                self.log("Administrator privileges required", "ERROR")
                return False
                
            # Get installation directory from registry
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, self.registry_key)
                install_dir = Path(winreg.QueryValueEx(key, "InstallLocation")[0])
                winreg.CloseKey(key)
            except:
                self.log("Installation not found in registry", "ERROR")
                return False
                
            self.log(f"Starting silent uninstallation from: {install_dir}")
            
            # Step 1: Stop services
            self.log("Stopping services...")
            self.stop_tailscale_services()
            
            # Step 2: Remove shortcuts
            self.log("Removing shortcuts...")
            self.remove_shortcuts()
            
            # Step 3: Remove registry entries
            self.log("Removing registry entries...")
            self.remove_registry_entries()
            
            # Step 4: Remove application files
            self.log("Removing application files...")
            self.remove_application_files(install_dir, remove_data)
            
            self.log("Silent uninstallation completed successfully!", "SUCCESS")
            return True
            
        except Exception as e:
            self.log(f"Silent uninstallation failed: {e}", "ERROR")
            return False
            
    def copy_application_files(self, install_dir):
        """Copy application files to installation directory"""
        # Create main application files
        app_exe = install_dir / "tailscale_standalone.exe"
        
        # For demo purposes, create a simple executable
        # In real implementation, this would copy the actual Tailscale files
        with open(app_exe, 'w') as f:
            f.write("#!/usr/bin/env python\n")
            f.write("print('Tailscale Standalone Application')\n")
            f.write("input('Press Enter to continue...')\n")
            
        # Create config directory
        config_dir = install_dir / "config"
        config_dir.mkdir(exist_ok=True)
        
        # Create logs directory
        logs_dir = install_dir / "logs"
        logs_dir.mkdir(exist_ok=True)
        
        # Create sample config file
        config_file = config_dir / "config.json"
        config_data = {
            "app_name": self.app_name,
            "version": self.app_version,
            "install_time": datetime.now().isoformat(),
            "install_dir": str(install_dir)
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f, indent=2)
            
    def create_shortcuts(self, install_dir, create_desktop_shortcut=True):
        """Create Start Menu and Desktop shortcuts"""
        app_exe = install_dir / "tailscale_standalone.exe"
        
        # Create Start Menu shortcut
        start_menu_dir = Path(os.environ.get('APPDATA', '')) / "Microsoft/Windows/Start Menu/Programs"
        start_menu_shortcut = start_menu_dir / f"{self.app_name}.lnk"
        self.create_shortcut(str(app_exe), str(start_menu_shortcut), 
                           f"Launch {self.app_name}")
                           
        if create_desktop_shortcut:
            # Create Desktop shortcut
            desktop_dir = Path(os.environ.get('USERPROFILE', '')) / "Desktop"
            desktop_shortcut = desktop_dir / f"{self.app_name}.lnk"
            self.create_shortcut(str(app_exe), str(desktop_shortcut), 
                               f"Launch {self.app_name}")
                               
    def create_shortcut(self, target_path, shortcut_path, description):
        """Create a Windows shortcut"""
        try:
            import winshell
            shortcut = winshell.shortcut(shortcut_path)
            shortcut.path = target_path
            shortcut.description = description
            shortcut.write()
        except ImportError:
            # Fallback method using PowerShell
            ps_script = f'''
            $WshShell = New-Object -comObject WScript.Shell
            $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
            $Shortcut.TargetPath = "{target_path}"
            $Shortcut.Description = "{description}"
            $Shortcut.Save()
            '''
            subprocess.run(["powershell", "-Command", ps_script], 
                         capture_output=True, check=True)
        except Exception as e:
            self.log(f"Warning: Could not create shortcut {shortcut_path}: {e}", "WARNING")
            
    def create_registry_entries(self, install_dir):
        """Create Windows registry entries for uninstaller"""
        try:
            # Create uninstall registry key
            key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, self.registry_key)
            
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, self.app_name)
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, self.app_version)
            winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, self.app_publisher)
            winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(install_dir))
            winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, 
                            str(install_dir / "uninstall.exe"))
            winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, 
                            str(install_dir / "tailscale_standalone.exe"))
            winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, 50000)  # 50MB
            
            winreg.CloseKey(key)
        except Exception as e:
            self.log(f"Warning: Could not create registry entries: {e}", "WARNING")
            
    def create_uninstaller(self, install_dir):
        """Create uninstaller executable"""
        uninstaller_path = install_dir / "uninstall.exe"
        
        # Create a simple uninstaller script
        uninstaller_code = f'''
import sys
import os
import shutil
import winreg
from pathlib import Path

def uninstall():
    install_dir = Path("{install_dir}")
    registry_key = r"{self.registry_key}"
    
    try:
        # Remove shortcuts
        start_menu_shortcut = Path(os.environ.get('APPDATA', '')) / "Microsoft/Windows/Start Menu/Programs/{self.app_name}.lnk"
        desktop_shortcut = Path(os.environ.get('USERPROFILE', '')) / "Desktop/{self.app_name}.lnk"
        
        if start_menu_shortcut.exists():
            start_menu_shortcut.unlink()
        if desktop_shortcut.exists():
            desktop_shortcut.unlink()
            
        # Remove registry entries
        try:
            winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, registry_key)
        except:
            pass
            
        # Remove application files
        if install_dir.exists():
            shutil.rmtree(install_dir)
            
        print("Uninstallation completed successfully!")
        
    except Exception as e:
        print(f"Uninstallation failed: {{e}}")
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(uninstall())
'''
        
        # Write uninstaller script
        uninstaller_script = install_dir / "uninstall.py"
        with open(uninstaller_script, 'w') as f:
            f.write(uninstaller_code)
            
        # In a real implementation, you would compile this to an executable
        # For now, just copy the script
        shutil.copy2(uninstaller_script, uninstaller_path)
        
    def stop_tailscale_services(self):
        """Stop Tailscale services"""
        try:
            # Stop Tailscale service
            subprocess.run(["sc", "stop", "Tailscale"], 
                         capture_output=True, check=False)
        except Exception as e:
            self.log(f"Warning: Could not stop Tailscale service: {e}", "WARNING")
            
    def remove_shortcuts(self):
        """Remove Start Menu and Desktop shortcuts"""
        try:
            start_menu_dir = Path(os.environ.get('APPDATA', '')) / "Microsoft/Windows/Start Menu/Programs"
            desktop_dir = Path(os.environ.get('USERPROFILE', '')) / "Desktop"
            
            start_menu_shortcut = start_menu_dir / f"{self.app_name}.lnk"
            desktop_shortcut = desktop_dir / f"{self.app_name}.lnk"
            
            if start_menu_shortcut.exists():
                start_menu_shortcut.unlink()
            if desktop_shortcut.exists():
                desktop_shortcut.unlink()
        except Exception as e:
            self.log(f"Warning: Could not remove shortcuts: {e}", "WARNING")
            
    def remove_registry_entries(self):
        """Remove Windows registry entries"""
        try:
            winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, self.registry_key)
        except Exception as e:
            self.log(f"Warning: Could not remove registry entries: {e}", "WARNING")
            
    def remove_application_files(self, install_dir, remove_data=False):
        """Remove application files"""
        try:
            if install_dir.exists():
                if remove_data:
                    # Remove everything
                    shutil.rmtree(install_dir)
                else:
                    # Remove only application files, keep logs
                    for item in install_dir.iterdir():
                        if item.name != "logs":
                            if item.is_file():
                                item.unlink()
                            elif item.is_dir():
                                shutil.rmtree(item)
        except Exception as e:
            self.log(f"Warning: Could not remove application files: {e}", "WARNING")

def main():
    """Main entry point for silent installer"""
    parser = argparse.ArgumentParser(description="Silent installer for Tailscale Standalone")
    parser.add_argument("--install", action="store_true", help="Install the application")
    parser.add_argument("--uninstall", action="store_true", help="Uninstall the application")
    parser.add_argument("--install-dir", help="Installation directory (default: C:/Program Files/Tailscale Standalone)")
    parser.add_argument("--no-shortcuts", action="store_true", help="Don't create shortcuts")
    parser.add_argument("--no-desktop-shortcut", action="store_true", help="Don't create desktop shortcut")
    parser.add_argument("--remove-data", action="store_true", help="Remove all data during uninstall")
    
    args = parser.parse_args()
    
    installer = SilentInstaller()
    
    if args.install:
        success = installer.install(
            install_dir=args.install_dir,
            create_shortcuts=not args.no_shortcuts,
            create_desktop_shortcut=not args.no_desktop_shortcut
        )
        sys.exit(0 if success else 1)
    elif args.uninstall:
        success = installer.uninstall(remove_data=args.remove_data)
        sys.exit(0 if success else 1)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
