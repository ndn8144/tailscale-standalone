# ATT Tailscale Standalone - Inno Setup Integration

Hướng dẫn sử dụng Inno Setup để tạo installer Windows chuẩn cho ATT Tailscale Standalone.

## Tổng quan

Dự án này tích hợp Inno Setup vào quy trình build hiện tại để tạo installer Windows chuyên nghiệp với các tính năng:

- ✅ PyInstaller tạo file .exe standalone
- ✅ Inno Setup đóng gói thành installer Windows chuẩn
- ✅ Shortcut desktop, uninstaller, registry entries
- ✅ PowerShell post-install script
- ✅ Silent installation cho triển khai hàng loạt
- ✅ GitHub Actions CI/CD
- ✅ Ký số installer (tùy chọn)

## Cấu trúc thư mục

```
tailscale-standalone/
├── installers/
│   └── tailscale-standalone.iss    # Inno Setup script chính
├── scripts/
│   └── build_inno.ps1              # PowerShell build script
├── templates/
│   ├── install_script.ps1          # Post-install PowerShell script
│   └── config_template.json        # Cấu hình template
├── .github/workflows/
│   └── release-windows.yml         # GitHub Actions workflow
├── assets/
│   └── app.ico                     # Icon app (tùy chọn)
└── src/
    └── windows_installer_builder.py # Builder chính (đã cập nhật)
```

## Cài đặt yêu cầu

### 1. Inno Setup
```powershell
# Cài đặt qua winget
winget install --id=JRSoftware.InnoSetup -e

# Hoặc tải từ: https://jrsoftware.org/isinfo.php
```

### 2. Python dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment variables
Tạo file `.env`:
```env
TAILSCALE_AUTH_KEY=tskey-auth-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## Sử dụng

### 1. Build local

#### Cách 1: Sử dụng PowerShell script (khuyến nghị)
```powershell
# Build với auth key từ environment
.\scripts\build_inno.ps1

# Build với auth key cụ thể
.\scripts\build_inno.ps1 -AuthKey "tskey-auth-xxx"

# Build silent (không hiển thị UI)
.\scripts\build_inno.ps1 -Silent

# Build với version cụ thể
.\scripts\build_inno.ps1 -Version "1.2.3"

# Clean build (xóa build cũ)
.\scripts\build_inno.ps1 -Clean
```

#### Cách 2: Build thủ công
```powershell
# 1. Build PyInstaller
python src\windows_installer_builder.py

# 2. Build Inno Setup
$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
& $iscc "installers\tailscale-standalone.iss" /DAppVersion="1.0.0" /DAppBinDir="builds\dist"
```

### 2. Build qua GitHub Actions

1. Push code lên GitHub
2. Tạo tag: `git tag v1.0.0 && git push origin v1.0.0`
3. GitHub Actions sẽ tự động build và tạo release

### 3. Triển khai

#### Triển khai thường
1. Gửi file installer cho nhân viên
2. Hướng dẫn: Right-click → "Run as administrator"
3. Installer sẽ tự động cài đặt Tailscale và cấu hình

#### Triển khai silent (hàng loạt)
```cmd
# Silent installation
installer.exe /SILENT

# Silent với log
installer.exe /SILENT /LOG="C:\temp\install.log"

# Silent với custom directory
installer.exe /SILENT /DIR="C:\CustomPath"
```

## Cấu hình

### 1. Auth Key
- **Embedded**: Truyền qua parameter `/DAuthKey=...` cho ISCC
- **User Input**: Để trống, installer sẽ hỏi user nhập key
- **Registry**: Lưu trong `HKLM\Software\ATT Tailscale Standalone\Config`

### 2. Customization
Chỉnh sửa `installers/tailscale-standalone.iss`:
- Tên app, publisher, URL
- Icon, shortcut
- Registry entries
- Custom pages

### 3. Post-install script
Chỉnh sửa `templates/install_script.ps1`:
- Cài đặt Tailscale MSI
- Cấu hình watchdog service
- Tạo scheduled task
- Authentication

## Tính năng

### Inno Setup Features
- ✅ Modern wizard UI
- ✅ Desktop shortcuts
- ✅ Start menu shortcuts
- ✅ Uninstaller
- ✅ Registry entries
- ✅ Environment variables
- ✅ Silent installation
- ✅ Multi-language support
- ✅ Admin privileges check
- ✅ Windows version check

### PowerShell Post-install
- ✅ Download và cài đặt Tailscale MSI
- ✅ Cấu hình watchdog service
- ✅ Tạo Windows Scheduled Task
- ✅ Authentication với auth key
- ✅ Centralized logging
- ✅ Error handling và recovery

### Watchdog Service
- ✅ Auto-reconnect on disconnection
- ✅ Service restart capability
- ✅ Network connectivity monitoring
- ✅ Exponential backoff on failures
- ✅ Centralized logging với rotation

## Troubleshooting

### Build Issues
```powershell
# Kiểm tra Inno Setup
Test-Path "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"

# Kiểm tra Python dependencies
python -c "import PyInstaller"

# Kiểm tra auth key
python -c "import os; print(os.getenv('TAILSCALE_AUTH_KEY'))"
```

### Installation Issues
1. **Administrator required**: Chạy installer với quyền admin
2. **Network issues**: Kiểm tra kết nối internet
3. **Antivirus**: Thêm exception cho installer
4. **Python missing**: Cài đặt Python cho watchdog service

### Logs
- **Installation**: `%TEMP%\att_tailscale_install.log`
- **Watchdog**: `C:\ProgramData\ATT\Logs\att_tailscale.log`
- **Inno Setup**: `%TEMP%\Setup Log yyyy-mm-dd #xxx.txt`

## Security

### Auth Key Management
- Sử dụng ephemeral auth keys
- Rotate keys thường xuyên
- Không commit keys vào git
- Sử dụng GitHub Secrets cho CI/CD

### Code Signing (tùy chọn)
```ini
; Trong tailscale-standalone.iss
SignTool=your_signtool_profile
SignedUninstaller=yes
```

## CI/CD

### GitHub Actions
- Tự động build khi push tag
- Tạo GitHub Release
- Upload installer artifacts
- Test silent installation

### Secrets cần thiết
- `TAILSCALE_AUTH_KEY`: Auth key cho Tailscale
- `GITHUB_TOKEN`: Tự động có sẵn

## Advanced Usage

### Custom Configuration
Tạo file `config.json` tùy chỉnh:
```json
{
  "tailscale": {
    "advertise_routes": ["192.168.1.0/24"],
    "advertise_tags": ["tag:employee", "tag:laptop"]
  },
  "watchdog": {
    "check_interval": 60,
    "max_retries": 10
  }
}
```

### Multiple Environments
```powershell
# Development
.\scripts\build_inno.ps1 -Version "dev-1.0.0"

# Staging  
.\scripts\build_inno.ps1 -Version "staging-1.0.0"

# Production
.\scripts\build_inno.ps1 -Version "1.0.0"
```

## Support

- **Documentation**: Xem README.md chính
- **Issues**: Tạo GitHub issue
- **Logs**: Gửi kèm log files khi báo lỗi
- **Contact**: it-security@att.com

## Changelog

### v1.0.0
- ✅ Tích hợp Inno Setup
- ✅ PowerShell build script
- ✅ GitHub Actions CI/CD
- ✅ Silent installation support
- ✅ Watchdog service integration
- ✅ Centralized logging
- ✅ Multi-language support
