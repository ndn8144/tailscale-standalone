# Enhanced Installer with Tailscale Cleanup

## Overview

The enhanced installer (`Install_IPG&V2rayN_Enhanced.bat`) is an improved version of the original Google Drive downloader that includes comprehensive Tailscale uninstallation and system cleanup functionality.

## New Features

### 1. Silent Tailscale Uninstallation
- **Complete MSI removal**: Automatically detects and removes Tailscale MSI installations
- **Process termination**: Safely stops all Tailscale processes and services
- **Registry cleanup**: Removes all Tailscale-related registry entries
- **Silent operation**: All uninstallation steps run silently without user prompts

### 2. Watchdog Process Management
- **Process detection**: Identifies and terminates ATT Tailscale watchdog processes
- **Python process cleanup**: Removes Python processes running watchdog scripts
- **Scheduled task removal**: Deletes ATT_Tailscale_Watchdog scheduled tasks
- **Service cleanup**: Stops and removes Tailscale services

### 3. Log and Data Cleanup
- **Selective log removal**: Option to clean Tailscale-specific logs while preserving others
- **Temporary file cleanup**: Removes all temporary files related to Tailscale
- **Cache cleanup**: Clears Python pip cache and related temporary data
- **Configuration cleanup**: Removes auth keys and configuration files

### 4. Directory Management
- **C:/ATT directory handling**: Configurable removal or selective cleanup
- **Preserve important data**: Option to keep logs while removing application files
- **Complete removal**: Full directory removal when specified
- **Verification**: Checks for successful removal and reports any remaining items

## Configuration Options

The script includes several configurable settings at the top:

```batch
REM Tailscale cleanup settings
set "CLEANUP_LOGS=1"        REM 1=Remove logs, 0=Keep logs
set "REMOVE_ATT_DIR=1"      REM 1=Remove entire ATT dir, 0=Selective cleanup
set "SILENT_UNINSTALL=1"    REM 1=Silent mode, 0=Interactive mode
```

## Usage

### Basic Usage
```cmd
Install_IPG&V2rayN_Enhanced.bat
```

The script will:
1. Auto-elevate to Administrator privileges
2. Perform silent Tailscale uninstallation and cleanup
3. Download IP-Guard and v2rayN files
4. Perform final system cleanup
5. Verify removal and report results

### Administrator Requirements
The script requires Administrator privileges and will automatically request elevation if not already running as Administrator.

## Process Flow

### Step 1: Tailscale Uninstallation
- Stop all Tailscale processes and services
- Remove scheduled tasks (ATT_Tailscale_Watchdog)
- Uninstall Tailscale MSI packages
- Clean registry entries
- Remove application files and directories

### Step 2: File Downloads
- Create target directories
- Download IP-Guard setup file
- Download v2rayN archive
- Verify file integrity

### Step 3: Final Cleanup
- Clean temporary files
- Verify successful removal
- Restart Windows Explorer
- Report completion status

## Cleanup Details

### Processes Terminated
- `tailscale.exe`
- `tailscaled.exe` 
- `att_tailscale_watchdog.exe`
- Python processes running watchdog scripts

### Services Stopped
- Tailscale Windows service
- Any related background services

### Registry Entries Removed
- `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\TailscaleStandalone`
- `HKLM\SOFTWARE\Tailscale`
- `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\TrayNotify`
- `HKCU\SOFTWARE\Tailscale`

### Files and Directories Cleaned
- `C:\Program Files\Tailscale\` (complete removal)
- `C:\ProgramData\ATT\` (configurable - complete or selective)
- Tailscale-related logs in ATT directory
- Watchdog Python scripts
- Configuration and auth key files
- Temporary files in `%TEMP%`
- Desktop and Start Menu shortcuts

### Scheduled Tasks Removed
- `ATT_Tailscale_Watchdog`
- Any other Tailscale or ATT related tasks

## Error Handling

The enhanced script includes comprehensive error handling:
- Continues operation even if some cleanup steps fail
- Logs warnings for non-critical failures
- Provides detailed status reporting
- Verifies removal and reports any remaining components

## Verification

After cleanup, the script performs verification checks:
- Scans for remaining Tailscale processes
- Checks for leftover directories
- Reports any items that couldn't be removed
- Provides success confirmation when cleanup is complete

## Compatibility

- **Windows 10/11**: Full compatibility
- **Windows Server 2019+**: Full compatibility
- **PowerShell**: Uses PowerShell for advanced operations
- **Administrator Rights**: Required for complete functionality

## Safety Features

- **Backup preservation**: Option to keep logs and important data
- **Selective cleanup**: Configurable removal levels
- **Process verification**: Ensures processes are safely terminated
- **Registry safety**: Only removes specific Tailscale entries
- **Rollback information**: Maintains logs for troubleshooting

## Troubleshooting

If the script encounters issues:
1. Ensure you're running as Administrator
2. Check Windows Event Logs for service-related errors
3. Manually verify process termination if needed
4. Review the script's output for specific error messages
5. Use the standalone uninstaller if the integrated cleanup fails

## Related Files

- `Install_IPG&V2rayN_Enhanced.bat` - Main enhanced installer
- `complete_uninstaller.py` - Python-based complete uninstaller
- `uninstall_tailscale_complete.ps1` - PowerShell complete uninstaller
- `att_tailscale_watchdog.py` - Original watchdog script (will be removed)

## Security Considerations

- Script requires Administrator privileges for complete functionality
- Registry modifications are limited to Tailscale-specific entries
- Process termination is performed safely with proper timeouts
- No sensitive data is logged or exposed during cleanup
- Temporary files are securely deleted
