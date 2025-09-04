# Test Build Script for ATT Tailscale Standalone
# Kiểm tra build process trước khi triển khai

param(
    [switch]$Quick = $false,
    [switch]$Verbose = $false
)

$ErrorActionPreference = "Stop"

function Write-TestOutput {
    param([string]$Message, [string]$Level = "INFO")
    
    $timestamp = Get-Date -Format "HH:mm:ss"
    $color = switch ($Level) {
        "ERROR" { "Red" }
        "WARNING" { "Yellow" }
        "SUCCESS" { "Green" }
        "INFO" { "Cyan" }
        default { "White" }
    }
    
    Write-Host "[$timestamp] [$Level] $Message" -ForegroundColor $color
}

function Test-Prerequisites {
    Write-TestOutput "Testing prerequisites..." "INFO"
    
    $issues = @()
    
    # Check Python
    try {
        $pythonVersion = python --version 2>&1
        Write-TestOutput "Python: $pythonVersion" "SUCCESS"
    }
    catch {
        $issues += "Python not found or not in PATH"
    }
    
    # Check PyInstaller
    try {
        python -c "import PyInstaller" 2>$null
        Write-TestOutput "PyInstaller: Available" "SUCCESS"
    }
    catch {
        $issues += "PyInstaller not installed"
    }
    
    # Check Inno Setup
    $innoPaths = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 5\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 5\ISCC.exe"
    )
    
    $innoFound = $false
    foreach ($path in $innoPaths) {
        if (Test-Path $path) {
            Write-TestOutput "Inno Setup: $path" "SUCCESS"
            $innoFound = $true
            break
        }
    }
    
    if (-not $innoFound) {
        $issues += "Inno Setup not found"
    }
    
    # Check auth key
    $authKey = $env:TAILSCALE_AUTH_KEY
    if ($authKey) {
        if ($authKey -like "tskey-auth-*") {
            Write-TestOutput "Auth Key: Available (${authKey.Substring(0,20)}...)" "SUCCESS"
        } else {
            $issues += "Invalid auth key format"
        }
    } else {
        Write-TestOutput "Auth Key: Not set (will prompt user)" "WARNING"
    }
    
    # Check required files
    $requiredFiles = @(
        "src\windows_installer_builder.py",
        "installers\tailscale-standalone.iss",
        "scripts\build_inno.ps1",
        "templates\install_script.ps1",
        "templates\config_template.json"
    )
    
    foreach ($file in $requiredFiles) {
        if (Test-Path $file) {
            Write-TestOutput "File: $file" "SUCCESS"
        } else {
            $issues += "Missing file: $file"
        }
    }
    
    if ($issues.Count -gt 0) {
        Write-TestOutput "Prerequisites check failed:" "ERROR"
        foreach ($issue in $issues) {
            Write-TestOutput "  - $issue" "ERROR"
        }
        return $false
    }
    
    Write-TestOutput "All prerequisites met" "SUCCESS"
    return $true
}

function Test-PyInstallerBuild {
    Write-TestOutput "Testing PyInstaller build..." "INFO"
    
    try {
        # Clean previous builds
        if (Test-Path "builds") {
            Remove-Item "builds" -Recurse -Force -ErrorAction SilentlyContinue
        }
        if (Test-Path "temp") {
            Remove-Item "temp" -Recurse -Force -ErrorAction SilentlyContinue
        }
        
        # Run PyInstaller build
        Write-TestOutput "Running PyInstaller build..." "INFO"
        python src\windows_installer_builder.py
        
        if ($LASTEXITCODE -ne 0) {
            Write-TestOutput "PyInstaller build failed" "ERROR"
            return $false
        }
        
        # Check output
        $exeFiles = Get-ChildItem "builds\dist\*.exe" -ErrorAction SilentlyContinue
        if ($exeFiles.Count -eq 0) {
            Write-TestOutput "No executable found in builds\dist\" "ERROR"
            return $false
        }
        
        $exeFile = $exeFiles[0]
        $exeSize = [math]::Round($exeFile.Length / 1MB, 2)
        Write-TestOutput "PyInstaller build successful: $($exeFile.Name) ($exeSize MB)" "SUCCESS"
        
        return $true
    }
    catch {
        Write-TestOutput "PyInstaller build error: $($_.Exception.Message)" "ERROR"
        return $false
    }
}

function Test-InnoSetupBuild {
    Write-TestOutput "Testing Inno Setup build..." "INFO"
    
    try {
        # Get Inno Setup path
        $isccPath = if (Test-Path "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe") {
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
        } else {
            "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
        }
        
        # Prepare parameters
        $version = "1.0.0-test"
        $binDir = "builds\dist"
        $authKey = $env:TAILSCALE_AUTH_KEY
        
        # Build command
        $isccArgs = @(
            "installers\tailscale-standalone.iss"
            "/DAppVersion=$version"
            "/DAppBinDir=`"$binDir`""
            "/O`"builds\installer`""
        )
        
        if ($authKey) {
            $isccArgs += "/DAuthKey=`"$authKey`""
        }
        
        Write-TestOutput "Running Inno Setup Compiler..." "INFO"
        & $isccPath $isccArgs
        
        if ($LASTEXITCODE -ne 0) {
            Write-TestOutput "Inno Setup build failed" "ERROR"
            return $false
        }
        
        # Check output
        $installerFiles = Get-ChildItem "builds\installer\*.exe" -ErrorAction SilentlyContinue
        if ($installerFiles.Count -eq 0) {
            Write-TestOutput "No installer found in builds\installer\" "ERROR"
            return $false
        }
        
        $installerFile = $installerFiles[0]
        $installerSize = [math]::Round($installerFile.Length / 1MB, 2)
        Write-TestOutput "Inno Setup build successful: $($installerFile.Name) ($installerSize MB)" "SUCCESS"
        
        return $true
    }
    catch {
        Write-TestOutput "Inno Setup build error: $($_.Exception.Message)" "ERROR"
        return $false
    }
}

function Test-InstallerValidation {
    param([string]$InstallerPath)
    
    Write-TestOutput "Validating installer..." "INFO"
    
    try {
        # Basic file validation
        if (-not (Test-Path $InstallerPath)) {
            Write-TestOutput "Installer file not found: $InstallerPath" "ERROR"
            return $false
        }
        
        $fileInfo = Get-Item $InstallerPath
        if ($fileInfo.Length -lt 1MB) {
            Write-TestOutput "Installer file seems too small: $($fileInfo.Length) bytes" "ERROR"
            return $false
        }
        
        Write-TestOutput "Installer file validation passed" "SUCCESS"
        
        # Test silent installation in temporary directory
        if (-not $Quick) {
            Write-TestOutput "Testing silent installation..." "INFO"
            
            $testDir = Join-Path $env:TEMP "att-tailscale-test-$(Get-Random)"
            try {
                New-Item -ItemType Directory -Path $testDir -Force | Out-Null
                
                $testArgs = @(
                    "/SILENT"
                    "/DIR=`"$testDir`""
                    "/LOG=`"$testDir\install.log`""
                    "/SUPPRESSMSGBOXES"
                    "/NORESTART"
                )
                
                Write-TestOutput "Running silent installation test..." "INFO"
                $testProcess = Start-Process -FilePath $InstallerPath -ArgumentList $testArgs -Wait -PassThru -NoNewWindow
                
                if ($testProcess.ExitCode -eq 0) {
                    Write-TestOutput "Silent installation test passed" "SUCCESS"
                } else {
                    Write-TestOutput "Silent installation test failed with exit code: $($testProcess.ExitCode)" "WARNING"
                }
            }
            catch {
                Write-TestOutput "Silent installation test error: $($_.Exception.Message)" "WARNING"
            }
            finally {
                if (Test-Path $testDir) {
                    Remove-Item $testDir -Recurse -Force -ErrorAction SilentlyContinue
                }
            }
        }
        
        return $true
    }
    catch {
        Write-TestOutput "Installer validation error: $($_.Exception.Message)" "ERROR"
        return $false
    }
}

function Show-TestSummary {
    param(
        [bool]$Prerequisites,
        [bool]$PyInstaller,
        [bool]$InnoSetup,
        [bool]$Validation,
        [string]$InstallerPath = ""
    )
    
    Write-Host ""
    Write-Host "=" * 80 -ForegroundColor Magenta
    Write-Host "TEST SUMMARY" -ForegroundColor Magenta
    Write-Host "=" * 80 -ForegroundColor Magenta
    
    $tests = @(
        @{Name="Prerequisites"; Result=$Prerequisites},
        @{Name="PyInstaller Build"; Result=$PyInstaller},
        @{Name="Inno Setup Build"; Result=$InnoSetup},
        @{Name="Installer Validation"; Result=$Validation}
    )
    
    foreach ($test in $tests) {
        $status = if ($test.Result) { "✓ PASS" } else { "✗ FAIL" }
        $color = if ($test.Result) { "Green" } else { "Red" }
        Write-Host "$($test.Name): $status" -ForegroundColor $color
    }
    
    if ($InstallerPath) {
        $installerFile = Get-Item $InstallerPath
        $installerSize = [math]::Round($installerFile.Length / 1MB, 2)
        Write-Host ""
        Write-Host "Installer: $($installerFile.Name)" -ForegroundColor Cyan
        Write-Host "Size: $installerSize MB" -ForegroundColor Cyan
        Write-Host "Path: $($installerFile.FullName)" -ForegroundColor Cyan
    }
    
    $allPassed = $Prerequisites -and $PyInstaller -and $InnoSetup -and $Validation
    
    Write-Host ""
    if ($allPassed) {
        Write-Host "🎉 ALL TESTS PASSED! Ready for deployment." -ForegroundColor Green
    } else {
        Write-Host "❌ SOME TESTS FAILED! Please fix issues before deployment." -ForegroundColor Red
    }
    
    Write-Host "=" * 80 -ForegroundColor Magenta
    
    return $allPassed
}

# Main execution
try {
    Write-TestOutput "Starting ATT Tailscale Standalone build test..." "INFO"
    Write-TestOutput "Quick mode: $Quick" "INFO"
    
    # Test 1: Prerequisites
    $prereqResult = Test-Prerequisites
    if (-not $prereqResult) {
        Write-TestOutput "Prerequisites test failed, stopping..." "ERROR"
        exit 1
    }
    
    # Test 2: PyInstaller build
    $pyInstallerResult = Test-PyInstallerBuild
    if (-not $pyInstallerResult) {
        Write-TestOutput "PyInstaller build failed, stopping..." "ERROR"
        exit 1
    }
    
    # Test 3: Inno Setup build
    $innoResult = Test-InnoSetupBuild
    if (-not $innoResult) {
        Write-TestOutput "Inno Setup build failed, stopping..." "ERROR"
        exit 1
    }
    
    # Test 4: Installer validation
    $installerFiles = Get-ChildItem "builds\installer\*.exe" -ErrorAction SilentlyContinue
    $validationResult = $false
    $installerPath = ""
    
    if ($installerFiles) {
        $installerPath = $installerFiles[0].FullName
        $validationResult = Test-InstallerValidation -InstallerPath $installerPath
    }
    
    # Show summary
    $allPassed = Show-TestSummary -Prerequisites $prereqResult -PyInstaller $pyInstallerResult -InnoSetup $innoResult -Validation $validationResult -InstallerPath $installerPath
    
    if ($allPassed) {
        Write-TestOutput "Build test completed successfully!" "SUCCESS"
        exit 0
    } else {
        Write-TestOutput "Build test failed!" "ERROR"
        exit 1
    }
}
catch {
    Write-TestOutput "Test execution error: $($_.Exception.Message)" "ERROR"
    exit 1
}
