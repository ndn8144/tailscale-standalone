"""
Multi-platform ATT Tailscale installer builder
Supports both Windows and Linux
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import json

# Import builders
from windows_installer_builder import WindowsInstallerBuilder
from linux_installer_builder import LinuxInstallerBuilder

class MultiPlatformBuilder:
    def __init__(self):
        self.build_dir = Path("builds")
        self.build_dir.mkdir(exist_ok=True)
    
    def build_all_platforms(self):
        """Build installers for all platforms"""
        
        print("=" * 70)
        print("ATT TAILSCALE MULTI-PLATFORM BUILDER")
        print("=" * 70)
        print("Building installers for:")
        print("  [WIN] Windows (MSI + Watchdog + Scheduled Task)")
        print("  [LINUX] Linux (Package + Watchdog + Systemd)")
        print("=" * 70)
        
        results = {}
        
        try:
            # Build Windows installer
            print("\\n[WIN] Building Windows installer...")
            windows_builder = WindowsInstallerBuilder()
            windows_exe, windows_info = windows_builder.build_installer()
            results["windows"] = {
                "success": True,
                "path": str(windows_exe),
                "info": windows_info
            }
            print("[OK] Windows installer completed")
            
        except Exception as e:
            print(f"[ERROR] Windows build failed: {e}")
            results["windows"] = {
                "success": False,
                "error": str(e)
            }
        
        try:
            # Build Linux installer
            print("\\n[LINUX] Building Linux installer...")
            linux_builder = LinuxInstallerBuilder()
            linux_package, linux_info = linux_builder.build_linux_installer()
            results["linux"] = {
                "success": True,
                "path": str(linux_package),
                "info": linux_info
            }
            print("[OK] Linux installer completed")
            
        except Exception as e:
            print(f"[ERROR] Linux build failed: {e}")
            results["linux"] = {
                "success": False,
                "error": str(e)
            }
        
        # Create summary
        self.create_build_summary(results)
        
        return results
    
    def create_build_summary(self, results):
        """Create build summary"""
        
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        summary_file = self.build_dir / f"build_summary_{timestamp}.json"
        
        summary = {
            "build_time": datetime.now().isoformat(),
            "platforms": results,
            "total_platforms": len(results),
            "successful_builds": sum(1 for r in results.values() if r["success"]),
            "failed_builds": sum(1 for r in results.values() if not r["success"])
        }
        
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print("\\n" + "=" * 70)
        print("BUILD SUMMARY")
        print("=" * 70)
        print(f"Total Platforms: {summary['total_platforms']}")
        print(f"Successful: {summary['successful_builds']}")
        print(f"Failed: {summary['failed_builds']}")
        print(f"Summary: {summary_file}")
        
        for platform, result in results.items():
            if result["success"]:
                print(f"[OK] {platform.upper()}: {result['path']}")
            else:
                print(f"[ERROR] {platform.upper()}: {result['error']}")
        
        print("=" * 70)

if __name__ == "__main__":
    builder = MultiPlatformBuilder()
    results = builder.build_all_platforms()
    
    if all(r["success"] for r in results.values()):
        print("\\n[SUCCESS] ALL PLATFORMS BUILT SUCCESSFULLY!")
    else:
        print("\\n[WARNING] SOME BUILDS FAILED - CHECK ERRORS ABOVE")