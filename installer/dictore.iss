; Dictore Inno Setup Script
; Creates a Windows installer from the PyInstaller --onedir output

#define MyAppName "Dictore"
#define MyAppVersion "1.6.1"
#define MyAppPublisher "infiniV"
#define MyAppURL "https://get-voice-flow.vercel.app/"
#define MyAppSupportURL "https://github.com/infiniV/Dictore/issues"
#define MyAppUpdatesURL "https://github.com/infiniV/Dictore/releases"
#define MyAppExeName "Dictore.exe"

[Setup]
; App identity
AppId={{B8F3A7C2-4D5E-6F01-2345-6789ABCDEF01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppSupportURL}
AppUpdatesURL={#MyAppUpdatesURL}

; Installation settings
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Output settings
OutputDir=..\dist\installer
OutputBaseFilename=DictoreSetup-{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Installer appearance
SetupIconFile=..\src-pyloid\icons\icon.ico

WizardStyle=modern
WizardSizePercent=100

; Uninstaller
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

; Misc
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Start {#MyAppName} when Windows starts"; GroupDescription: "Startup:"; Flags: unchecked

[InstallDelete]
; Wipe the bundled python tree from any prior install before laying down new
; files. Required because some Python wheels change filenames across versions
; (e.g. PyAV 15.x shipped av/codec/codec.cp312-win_amd64.pyd while 17.x ships
; av/codec/codec.abi3.pyd). Without this, an upgrade leaves the older .pyd
; sitting next to the newer one and Python imports the stale version-tagged
; extension first, causing ImportError on missing symbols.
; User data lives in %USERPROFILE%\.Dictore and is NOT affected.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
; Include entire Dictore directory from PyInstaller output
Source: "..\dist\Dictore\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"

; Desktop (optional)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Startup entry (optional)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: startupicon

[Run]
; Option to launch after install
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[Code]
// Kill running instance before uninstall/upgrade
function InitializeUninstall(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  Exec('taskkill', '/F /IM {#MyAppExeName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssInstall then
  begin
    // Kill running instance before install/upgrade
    Exec('taskkill', '/F /IM {#MyAppExeName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;
