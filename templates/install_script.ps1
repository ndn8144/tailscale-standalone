# ATT Tailscale Installation Script
# Post-installation script for Inno Setup installer
# Handles Tailscale MSI installation, service setup, and configuration

param(
    [Parameter(Mandatory=$true)]
    [string]$InstallPath,
    
    [Parameter(Mandatory=$false)]
    [string]$AuthKey = "",
    
    [Parameter(Mandatory=$false)]
    [switch]$Uninstall = $false,
    
    [Parameter(Mandatory=$false)]
    [string]$ConfigFile = "",
    
    [Parameter(Mandatory=$false)]
    [switch]$Silent = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$Force = $false
)

# Configuration
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Paths
$LogDir = "C:\ProgramData\ATT\Logs"
$ConfigDir = "C:\ProgramData\ATT\Config"
$WatchdogDir = "C:\ProgramData\ATT\Watchdog"
$TailscaleExe = "C:\Program Files\Tailscale\tailscale.exe"
$ServiceName = "ATT_Tailscale_Watchdog"

# Logging
function Write-Log {
    param(
        [string]$Message,
        [string]$Level = "INFO",
        [string]$Component = "InstallScript"
    )
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = "[$timestamp] [$Level] [$Component] $Message"
    
    if (-not $Silent) {
        switch ($Level) {
            "ERROR" { Write-Host $logMessage -ForegroundColor Red }
            "WARNING" { Write-Host $logMessage -ForegroundColor Yellow }
            "SUCCESS" { Write-Host $logMessage -ForegroundColor Green }
            default { Write-Host $logMessage -ForegroundColor White }
        }
    }
    
    # Write to log file
    try {
        if (-not (Test-Path $LogDir)) {
            New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
        }
        
        $logFile = Join-Path $LogDir "att_tailscale_install.log"
        Add-Content -Path $logFile -Value $logMessage -Encoding UTF8
    }
    catch {
        # Ignore logging errors
    }
}

function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-ConfigValue {
    param(
        [string]$Key,
        [string]$DefaultValue = ""
    )
    
    if ($ConfigFile -and (Test-Path $ConfigFile)) {
        try {
            $config = Get-Content $ConfigFile -Raw | ConvertFrom-Json
            $keys = $Key.Split('.')
            $value = $config
            
            foreach ($keyPart in $keys) {
                if ($value.PSObject.Properties.Name -contains $keyPart) {
                    $value = $value.$keyPart
                } else {
                    return $DefaultValue
                }
            }
            
            return $value
        }
        catch {
            Write-Log "Failed to read config value '$Key': $($_.Exception.Message)" "WARNING"
            return $DefaultValue
        }
    }
    
    return $DefaultValue
}

function Test-NetworkConnectivity {
    $testHosts = @(
        "login.tailscale.com:443",
        "api.tailscale.com:443",
        "pkgs.tailscale.com:443"
    )
    
    $reachableHosts = 0
    foreach ($host in $testHosts) {
        try {
            $hostname, $port = $host.Split(':')
            $tcpClient = New-Object System.Net.Sockets.TcpClient
            $tcpClient.ConnectAsync($hostname, $port).Wait(5000)
            $tcpClient.Close()
            $reachableHosts++
            Write-Log "Network test passed: $host" "DEBUG"
        }
        catch {
            Write-Log "Network test failed: $host - $($_.Exception.Message)" "WARNING"
        }
    }
    
    return $reachableHosts -gt 0
}

function Install-TailscaleMSI {
    Write-Log "Starting Tailscale MSI installation..."
    
    # Check if already installed
    if (Test-Path $TailscaleExe) {
        Write-Log "Tailscale already installed, checking version..."
        try {
            $version = & $TailscaleExe version 2>$null
            Write-Log "Current Tailscale version: $version"
            
            if (-not $Force) {
                Write-Log "Tailscale already installed. Use -Force to reinstall." "INFO"
                return $true
            }
        }
        catch {
            Write-Log "Failed to get Tailscale version: $($_.Exception.Message)" "WARNING"
        }
    }
    
    # Test network connectivity
    if (-not (Test-NetworkConnectivity)) {
        Write-Log "Network connectivity test failed. Please check your internet connection." "ERROR"
        return $false
    }
    
    # Download Tailscale MSI
    $msiUrl = "https://pkgs.tailscale.com/stable/tailscale-setup-latest-amd64.msi"
    $msiPath = Join-Path $env:TEMP "tailscale-setup-$(Get-Random).msi"
    
    try {
        Write-Log "Downloading Tailscale MSI from $msiUrl..."
        $webClient = New-Object System.Net.WebClient
        $webClient.Headers.Add("User-Agent", "ATT-Tailscale-Installer/1.0")
        $webClient.DownloadFile($msiUrl, $msiPath)
        
        $msiSize = [math]::Round((Get-Item $msiPath).Length / 1MB, 2)
        Write-Log "Downloaded MSI: $msiSize MB"
    }
    catch {
        Write-Log "Failed to download Tailscale MSI: $($_.Exception.Message)" "ERROR"
        return $false
    }
    
    # Install MSI
    try {
        Write-Log "Installing Tailscale MSI..."
        
        $installArgs = @(
            "/i", $msiPath,
            "/quiet",
            "/norestart",
            "/noprompt",
            "TS_UNATTENDEDMODE=always",
            "TS_INSTALLUPDATES=always",
            "TS_NOLAUNCH=1",
            "TS_NOSTART=1"
        )
        
        $process = Start-Process -FilePath "msiexec.exe" -ArgumentList $installArgs -Wait -PassThru -NoNewWindow
        
        if ($process.ExitCode -eq 0) {
            Write-Log "Tailscale MSI installation completed successfully" "SUCCESS"
        } else {
            Write-Log "Tailscale MSI installation failed with exit code: $($process.ExitCode)" "ERROR"
            return $false
        }
    }
    catch {
        Write-Log "Tailscale MSI installation error: $($_.Exception.Message)" "ERROR"
        return $false
    }
    finally {
        # Clean up MSI file
        if (Test-Path $msiPath) {
            Remove-Item $msiPath -Force -ErrorAction SilentlyContinue
        }
    }
    
    # Verify installation
    Start-Sleep -Seconds 3
    if (-not (Test-Path $TailscaleExe)) {
        Write-Log "Tailscale executable not found after installation" "ERROR"
        return $false
    }
    
    Write-Log "Tailscale installation verified" "SUCCESS"
    return $true
}

function Setup-WatchdogService {
    Write-Log "Setting up watchdog service..."
    
    # Create watchdog directory
    if (-not (Test-Path $WatchdogDir)) {
        New-Item -ItemType Directory -Path $WatchdogDir -Force | Out-Null
        Write-Log "Created watchdog directory: $WatchdogDir"
    }
    
    # Copy watchdog script
    $watchdogScript = Join-Path $InstallPath "watchdog\att_tailscale_watchdog.py"
    if (Test-Path $watchdogScript) {
        Copy-Item $watchdogScript -Destination $WatchdogDir -Force
        Write-Log "Copied watchdog script to: $WatchdogDir"
    } else {
        Write-Log "Watchdog script not found: $watchdogScript" "WARNING"
    }
    
    # Create batch file to run watchdog
    $batchFile = Join-Path $WatchdogDir "run_watchdog.bat"
    $batchContent = @"
@echo off
cd /d "$WatchdogDir"
python "att_tailscale_watchdog.py" service
"@
    
    Set-Content -Path $batchFile -Value $batchContent -Encoding ASCII
    Write-Log "Created watchdog batch file: $batchFile"
    
    # Create scheduled task
    try {
        $taskName = $ServiceName
        $taskDescription = "ATT Tailscale Watchdog Service - Automatically monitors and maintains Tailscale VPN connection"
        
        # Remove existing task if it exists
        $existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        if ($existingTask) {
            Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
            Write-Log "Removed existing scheduled task: $taskName"
        }
        
        # Create new task
        $action = New-ScheduledTaskAction -Execute $batchFile -WorkingDirectory $WatchdogDir
        $trigger = New-ScheduledTaskTrigger -AtLogOn
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
        $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
        
        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description $taskDescription | Out-Null
        
        Write-Log "Created scheduled task: $taskName" "SUCCESS"
        
        # Start the task
        Start-ScheduledTask -TaskName $taskName
        Write-Log "Started watchdog service" "SUCCESS"
    }
    catch {
        Write-Log "Failed to create scheduled task: $($_.Exception.Message)" "ERROR"
        return $false
    }
    
    return $true
}

function Set-TailscaleConfiguration {
    param([string]$AuthKey)
    
    if (-not $AuthKey) {
        Write-Log "No auth key provided, skipping Tailscale configuration" "WARNING"
        return $true
    }
    
    Write-Log "Configuring Tailscale with provided auth key..."
    
    try {
        # Stop any running Tailscale processes
        Get-Process -Name "tailscale*" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        
        # Get hostname
        $hostname = $env:COMPUTERNAME.ToLower()
        
        # Configure Tailscale
        $configArgs = @(
            "up",
            "--auth-key", $AuthKey,
            "--unattended",
            "--accept-routes",
            "--accept-dns",
            "--force-reauth",
            "--hostname", $hostname
        )
        
        Write-Log "Running: $TailscaleExe $($configArgs -join ' ')"
        $process = Start-Process -FilePath $TailscaleExe -ArgumentList $configArgs -Wait -PassThru -NoNewWindow
        
        if ($process.ExitCode -eq 0) {
            Write-Log "Tailscale configuration completed successfully" "SUCCESS"
        } else {
            Write-Log "Tailscale configuration failed with exit code: $($process.ExitCode)" "WARNING"
            # Don't fail completely, watchdog will retry
        }
    }
    catch {
        Write-Log "Tailscale configuration error: $($_.Exception.Message)" "WARNING"
        # Don't fail completely, watchdog will retry
    }
    
    return $true
}

function Save-Configuration {
    param([string]$AuthKey)
    
    Write-Log "Saving configuration..."
    
    # Create config directory
    if (-not (Test-Path $ConfigDir)) {
        New-Item -ItemType Directory -Path $ConfigDir -Force | Out-Null
    }
    
    # Load template config
    $configTemplate = Join-Path $InstallPath "config.json"
    $config = @{}
    
    if (Test-Path $configTemplate) {
        try {
            $config = Get-Content $configTemplate -Raw | ConvertFrom-Json
        }
        catch {
            Write-Log "Failed to load config template: $($_.Exception.Message)" "WARNING"
        }
    }
    
    # Update with provided values
    if ($AuthKey) {
        $config.tailscale.auth_key = $AuthKey
    }
    
    $config.version = "1.0.0"
    $config.deployment.organization = "ATT Corporation"
    $config.deployment.contact_email = "it-security@att.com"
    
    # Save config
    $configFile = Join-Path $ConfigDir "config.json"
    $config | ConvertTo-Json -Depth 10 | Set-Content -Path $configFile -Encoding UTF8
    
    Write-Log "Configuration saved to: $configFile" "SUCCESS"
    return $true
}

function Remove-TailscaleInstallation {
    Write-Log "Removing Tailscale installation..."
    
    try {
        # Stop and remove scheduled task
        $taskName = $ServiceName
        $existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        if ($existingTask) {
            Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
            Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
            Write-Log "Removed scheduled task: $taskName"
        }
        
        # Stop Tailscale processes
        Get-Process -Name "tailscale*" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        
        # Logout from Tailscale
        if (Test-Path $TailscaleExe) {
            & $TailscaleExe logout --force 2>$null
        }
        
        # Remove directories
        $dirsToRemove = @($WatchdogDir, $ConfigDir, $LogDir)
        foreach ($dir in $dirsToRemove) {
            if (Test-Path $dir) {
                Remove-Item $dir -Recurse -Force -ErrorAction SilentlyContinue
                Write-Log "Removed directory: $dir"
            }
        }
        
        Write-Log "Tailscale removal completed" "SUCCESS"
        return $true
    }
    catch {
        Write-Log "Error during removal: $($_.Exception.Message)" "ERROR"
        return $false
    }
}

# Main execution
function Main {
    Write-Log "ATT Tailscale Installation Script Started"
    Write-Log "Install Path: $InstallPath"
    Write-Log "Auth Key: $(if ($AuthKey) { $AuthKey.Substring(0, [Math]::Min(20, $AuthKey.Length)) + '...' } else { 'Not provided' })"
    Write-Log "Uninstall: $Uninstall"
    Write-Log "Silent: $Silent"
    
    # Check administrator privileges
    if (-not (Test-Administrator)) {
        Write-Log "This script requires administrator privileges. Please run as administrator." "ERROR"
        return 1
    }
    
    if ($Uninstall) {
        Write-Log "Starting uninstall process..."
        $success = Remove-TailscaleInstallation
        if ($success) {
            Write-Log "Uninstall completed successfully" "SUCCESS"
            return 0
        } else {
            Write-Log "Uninstall failed" "ERROR"
            return 1
        }
    }
    
    # Installation process
    Write-Log "Starting installation process..."
    
    try {
        # Step 1: Install Tailscale MSI
        if (-not (Install-TailscaleMSI)) {
            Write-Log "Tailscale MSI installation failed" "ERROR"
            return 1
        }
        
        # Step 2: Setup watchdog service
        if (-not (Setup-WatchdogService)) {
            Write-Log "Watchdog service setup failed" "ERROR"
            return 1
        }
        
        # Step 3: Configure Tailscale
        Set-TailscaleConfiguration -AuthKey $AuthKey
        
        # Step 4: Save configuration
        Save-Configuration -AuthKey $AuthKey
        
        Write-Log "Installation completed successfully" "SUCCESS"
        Write-Log "Watchdog service is running and will monitor Tailscale connection"
        Write-Log "Logs are available at: $LogDir"
        
        return 0
    }
    catch {
        Write-Log "Installation failed: $($_.Exception.Message)" "ERROR"
        return 1
    }
}

# Run main function
exit (Main)
