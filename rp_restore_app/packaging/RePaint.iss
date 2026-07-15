#define MyAppName "RePaint"
#define MyAppVersion "1.0.1"
#define MyAppPublisher "Katarína Pohanková"
#define MyAppExeName "RePaint.exe"

[Setup]
; Rovnaké AppId ako v pôvodnom RP-Restore inštalátore:
; nová verzia sa bude považovať za aktualizáciu tej istej aplikácie.
AppId={{A4E97E5D-3F13-49AA-91B7-4EC57D7A56C8}

AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
VersionInfoVersion=1.0.1.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Setup
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

OutputDir=..\installer_output
OutputBaseFilename=RePaint-Setup-{#MyAppVersion}
SetupIconFile=RePaint.ico

Compression=lzma2
SolidCompression=yes
WizardStyle=modern

UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}

CloseApplications=yes
RestartApplications=no

[Languages]
Name: "czech"; MessagesFile: "compiler:Languages\Czech.isl"

[Tasks]
Name: "desktopicon"; Description: "Vytvořit zástupce na ploše"; GroupDescription: "Další možnosti:"; Flags: unchecked

[Files]
Source: "..\dist\RePaint\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Upratanie názvov po prípadnej staršej testovacej verzii.
Type: files; Name: "{app}\RP-Restore.exe"
Type: files; Name: "{autoprograms}\RP-Restore.lnk"
Type: files; Name: "{autodesktop}\RP-Restore.lnk"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Spustit {#MyAppName}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent
