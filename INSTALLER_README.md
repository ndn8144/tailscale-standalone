# Tailscale Standalone Installer System

A comprehensive installer/uninstaller system for Tailscale Standalone with silent installation and full standalone installer modes.

## Overview

This installer system provides:
- **Silent Installer**: Command-line installation for automated deployment
- **Full Standalone Installer**: Complete Tailscale setup with embedded MSI and watchdog service

## Features

### Silent Installer
- ✅ Command-line installation without GUI
- ✅ Configurable installation directory
- ✅ Shortcut creation options
- ✅ Service management
- ✅ Registry cleanup
- ✅ Complete uninstallation support

### Full Standalone Installer
- ✅ Embedded Tailscale MSI
- ✅ Watchdog service with auto-recovery
- ✅ Centralized logging system
- ✅ Windows Scheduled Task integration
- ✅ Auto-reconnect capabilities
- ✅ Chocolatey package manager integration

## File Structure

```
src/
├── silent_installer.py       # Silent installation logic
├── windows_installer_builder.py  # Full standalone builder
└── config.py                 # Configuration settings

builds/
├── dist/                     # Built executables
│   └── TailscaleInstaller-*.exe  # Standalone installer
└── build_summary_*.json      # Build information

build_installer.py            # Main build script
test_installer.py             # Test suite
```

## Quick Start

### 1. Build the Installer

```bash
# Build all installers
python build_installer.py

# Build standalone installer only
python src/windows_installer_builder.py
```

### 2. Run Standalone Installer

```bash
# Interactive mode (default)
TailscaleInstaller-YYYYMMDD-HHMMSS.exe

# Silent mode
TailscaleInstaller-YYYYMMDD-HHMMSS.exe --silent

# Silent with options
TailscaleInstaller-YYYYMMDD-HHMMSS.exe --silent --install-dir "C:\Custom\Path" --no-desktop-shortcut
```

### 3. Test the Installer

```bash
# Run test suite
python test_installer.py
```

## Usage Guide

### Interactive Mode

1. **Launch**: Double-click `TailscaleInstaller-YYYYMMDD-HHMMSS.exe`
2. **Follow Prompts**: The installer will guide you through the process
3. **Monitor Progress**: Watch console output for status messages

### Silent Mode

```cmd
# Basic installation
TailscaleInstaller-YYYYMMDD-HHMMSS.exe --silent

# Custom installation directory
TailscaleInstaller-YYYYMMDD-HHMMSS.exe --silent --install-dir "C:\Custom\Tailscale"

# No shortcuts
TailscaleInstaller-YYYYMMDD-HHMMSS.exe --silent --no-shortcuts

# No desktop shortcut only
TailscaleInstaller-YYYYMMDD-HHMMSS.exe --silent --no-desktop-shortcut
```

### Uninstallation

The installer automatically creates an uninstaller at:
`<Installation Directory>\uninstall.exe`

You can also uninstall through:
- Windows Add/Remove Programs
- Start Menu shortcut (if created)

## Installation Process

### GUI Installation Steps

1. **Prerequisites Check**
   - Verify administrator privileges
   - Check Windows version compatibility
   - Verify disk space availability

2. **Directory Creation**
   - Create installation directory
   - Set appropriate permissions

3. **File Copying**
   - Copy application files
   - Create configuration files
   - Set up logging directory

4. **Shortcut Creation**
   - Create Start Menu shortcut
   - Create Desktop shortcut (if enabled)
   - Configure shortcut properties

5. **Registry Integration**
   - Create Windows registry entries
   - Enable Add/Remove Programs integration
   - Set up uninstaller information

6. **Uninstaller Creation**
   - Generate uninstaller executable
   - Configure cleanup procedures

### Silent Installation Steps

Same as GUI installation but without user interaction:
- Uses default settings or command-line parameters
- Provides console output for monitoring
- Returns appropriate exit codes

## Configuration

### Installation Directory
- **Default**: `C:\Program Files\Tailscale Standalone`
- **Custom**: Specify via `--install-dir` parameter
- **Requirements**: Must be writable by administrator

### Shortcuts
- **Start Menu**: Always created (unless `--no-shortcuts` specified)
- **Desktop**: Created by default (disable with `--no-desktop-shortcut`)
- **Location**: 
  - Start Menu: `%APPDATA%\Microsoft\Windows\Start Menu\Programs\`
  - Desktop: `%USERPROFILE%\Desktop\`

### Registry Entries
- **Key**: `HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\TailscaleStandalone`
- **Values**: DisplayName, DisplayVersion, Publisher, InstallLocation, UninstallString

## Error Handling

### Common Issues

1. **Administrator Privileges Required**
   - **Solution**: Right-click installer and select "Run as administrator"
   - **Silent Mode**: Run Command Prompt as administrator

2. **Installation Directory Access Denied**
   - **Solution**: Choose a different directory or run as administrator
   - **Check**: Ensure directory is not in use by another process

3. **Shortcut Creation Failed**
   - **Solution**: Check user profile permissions
   - **Fallback**: Installer continues without shortcuts

4. **Registry Access Denied**
   - **Solution**: Run as administrator
   - **Impact**: Uninstaller may not appear in Add/Remove Programs

### Error Codes

- **0**: Success
- **1**: General error
- **2**: Administrator privileges required
- **3**: Installation directory error
- **4**: File copy error
- **5**: Registry error

## Development

### Building from Source

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run Tests**
   ```bash
   python test_installer.py
   ```

3. **Build Installer**
   ```bash
   python build_installer.py
   ```

### Customization

#### Modify Installation Directory
Edit `src/installer_gui.py`:
```python
self.default_install_dir = Path("C:/Your/Custom/Path")
```

#### Add Custom Files
Modify `copy_application_files()` method in both `installer_gui.py` and `silent_installer.py`.

#### Customize Registry Entries
Update `create_registry_entries()` method in both installer files.

## Requirements

### System Requirements
- **OS**: Windows 10 or later
- **Architecture**: x64
- **Privileges**: Administrator (for installation)
- **Disk Space**: 50+ MB free space
- **Python**: 3.7+ (for building)

### Dependencies
- `tkinter` (GUI framework)
- `winshell` (shortcut creation)
- `pyinstaller` (executable building)
- `winreg` (registry access)
- `ctypes` (system functions)

## Security Considerations

- **Administrator Privileges**: Required for system-level operations
- **Registry Access**: Limited to uninstaller entries
- **File Permissions**: Respects Windows security model
- **Code Signing**: Consider signing executables for production use

## Troubleshooting

### Installation Issues

1. **Check Administrator Privileges**
   ```cmd
   whoami /groups | findstr "S-1-5-32-544"
   ```

2. **Verify Installation Directory**
   ```cmd
   dir "C:\Program Files\Tailscale Standalone"
   ```

3. **Check Registry Entries**
   ```cmd
   reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\TailscaleStandalone"
   ```

### Uninstallation Issues

1. **Manual Cleanup**
   - Delete installation directory
   - Remove shortcuts manually
   - Clean registry entries

2. **Registry Cleanup**
   ```cmd
   reg delete "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\TailscaleStandalone" /f
   ```

## Support

For technical support:
1. Check installation logs
2. Verify system requirements
3. Test with administrator privileges
4. Contact IT administrator

## License

This installer system is part of the Tailscale Standalone project. Please refer to the main project license for usage terms.
