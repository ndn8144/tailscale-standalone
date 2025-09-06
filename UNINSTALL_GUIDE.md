# Tailscale Standalone - Complete Uninstall Guide

This guide provides multiple methods to completely uninstall Tailscale Standalone and all its components from Windows systems.

## 🚨 Important Notes

- **Run as Administrator**: All uninstall methods require Administrator privileges
- **Complete Removal**: These scripts remove ALL Tailscale components including:
  - Tailscale MSI installation
  - Watchdog service and scheduled tasks
  - Registry entries
  - Application files and data
  - Shortcuts (Start Menu, Desktop)
  - Log files (optional)

## 📋 Uninstall Methods

### Method 1: Simple Batch File (Recommended)

**File**: `uninstall_tailscale_simple.cmd`

**Usage**:
```cmd
# Right-click and "Run as administrator"
uninstall_tailscale_simple.cmd
```

**Features**:
- ✅ No additional dependencies
- ✅ Complete removal in 8 steps
- ✅ User-friendly progress display
- ✅ Automatic administrator check

### Method 2: PowerShell Script (Advanced)

**File**: `uninstall_tailscale_complete.ps1`

**Usage**:
```powershell
# Run as Administrator
.\uninstall_tailscale_complete.ps1

# With options
.\uninstall_tailscale_complete.ps1 -Force -RemoveData -Quiet
```

**Options**:
- `-Force`: Force removal of all components including Chocolatey
- `-RemoveData`: Remove all data including logs
- `-Quiet`: Minimal output mode

**Features**:
- ✅ Detailed logging to `%TEMP%\tailscale_uninstall.log`
- ✅ Advanced error handling
- ✅ Configurable removal options
- ✅ Verification and cleanup

### Method 3: Python Script (Developer)

**File**: `src/complete_uninstaller.py`

**Usage**:
```cmd
# Run as Administrator
python src/complete_uninstaller.py

# With options
python src/complete_uninstaller.py --remove-data --quiet
```

**Options**:
- `--remove-data`: Remove all data including logs
- `--quiet`: Quiet mode with minimal output

**Features**:
- ✅ Programmatic control
- ✅ Detailed logging
- ✅ Integration with existing codebase
- ✅ Configurable removal options

### Method 4: Batch File with PowerShell

**File**: `uninstall_tailscale.bat`

**Usage**:
```cmd
# Right-click and "Run as administrator"
uninstall_tailscale.bat
```

**Features**:
- ✅ Automatic privilege escalation
- ✅ Runs PowerShell script
- ✅ User-friendly interface

## 🔧 What Gets Removed

### Core Components
- **Tailscale MSI**: Complete MSI installation via Windows Add/Remove Programs
- **Scheduled Task**: `ATT_Tailscale_Watchdog` task
- **Services**: Tailscale Windows service
- **Processes**: All tailscale.exe and tailscaled.exe processes

### Files and Directories
- `C:\Program Files\Tailscale Standalone\` - Application files
- `C:\ProgramData\ATT\` - Watchdog service and configuration
- `C:\Program Files\Tailscale\` - Tailscale installation
- Log files (optional based on method)

### Registry Entries
- `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\TailscaleStandalone`
- `HKLM\SOFTWARE\Tailscale`
- `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\TrayNotify`

### Shortcuts
- Start Menu: `Tailscale Standalone.lnk`
- Desktop: `Tailscale Standalone.lnk`

### Optional Components
- **Chocolatey packages**: Python and other packages (if installed)
- **Temporary files**: All tailscale-related temp files

## 🚀 Quick Start

### For End Users
1. Download `uninstall_tailscale_simple.cmd`
2. Right-click → "Run as administrator"
3. Follow the on-screen prompts
4. Restart computer if prompted

### For IT Administrators
1. Use PowerShell script for automated deployment:
```powershell
# Silent uninstall
.\uninstall_tailscale_complete.ps1 -Force -RemoveData -Quiet
```

2. Or use Python script for integration:
```cmd
python src/complete_uninstaller.py --remove-data --quiet
```

## 🔍 Verification

After running any uninstall method, verify complete removal:

### Check Processes
```cmd
tasklist | findstr tailscale
```
Should return no results.

### Check Services
```cmd
sc query Tailscale
```
Should return "The specified service does not exist as an installed service."

### Check Directories
```cmd
dir "C:\Program Files\Tailscale"
dir "C:\ProgramData\ATT"
```
Should return "The system cannot find the path specified."

### Check Registry
```cmd
reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\TailscaleStandalone"
```
Should return "The system cannot find the specified registry key or value."

## 📝 Log Files

All methods create detailed log files:

- **PowerShell**: `%TEMP%\tailscale_uninstall.log`
- **Python**: `%TEMP%\tailscale_complete_uninstall.log`

Check these files if uninstallation encounters issues.

## ⚠️ Troubleshooting

### Common Issues

1. **"Access Denied" errors**
   - Ensure running as Administrator
   - Close any Tailscale applications first

2. **"File in use" errors**
   - Restart computer and try again
   - Use Task Manager to end tailscale processes

3. **Registry errors**
   - Some registry keys may be protected
   - This is normal and won't affect functionality

4. **Scheduled task not found**
   - Task may have been manually removed
   - This is not an error

### Manual Cleanup

If automated scripts fail, manually remove:

1. **Stop services**:
   ```cmd
   sc stop Tailscale
   sc delete Tailscale
   ```

2. **Remove directories**:
   ```cmd
   rmdir /s /q "C:\Program Files\Tailscale"
   rmdir /s /q "C:\ProgramData\ATT"
   ```

3. **Remove registry keys**:
   ```cmd
   reg delete "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\TailscaleStandalone" /f
   ```

## 🔄 Reinstallation

After complete uninstallation, you can reinstall Tailscale Standalone using the original installer. The system will be clean and ready for a fresh installation.

## 📞 Support

If you encounter issues not covered in this guide:

1. Check the log files for detailed error messages
2. Verify Administrator privileges
3. Try restarting the computer and running the uninstaller again
4. Contact IT support with the log file contents

---

**Note**: These uninstallers are designed to completely remove the Tailscale Standalone system. Use with caution in production environments and always test first.
