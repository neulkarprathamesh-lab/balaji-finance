; ===================================================================
;  BalajiFeeHub-Client-Setup.iss   --  Inno Setup 6 source
;  Compiles into  BalajiFeeHub-Client-Setup.exe
;
;  Installs the native Electron desktop shell (BalajiFeeHub.exe) into
;  Program Files\BalajiFeeHub. The application auto-discovers the Main
;  Server on the school LAN and saves the successful IP under
;  %APPDATA%\BalajiFeeHub\config.json so the user never has to type it
;  again. No Python, no MongoDB, no Node, no Chrome, no WebView2 is
;  required on the client PC -- Electron ships everything it needs.
; ===================================================================

#define AppName            "Balaji FeeHub"
#define AppVersion         "1.0.0"
#define AppPublisher       "Balaji Convent & Junior College"

[Setup]
AppId={{9B4A0F6E-4A5F-4B7A-8E9D-BAA3F7C2E102}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\BalajiFeeHub
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputBaseFilename=BalajiFeeHub-Client-Setup
OutputDir=Output
Compression=lzma2/max
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
PrivilegesRequired=admin
MinVersion=10.0
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\BalajiFeeHub.exe
SetupIconFile=.\school-logo.ico
WizardStyle=modern

[Files]
Source: "payload\BalajiConventFeeSoftware-v1.0\04-desktop\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{commondesktop}\Balaji FeeHub"; Filename: "{app}\BalajiFeeHub.exe"; IconFilename: "{app}\BalajiFeeHub.exe"; WorkingDir: "{app}"
Name: "{autoprograms}\Balaji FeeHub"; Filename: "{app}\BalajiFeeHub.exe"; IconFilename: "{app}\BalajiFeeHub.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\BalajiFeeHub.exe"; WorkingDir: "{app}"; Flags: postinstall nowait skipifsilent; Description: "Launch Balaji FeeHub"
