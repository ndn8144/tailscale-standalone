# Test script for ATT Tailscale Standalone Installer
param(
    [string]$InstallerPath = "",
    [switch]$Silent = $false,
    [switch]$Help = $false
)

if ($Help) {
    Write-Host "Usage: .\scripts\test_installer.ps1 [-InstallerPath <path>] [-Silent] [-Help]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -InstallerPath  Path to the installer .exe file"
    Write-Host "  -Silent         Run installer in silent mode"
    Write-Host "  -Help           Show this help message"
    exit 0
}

# Find installer if not provided
if (-not $InstallerPath) {
    $installerFiles = @(
        "installers\builds\installer\*.exe",
        "builds\installer\*.exe"
    )
    
    foreach ($pattern in $installerFiles) {
        $files = Get-ChildItem $pattern -ErrorAction SilentlyContinue
        if ($files) {
            $InstallerPath = $files[0].FullName
            break
        }
    }
    
    if (-not $InstallerPath) {
        Write-Error "No installer found. Please specify -InstallerPath or run build first."
        exit 1
    }
}

if (-not (Test-Path $InstallerPath)) {
    Write-Error "Installer not found: $InstallerPath"
    exit 1
}

Write-Host "Testing installer: $InstallerPath"
Write-Host "Size: $((Get-Item $InstallerPath).Length / 1MB) MB"
Write-Host ""

# Test installer properties
Write-Host "Installer Properties:"
try {
    $fileInfo = Get-ItemProperty $InstallerPath
    Write-Host "  Created: $($fileInfo.CreationTime)"
    Write-Host "  Modified: $($fileInfo.LastWriteTime)"
    Write-Host "  Version: $($fileInfo.VersionInfo.FileVersion)"
} catch {
    Write-Host "  Could not read file properties"
}

Write-Host ""
Write-Host "Installer Test Options:"
Write-Host "1. Test installer properties (current)"
Write-Host "2. Run installer in test mode (requires admin)"
Write-Host "3. Check installer dependencies"
Write-Host "4. Exit"

$choice = Read-Host "Select option (1-4)"

switch ($choice) {
    "1" {
        Write-Host "Installer properties test completed."
    }
    "2" {
        if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
            Write-Warning "Administrator privileges required for installer test."
            Write-Host "Please run PowerShell as Administrator and try again."
            exit 1
        }
        
        Write-Host "Starting installer test..."
        if ($Silent) {
            Write-Host "Running in silent mode..."
            & $InstallerPath /SILENT
        } else {
            Write-Host "Running in interactive mode..."
            & $InstallerPath
        }
    }
    "3" {
        Write-Host "Checking installer dependencies..."
        
        # Check if installer is digitally signed
        try {
            $signature = Get-AuthenticodeSignature $InstallerPath
            if ($signature.Status -eq "Valid") {
                Write-Host "  ✓ Digitally signed: $($signature.SignerCertificate.Subject)"
            } else {
                Write-Host "  ⚠ Not digitally signed: $($signature.Status)"
            }
        } catch {
            Write-Host "  ⚠ Could not verify digital signature"
        }
        
        # Check file type
        $fileType = [System.IO.Path]::GetExtension($InstallerPath)
        Write-Host "  File type: $fileType"
        
        # Check if it's a valid PE file
        try {
            $bytes = [System.IO.File]::ReadAllBytes($InstallerPath)
            if ($bytes[0] -eq 0x4D -and $bytes[1] -eq 0x5A) {
                Write-Host "  ✓ Valid PE executable"
            } else {
                Write-Host "  ⚠ Not a valid PE executable"
            }
        } catch {
            Write-Host "  ⚠ Could not verify PE format"
        }
    }
    "4" {
        Write-Host "Exiting..."
        exit 0
    }
    default {
        Write-Host "Invalid option. Exiting..."
        exit 1
    }
}

Write-Host ""
Write-Host "Test completed successfully!"
