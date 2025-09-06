"""
Main build script for Tailscale Standalone Installer
Creates silent installer and full standalone installer
"""

import os
import sys
import subprocess
import json
from pathlib import Path
from datetime import datetime

# Add src directory to path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from windows_installer_builder import WindowsInstallerBuilder

class MainInstallerBuilder:
    def __init__(self):
        self.build_dir = Path("builds")
        self.build_dir.mkdir(exist_ok=True)
        
    def build_all_installers(self):
        """Build all types of installers"""
        print("=" * 80)
        print("TAILSCALE STANDALONE INSTALLER BUILDER")
        print("=" * 80)
        print("Building installers:")
        print("  1. Silent Installer (command-line only)")
        print("  2. Full Standalone Installer (with Tailscale MSI)")
        print("=" * 80)
        
        results = {}
        
        try:
            # Build Full Standalone Installer (with Tailscale MSI)
            print("\\n[1/2] Building Full Standalone Installer...")
            windows_builder = WindowsInstallerBuilder()
            standalone_exe, standalone_info = windows_builder.build_standalone_installer()
            results["standalone_installer"] = {
                "success": True,
                "path": str(standalone_exe),
                "info": standalone_info
            }
            print("[OK] Full Standalone Installer completed")
            
        except Exception as e:
            print(f"[ERROR] Full Standalone Installer failed: {e}")
            results["standalone_installer"] = {
                "success": False,
                "error": str(e)
            }
        
        # Create comprehensive build summary
        self.create_build_summary(results)
        
        return results
    
    def create_build_summary(self, results):
        """Create comprehensive build summary"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary_file = self.build_dir / f"build_summary_{timestamp}.json"
        
        summary = {
            "build_time": datetime.now().isoformat(),
            "installers": results,
            "total_installers": len(results),
            "successful_builds": sum(1 for r in results.values() if r["success"]),
            "failed_builds": sum(1 for r in results.values() if not r["success"]),
            "usage_guide": {
                "gui_installer": {
                    "description": "GUI-based installer with wizard interface",
                    "usage": "Double-click installer_gui.exe or run with --silent flag",
                    "features": [
                        "Installation directory selection",
                        "Shortcut creation options",
                        "Progress tracking",
                        "Error handling",
                        "Automatic uninstaller creation"
                    ]
                },
                "standalone_installer": {
                    "description": "Full installer with embedded Tailscale MSI and watchdog service",
                    "usage": "Run as administrator - includes complete Tailscale setup",
                    "features": [
                        "Embedded Tailscale MSI",
                        "Watchdog service with auto-recovery",
                        "Centralized logging",
                        "Windows Scheduled Task integration",
                        "Auto-reconnect capabilities"
                    ]
                }
            }
        }
        
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print("\\n" + "=" * 80)
        print("BUILD SUMMARY")
        print("=" * 80)
        print(f"Total Installers: {summary['total_installers']}")
        print(f"Successful: {summary['successful_builds']}")
        print(f"Failed: {summary['failed_builds']}")
        print(f"Summary File: {summary_file}")
        
        for installer_type, result in results.items():
            if result["success"]:
                print(f"\\n[OK] {installer_type.upper()}:")
                print(f"  Path: {result['path']}")
                if 'info' in result and 'exe_size_mb' in result['info']:
                    print(f"  Size: {result['info']['exe_size_mb']} MB")
            else:
                print(f"\\n[ERROR] {installer_type.upper()}: {result['error']}")
        
        print("\\n" + "=" * 80)
        print("USAGE GUIDE")
        print("=" * 80)
        
        if results.get("standalone_installer", {}).get("success"):
            print("\\n[STANDALONE INSTALLER]")
            print("  File: TailscaleInstaller-YYYYMMDD-HHMMSS.exe")
            print("  Usage: Run as administrator")
            print("  Features: Complete Tailscale setup with watchdog service")
            print("  Silent Mode: Built-in silent installation support")
        
        print("\\n" + "=" * 80)
        print("DEPLOYMENT INSTRUCTIONS")
        print("=" * 80)
        print("1. Use the Standalone Installer for complete Tailscale setup")
        print("2. Test on a VM before deploying to production")
        print("3. Distribute via secure channels")
        print("4. Ensure users run as administrator")
        print("5. Monitor installation logs for issues")
        print("6. Silent installation: Run with --silent flag for automated deployment")
        
        return summary_file

def main():
    """Main entry point"""
    builder = MainInstallerBuilder()
    
    try:
        results = builder.build_all_installers()
        
        successful = sum(1 for r in results.values() if r["success"])
        total = len(results)
        
        if successful == total:
            print("\\n[SUCCESS] ALL INSTALLERS BUILT SUCCESSFULLY!")
        elif successful > 0:
            print(f"\\n[PARTIAL] {successful}/{total} INSTALLERS BUILT SUCCESSFULLY!")
        else:
            print("\\n[ERROR] ALL INSTALLERS FAILED!")
            return 1
            
        return 0
        
    except Exception as e:
        print(f"\\n[ERROR] Build process failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
