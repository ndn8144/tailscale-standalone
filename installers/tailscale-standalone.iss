; Inno Setup Script for ATT Tailscale Standalone Installer
; Tích hợp với PyInstaller build và PowerShell post-install script

#ifndef AppVersion
#define AppVersion "1.0.0"
#endif

#ifndef AppBinDir
#define AppBinDir "builds\dist"
#endif

#ifndef AuthKey
#define AuthKey ""
#endif

#ifndef AppExeName
#define AppExeName "TailscaleInstaller.exe"
#endif

#define MyAppName       "ATT Tailscale Standalone"
#define MyAppPublisher  "ATT Corporation"
#define MyAppURL        "https://tailscale.com"
#define MyAppExeName    AppExeName
#define MyAppVersion    AppVersion
#define MyAppBinDir     AppBinDir
#define MyAuthKey       AuthKey

[Setup]
AppId={{A6E1C8A9-0B8B-4C0C-9F9D-ATT-Tailscale-Standalone}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableDirPage=no
DisableProgramGroupPage=no
OutputDir=builds\installer
OutputBaseFilename=ATT-Tailscale-Standalone-Setup-{#MyAppVersion}
Compression=lzma2/ultra
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
SetupLogging=yes
MinVersion=6.1sp1
WizardStyle=modern
WizardSizePercent=120
WizardResizable=yes
; Optional: ký số nếu có chứng thư
; SignTool=your_signtool_profile
; SignedUninstaller=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
english.InstallTailscale=Install Tailscale VPN
english.InstallTailscaleDesc=This will install Tailscale VPN client and configure it with your organization's settings.

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"
Name: "quicklaunchicon"; Description: "Create a &Quick Launch shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked
Name: "installtailscale"; Description: "{cm:InstallTailscale}"; GroupDescription: "Installation options:"; Flags: checkedonce
Name: "startwatchdog"; Description: "Start watchdog service automatically"; GroupDescription: "Service options:"; Flags: checkedonce

[Files]
; App EXE (PyInstaller build)
Source: "{#MyAppBinDir}\TailscaleInstaller*.exe"; DestDir: "{app}"; Flags: ignoreversion

; PowerShell installation script
Source: "..\templates\install_script.ps1"; DestDir: "{app}"; Flags: ignoreversion

; Configuration template
Source: "..\templates\config_template.json"; DestDir: "{app}"; Flags: ignoreversion; DestName: "config.json"

; Watchdog service script
Source: "..\src\att_tailscale_watchdog.py"; DestDir: "{app}\watchdog"; Flags: ignoreversion

; README and documentation
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion; DestName: "README.txt"

; Optional: Include MSI if available (for offline installation)
Source: "..\temp\tailscale-*.msi"; DestDir: "{app}\temp"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: quicklaunchicon

[Registry]
; Store installation information
Root: HKLM; Subkey: "Software\{#MyAppName}"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\{#MyAppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\{#MyAppName}"; ValueType: string; ValueName: "InstallDate"; ValueData: "{code:GetInstallDate}"; Flags: uninsdeletekey

; Store auth key securely (if provided)
Root: HKLM; Subkey: "Software\{#MyAppName}\Config"; ValueType: string; ValueName: "AuthKey"; ValueData: "{#MyAuthKey}"; Flags: uninsdeletekey; Check: CheckAuthKey

; Environment variables for PowerShell scripts
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueType: expandsz; ValueName: "ATT_TAILSCALE_PATH"; ValueData: "{app}"; Flags: uninsdeletevalue

[Run]
; Run main installer if task is selected
Filename: "{app}\{#MyAppExeName}"; Parameters: "--install"; Flags: runhidden; Tasks: installtailscale

; Run PowerShell post-installation script
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NoProfile -File ""{app}\install_script.ps1"" -InstallPath ""{app}"" -AuthKey ""{#MyAuthKey}"""; Flags: runhidden; Tasks: installtailscale; Check: CheckAuthKey

; Start watchdog service if task is selected
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NoProfile -Command ""Start-Service -Name 'ATT_Tailscale_Watchdog' -ErrorAction SilentlyContinue"""; Flags: runhidden; Tasks: startwatchdog

[UninstallRun]
; Stop and remove watchdog service
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NoProfile -Command ""Stop-Service -Name 'ATT_Tailscale_Watchdog' -ErrorAction SilentlyContinue; Remove-Service -Name 'ATT_Tailscale_Watchdog' -ErrorAction SilentlyContinue"""; Flags: runhidden

; Clean up Tailscale installation (optional)
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NoProfile -Command ""& '{app}\install_script.ps1' -Uninstall"""; Flags: runhidden

[UninstallDelete]
Type: filesandordirs; Name: "{app}\temp"
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\watchdog"

[Code]

function GetInstallDate(Param: String): String;
begin
  Result := GetDateTimeString('yyyy-mm-dd hh:nn:ss', #0, #0);
end;


function CheckAuthKey: Boolean;
begin
  Result := (ExpandConstant('{#MyAuthKey}') <> '') and (Pos('tskey-auth-', ExpandConstant('{#MyAuthKey}')) > 0);
end;

function InitializeSetup(): Boolean;
begin
  // Check if running as administrator
  if not IsAdminLoggedOn then
  begin
    MsgBox('This installer requires administrator privileges.' + #13#10 + 
           'Please run as administrator.', mbError, MB_OK);
    Result := False;
    Exit;
  end;
  
  // Check Windows version
  if not IsWin64 then
  begin
    MsgBox('This installer requires 64-bit Windows.', mbError, MB_OK);
    Result := False;
    Exit;
  end;
  
  Result := True;
end;

function InitializeUninstall(): Boolean;
begin
  // Check if running as administrator
  if not IsAdminLoggedOn then
  begin
    MsgBox('Uninstaller requires administrator privileges.' + #13#10 + 
           'Please run as administrator.', mbError, MB_OK);
    Result := False;
    Exit;
  end;
  
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Create additional directories
    ForceDirectories(ExpandConstant('{app}\logs'));
    ForceDirectories(ExpandConstant('{app}\temp'));
    ForceDirectories(ExpandConstant('{app}\config'));
  end;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  // Skip auth key page if already provided via parameter
  if (PageID = wpSelectTasks) and (ExpandConstant('{#MyAuthKey}') <> '') then
    Result := False
  else
    Result := False;
end;

