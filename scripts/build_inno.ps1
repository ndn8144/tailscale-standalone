# PowerShell Build Script for ATT Tailscale Standalone with Inno Setup
# Tích hợp PyInstaller + Inno Setup + GitHub Actions

param(
    [string]$AuthKey = "",
    [string]$Version = "",
    [switch]$Silent = $false,
    [switch]$SkipTests = $false,
    [switch]$Clean = $false,
    [string]$OutputDir = "builds\installer"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Colors for output
$Colors = @{
    Info = "Cyan"
    Success = "Green"
    Warning = "Yellow"
    Error = "Red"
    Build = "Magenta"
}

function Write-ColorOutput {
    param([string]$Message, [string]$Color = "White", [string]$Prefix = "")
    $timestamp = Get-Date -Format "HH:mm:ss"
    Write-Host "[$timestamp] [$Prefix] $Message" -ForegroundColor $Color
}

function Test-Command {
    param([string]$Command)
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Install-InnoSetup {
    Write-ColorOutput "Checking for Inno Setup..." -Color $Colors.Info -Prefix "BUILD"
    
    $innoPaths = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 5\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 5\ISCC.exe"
    )
    
    foreach ($path in $innoPaths) {
        if (Test-Path $path) {
            Write-ColorOutput "Found Inno Setup: $path" -Color $Colors.Success -Prefix "BUILD"
            return $path
        }
    }
    
    Write-ColorOutput "Inno Setup not found. Installing via winget..." -Color $Colors.Warning -Prefix "BUILD"
    
    try {
        if (Test-Command "winget") {
            & winget install --id=JRSoftware.InnoSetup -e --silent --accept-package-agreements --accept-source-agreements
            Start-Sleep -Seconds 5
            
            # Check again after installation
            foreach ($path in $innoPaths) {
                if (Test-Path $path) {
                    Write-ColorOutput "Inno Setup installed successfully: $path" -Color $Colors.Success -Prefix "BUILD"
                    return $path
                }
            }
        }
        else {
            Write-ColorOutput "winget not available. Please install Inno Setup manually from: https://jrsoftware.org/isinfo.php" -Color $Colors.Error -Prefix "BUILD"
            throw "Inno Setup not found and cannot be installed automatically"
        }
    }
    catch {
        Write-ColorOutput "Failed to install Inno Setup: $($_.Exception.Message)" -Color $Colors.Error -Prefix "BUILD"
        throw
    }
}

function Get-Version {
    if ($Version) {
        return $Version
    }
    
    try {
        # Try to get version from git tag
        $gitVersion = git describe --tags --always 2>$null
        if ($gitVersion) {
            $version = $gitVersion -replace '^v', ''
            Write-ColorOutput "Using git version: $version" -Color $Colors.Info -Prefix "BUILD"
            return $version
        }
    }
    catch {
        Write-ColorOutput "Git not available, using default version" -Color $Colors.Warning -Prefix "BUILD"
    }
    
    # Fallback to timestamp-based version
    $timestamp = Get-Date -Format "yyyy.MM.dd.HHmm"
    return "1.0.0.$timestamp"
}

function Get-AuthKey {
    if ($AuthKey) {
        return $AuthKey
    }
    
    # Try environment variable
    $envKey = $env:TAILSCALE_AUTH_KEY
    if ($envKey) {
        Write-ColorOutput "Using auth key from environment variable" -Color $Colors.Info -Prefix "BUILD"
        return $envKey
    }
    
    # Try .env file
    if (Test-Path ".env") {
        try {
            $envContent = Get-Content ".env" -Raw
            if ($envContent -match "TAILSCALE_AUTH_KEY=(.+)") {
                $key = $matches[1].Trim()
                Write-ColorOutput "Using auth key from .env file" -Color $Colors.Info -Prefix "BUILD"
                return $key
            }
        }
        catch {
            Write-ColorOutput "Failed to read .env file: $($_.Exception.Message)" -Color $Colors.Warning -Prefix "BUILD"
        }
    }
    
    Write-ColorOutput "No auth key provided. Installer will prompt user for key." -Color $Colors.Warning -Prefix "BUILD"
    return ""
}

function Build-PyInstaller {
    Write-ColorOutput "Building PyInstaller executable..." -Color $Colors.Build -Prefix "BUILD"
    
    # Clean previous builds if requested
    if ($Clean) {
        Write-ColorOutput "Cleaning previous builds..." -Color $Colors.Info -Prefix "BUILD"
        if (Test-Path "builds") {
            Remove-Item "builds" -Recurse -Force -ErrorAction SilentlyContinue
        }
        if (Test-Path "temp") {
            Remove-Item "temp" -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    
    # Install/update requirements
    Write-ColorOutput "Installing Python dependencies..." -Color $Colors.Info -Prefix "BUILD"
    & python -m pip install --upgrade pip > $null 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to upgrade pip"
    }
    
    & python -m pip install -r requirements.txt > $null 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install requirements"
    }
    
    # Run the existing Windows installer builder
    Write-ColorOutput "Running Windows installer builder..." -Color $Colors.Info -Prefix "BUILD"
    $buildScript = "src\windows_installer_builder.py"
    
    if (-not (Test-Path $buildScript)) {
        throw "Windows installer builder not found: $buildScript"
    }
    
    $env:PYTHONIOENCODING = "utf-8"
    $env:PYTHONLEGACYWINDOWSSTDIO = "1"
    
    # Ensure temp directory exists
    if (-not (Test-Path "temp")) {
        New-Item -ItemType Directory -Path "temp" -Force | Out-Null
    }
    
    $process = Start-Process -FilePath "python" -ArgumentList $buildScript -Wait -PassThru -NoNewWindow
    
    if ($process.ExitCode -ne 0) {
        throw "PyInstaller build failed with exit code: $($process.ExitCode)"
    }
    
    # Find the generated executable
    $exeFiles = Get-ChildItem "builds\dist\*.exe" -ErrorAction SilentlyContinue
    if ($exeFiles.Count -eq 0) {
        throw "No executable found in builds\dist\"
    }
    
    $exeFile = $exeFiles[0]
    $exeSize = [math]::Round($exeFile.Length / 1MB, 2)
    Write-ColorOutput "PyInstaller build completed: $($exeFile.Name) ($exeSize MB)" -Color $Colors.Success -Prefix "BUILD"
    
    return $exeFile.FullName
}

function Build-InnoInstaller {
    param(
        [string]$PyInstallerExe,
        [string]$Version,
        [string]$AuthKey
    )
    
    Write-ColorOutput "Building Inno Setup installer..." -Color $Colors.Build -Prefix "BUILD"
    
    # Get Inno Setup path
    $isccPath = Install-InnoSetup
    
    # Prepare parameters
    $appVersion = $Version
    $appBinDir = Split-Path $PyInstallerExe -Parent
    $authKeyParam = if ($AuthKey) { "/DAuthKey=`"$AuthKey`"" } else { "" }
    
    # Create output directory
    $outputPath = Resolve-Path $OutputDir -ErrorAction SilentlyContinue
    if (-not $outputPath) {
        New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
        $outputPath = Resolve-Path $OutputDir
    }
    
    Write-ColorOutput "Output directory: $outputPath" -Color $Colors.Info -Prefix "BUILD"
    Write-ColorOutput "PyInstaller exe: $PyInstallerExe" -Color $Colors.Info -Prefix "BUILD"
    Write-ColorOutput "Version: $appVersion" -Color $Colors.Info -Prefix "BUILD"
    
    # Build Inno Setup command
    $issFile = "installers\tailscale-standalone.iss"
    if (-not (Test-Path $issFile)) {
        throw "Inno Setup script not found: $issFile"
    }
    
    # Get the exact PyInstaller exe name
    $pyInstallerExeName = Split-Path $PyInstallerExe -Leaf
    
    $isccArgs = @(
        $issFile
        "/DAppVersion=$appVersion"
        "/DAppBinDir=`"$appBinDir`""
        "/DAppExeName=`"$pyInstallerExeName`""
        "/O`"$outputPath`""
    )
    
    # Add auth key parameter if provided
    if ($authKeyParam) {
        $isccArgs += $authKeyParam
    }
    
    if ($Silent) {
        $isccArgs += "/SILENT"
    }
    
    Write-ColorOutput "Running Inno Setup Compiler..." -Color $Colors.Info -Prefix "BUILD"
    Write-ColorOutput "Command: $isccPath $($isccArgs -join ' ')" -Color $Colors.Info -Prefix "BUILD"
    
    try {
        # Ensure temp directory exists
        if (-not (Test-Path "temp")) {
            New-Item -ItemType Directory -Path "temp" -Force | Out-Null
        }
        
        # Use Start-Process to properly handle the executable
        $process = Start-Process -FilePath $isccPath -ArgumentList $isccArgs -Wait -PassThru -NoNewWindow -RedirectStandardOutput "temp\iscc_output.txt" -RedirectStandardError "temp\iscc_error.txt"
        
        if ($process.ExitCode -ne 0) {
            # Read error output for debugging
            $errorOutput = ""
            if (Test-Path "temp\iscc_error.txt") {
                $errorOutput = Get-Content "temp\iscc_error.txt" -Raw
            }
            throw "Inno Setup compilation failed with exit code: $($process.ExitCode). Error: $errorOutput"
        }
        
        # Find the generated installer
        $installerFiles = Get-ChildItem "$outputPath\*.exe" -ErrorAction SilentlyContinue
        if ($installerFiles.Count -eq 0) {
            throw "No installer found in output directory: $outputPath"
        }
        
        $installerFile = $installerFiles[0]
        $installerSize = [math]::Round($installerFile.Length / 1MB, 2)
        
        Write-ColorOutput "Inno Setup build completed: $($installerFile.Name) ($installerSize MB)" -Color $Colors.Success -Prefix "BUILD"
        
        return $installerFile.FullName
    }
    catch {
        Write-ColorOutput "Inno Setup build failed: $($_.Exception.Message)" -Color $Colors.Error -Prefix "BUILD"
        throw
    }
}

function Test-Installer {
    param([string]$InstallerPath)
    
    if ($SkipTests) {
        Write-ColorOutput "Skipping installer tests" -Color $Colors.Warning -Prefix "TEST"
        return
    }
    
    Write-ColorOutput "Testing installer..." -Color $Colors.Info -Prefix "TEST"
    
    # Basic file checks
    if (-not (Test-Path $InstallerPath)) {
        throw "Installer file not found: $InstallerPath"
    }
    
    $fileInfo = Get-Item $InstallerPath
    if ($fileInfo.Length -lt 1MB) {
        throw "Installer file seems too small: $($fileInfo.Length) bytes"
    }
    
    Write-ColorOutput "Installer file validation passed" -Color $Colors.Success -Prefix "TEST"
    
    # Optional: Test silent installation in a temporary directory
    if ($env:CI -eq "true") {
        Write-ColorOutput "Running silent installation test..." -Color $Colors.Info -Prefix "TEST"
        
        $testDir = Join-Path $env:TEMP "att-tailscale-test-$(Get-Random)"
        try {
            New-Item -ItemType Directory -Path $testDir -Force | Out-Null
            
            $testArgs = @(
                "/SILENT"
                "/DIR=`"$testDir`""
                "/LOG=`"$testDir\install.log`""
            )
            
            $testProcess = Start-Process -FilePath $InstallerPath -ArgumentList $testArgs -Wait -PassThru -NoNewWindow
            
            if ($testProcess.ExitCode -eq 0) {
                Write-ColorOutput "Silent installation test passed" -Color $Colors.Success -Prefix "TEST"
            }
            else {
                Write-ColorOutput "Silent installation test failed with exit code: $($testProcess.ExitCode)" -Color $Colors.Warning -Prefix "TEST"
            }
        }
        catch {
            Write-ColorOutput "Silent installation test error: $($_.Exception.Message)" -Color $Colors.Warning -Prefix "TEST"
        }
        finally {
            if (Test-Path $testDir) {
                Remove-Item $testDir -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

function Show-BuildSummary {
    param(
        [string]$InstallerPath,
        [string]$Version,
        [string]$AuthKey
    )
    
    $installerFile = Get-Item $InstallerPath
    $installerSize = [math]::Round($installerFile.Length / 1MB, 2)
    
    Write-Host ""
    Write-Host "=" * 80 -ForegroundColor $Colors.Build
    Write-Host "BUILD SUMMARY" -ForegroundColor $Colors.Build
    Write-Host "=" * 80 -ForegroundColor $Colors.Build
    Write-Host "Installer: $($installerFile.Name)" -ForegroundColor $Colors.Success
    Write-Host "Size: $installerSize MB" -ForegroundColor $Colors.Success
    Write-Host "Version: $Version" -ForegroundColor $Colors.Success
    Write-Host "Path: $($installerFile.FullName)" -ForegroundColor $Colors.Success
    Write-Host "Auth Key: $(if ($AuthKey) { $AuthKey.Substring(0, [Math]::Min(30, $AuthKey.Length)) + '...' } else { 'Not provided (user will be prompted)' })" -ForegroundColor $Colors.Success
    Write-Host ""
    Write-Host "FEATURES:" -ForegroundColor $Colors.Info
    Write-Host "  ✓ Tailscale MSI installation" -ForegroundColor $Colors.Success
    Write-Host "  ✓ Watchdog service with auto-recovery" -ForegroundColor $Colors.Success
    Write-Host "  ✓ Centralized logging" -ForegroundColor $Colors.Success
    Write-Host "  ✓ Windows Scheduled Task integration" -ForegroundColor $Colors.Success
    Write-Host "  ✓ Desktop shortcuts" -ForegroundColor $Colors.Success
    Write-Host "  ✓ Uninstaller" -ForegroundColor $Colors.Success
    Write-Host "  ✓ Silent installation support" -ForegroundColor $Colors.Success
    Write-Host ""
    Write-Host "DEPLOYMENT:" -ForegroundColor $Colors.Info
    Write-Host "  • Send installer to employees via secure email" -ForegroundColor $Colors.Info
    Write-Host "  • Instruct: Right-click → 'Run as administrator'" -ForegroundColor $Colors.Info
    Write-Host "  • For silent deployment: installer.exe /SILENT" -ForegroundColor $Colors.Info
    Write-Host "  • Monitor logs: C:\ProgramData\ATT\Logs\" -ForegroundColor $Colors.Info
    Write-Host "=" * 80 -ForegroundColor $Colors.Build
}

# Main execution
try {
    Write-ColorOutput "Starting ATT Tailscale Standalone build process..." -Color $Colors.Build -Prefix "BUILD"
    Write-ColorOutput "Parameters: Version=$Version, Silent=$Silent, Clean=$Clean" -Color $Colors.Info -Prefix "BUILD"
    
    # Get version and auth key
    $appVersion = Get-Version
    $appAuthKey = Get-AuthKey
    
    # Build PyInstaller executable
    $pyInstallerExe = Build-PyInstaller
    
    # Build Inno Setup installer
    $installerPath = Build-InnoInstaller -PyInstallerExe $pyInstallerExe -Version $appVersion -AuthKey $appAuthKey
    
    # Test installer
    Test-Installer -InstallerPath $installerPath
    
    # Show summary
    Show-BuildSummary -InstallerPath $installerPath -Version $appVersion -AuthKey $appAuthKey
    
    Write-ColorOutput "Build completed successfully!" -Color $Colors.Success -Prefix "BUILD"
    exit 0
}
catch {
    Write-ColorOutput "Build failed: $($_.Exception.Message)" -Color $Colors.Error -Prefix "BUILD"
    Write-ColorOutput "Stack trace: $($_.ScriptStackTrace)" -Color $Colors.Error -Prefix "BUILD"
    exit 1
}
