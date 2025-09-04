# Full build script for ATT Tailscale Standalone
param(
    [string]$AuthKey = "",
    [switch]$Clean = $false,
    [switch]$Test = $false,
    [switch]$Silent = $false,
    [switch]$Help = $false
)

if ($Help) {
    Write-Host "ATT Tailscale Standalone - Full Build Script"
    Write-Host "============================================="
    Write-Host ""
    Write-Host "Usage: .\scripts\full_build.ps1 [-AuthKey <key>] [-Clean] [-Test] [-Silent] [-Help]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -AuthKey    Tailscale authentication key (tskey-auth-...)"
    Write-Host "  -Clean      Clean previous builds before starting"
    Write-Host "  -Test       Run tests after build"
    Write-Host "  -Silent     Run in silent mode"
    Write-Host "  -Help       Show this help message"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\scripts\full_build.ps1"
    Write-Host "  .\scripts\full_build.ps1 -AuthKey 'tskey-auth-xxx' -Clean -Test"
    Write-Host "  .\scripts\full_build.ps1 -Silent"
    exit 0
}

$ErrorActionPreference = "Stop"

# Color functions
function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White",
        [string]$Prefix = "INFO"
    )
    
    $timestamp = Get-Date -Format "HH:mm:ss"
    $colorMap = @{
        "Red" = "Red"
        "Green" = "Green" 
        "Yellow" = "Yellow"
        "Blue" = "Blue"
        "Cyan" = "Cyan"
        "Magenta" = "Magenta"
        "White" = "White"
    }
    
    $colorCode = $colorMap[$Color]
    if (-not $colorCode) { $colorCode = "White" }
    
    Write-Host "[$timestamp] [$Prefix] $Message" -ForegroundColor $colorCode
}

Write-ColorOutput "Starting ATT Tailscale Standalone Full Build" "Cyan" "BUILD"
Write-ColorOutput "=============================================" "Cyan" "BUILD"

# Step 1: Prerequisites check
Write-ColorOutput "Step 1: Checking prerequisites..." "Blue" "BUILD"

$prereqIssues = @()

# Check Python
try {
    $pythonVersion = python --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-ColorOutput "✓ Python: $pythonVersion" "Green" "BUILD"
    } else {
        $prereqIssues += "Python not found"
    }
} catch {
    $prereqIssues += "Python not found"
}

# Check PyInstaller
try {
    python -c "import PyInstaller" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-ColorOutput "✓ PyInstaller: Available" "Green" "BUILD"
    } else {
        $prereqIssues += "PyInstaller not installed"
    }
} catch {
    $prereqIssues += "PyInstaller not installed"
}

# Check Inno Setup
$innoPaths = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
)

$innoFound = $false
foreach ($path in $innoPaths) {
    if (Test-Path $path) {
        Write-ColorOutput "✓ Inno Setup: $path" "Green" "BUILD"
        $innoFound = $true
        break
    }
}

if (-not $innoFound) {
    $prereqIssues += "Inno Setup not found"
}

# Check required files
$requiredFiles = @(
    "src\windows_installer_builder.py",
    "installers\tailscale-standalone.iss",
    "templates\install_script.ps1",
    "templates\config_template.json"
)

foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-ColorOutput "✓ File: $file" "Green" "BUILD"
    } else {
        $prereqIssues += "Missing file: $file"
    }
}

if ($prereqIssues.Count -gt 0) {
    Write-ColorOutput "Prerequisites check failed:" "Red" "ERROR"
    foreach ($issue in $prereqIssues) {
        Write-ColorOutput "  - $issue" "Red" "ERROR"
    }
    exit 1
}

Write-ColorOutput "All prerequisites met" "Green" "BUILD"

# Step 2: Clean if requested
if ($Clean) {
    Write-ColorOutput "Step 2: Cleaning previous builds..." "Blue" "BUILD"
    
    $cleanPaths = @("builds", "temp", "installers\builds")
    foreach ($path in $cleanPaths) {
        if (Test-Path $path) {
            Remove-Item $path -Recurse -Force -ErrorAction SilentlyContinue
            Write-ColorOutput "Cleaned: $path" "Yellow" "BUILD"
        }
    }
}

# Step 3: Build PyInstaller
Write-ColorOutput "Step 3: Building PyInstaller executable..." "Blue" "BUILD"

try {
    if ($AuthKey) {
        & .\scripts\build_inno.ps1 -AuthKey $AuthKey
    } else {
        & .\scripts\build_inno.ps1
    }
    
    if ($LASTEXITCODE -ne 0) {
        throw "Build script failed with exit code: $LASTEXITCODE"
    }
    
    Write-ColorOutput "PyInstaller build completed successfully" "Green" "BUILD"
} catch {
    Write-ColorOutput "PyInstaller build failed: $($_.Exception.Message)" "Red" "ERROR"
    exit 1
}

# Step 4: Verify outputs
Write-ColorOutput "Step 4: Verifying build outputs..." "Blue" "BUILD"

# Check PyInstaller output
$pyInstallerFiles = Get-ChildItem "builds\dist\*.exe" -ErrorAction SilentlyContinue
if ($pyInstallerFiles) {
    $pyInstallerFile = $pyInstallerFiles[0]
    $sizeMB = [math]::Round($pyInstallerFile.Length / 1MB, 2)
    Write-ColorOutput "✓ PyInstaller: $($pyInstallerFile.Name) ($sizeMB MB)" "Green" "BUILD"
} else {
    Write-ColorOutput "✗ PyInstaller output not found" "Red" "ERROR"
    exit 1
}

# Check Inno Setup output
$innoFiles = Get-ChildItem "installers\builds\installer\*.exe" -ErrorAction SilentlyContinue
if ($innoFiles) {
    $innoFile = $innoFiles[0]
    $sizeMB = [math]::Round($innoFile.Length / 1MB, 2)
    Write-ColorOutput "✓ Inno Setup: $($innoFile.Name) ($sizeMB MB)" "Green" "BUILD"
} else {
    Write-ColorOutput "✗ Inno Setup output not found" "Red" "ERROR"
    exit 1
}

# Step 5: Run tests if requested
if ($Test) {
    Write-ColorOutput "Step 5: Running tests..." "Blue" "BUILD"
    
    try {
        & .\scripts\test_build.ps1 -Quick
        if ($LASTEXITCODE -eq 0) {
            Write-ColorOutput "Tests completed successfully" "Green" "BUILD"
        } else {
            Write-ColorOutput "Some tests failed" "Yellow" "WARNING"
        }
    } catch {
        Write-ColorOutput "Test execution failed: $($_.Exception.Message)" "Red" "ERROR"
    }
}

# Step 6: Summary
Write-ColorOutput "Step 6: Build Summary" "Cyan" "BUILD"
Write-ColorOutput "===================" "Cyan" "BUILD"

Write-ColorOutput "Build completed successfully!" "Green" "SUCCESS"
Write-ColorOutput ""
Write-ColorOutput "Outputs:" "White" "INFO"
Write-ColorOutput "  PyInstaller: $($pyInstallerFile.FullName)" "White" "INFO"
Write-ColorOutput "  Inno Setup:  $($innoFile.FullName)" "White" "INFO"
Write-ColorOutput ""
Write-ColorOutput "Next steps:" "White" "INFO"
Write-ColorOutput "  1. Test installer: .\scripts\test_installer.ps1" "White" "INFO"
Write-ColorOutput "  2. Deploy to test VM" "White" "INFO"
Write-ColorOutput "  3. Verify Tailscale connection" "White" "INFO"
Write-ColorOutput "  4. Deploy to production" "White" "INFO"

if ($Silent) {
    Write-ColorOutput "Build completed in silent mode" "Green" "SUCCESS"
} else {
    Write-ColorOutput "Press any key to continue..." "Yellow" "INFO"
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}
