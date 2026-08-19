; ===================================================================
;  BalajiFeeHub-Client-Setup.iss   —  Inno Setup 6 source
;  Compiles into  BalajiFeeHub-Client-Setup.exe   (~150 KB)
;
;  Client PCs need only Windows 10/11 64-bit + Chrome or Edge.
;  No Python, Node, MongoDB, wheels or backend code is installed.
;  Runs install-client-pc.bat which:
;    • Detects Chrome/Edge
;    • Auto-discovers the Main Server on the LAN (10-second parallel scan)
;    • Manual-IP fallback with verification
;    • Creates Desktop + Start Menu shortcuts
;    • Opens the app
;
;  Compile the same way:
;    & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" BalajiFeeHub-Client-Setup.iss
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
SetupIconFile=.\school-logo.ico
WizardStyle=modern

[Files]
Source: "payload\BalajiConventFeeSoftware-v1.0\02-install-client-pc\*";        DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "payload\BalajiConventFeeSoftware-v1.0\03-source-code\frontend\public\school-logo.jpeg"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; The final shortcut targets are created by install-client-pc.bat once the server has been discovered.

[Run]
Filename: "{app}\install-client-pc.bat"; StatusMsg: "Discovering Balaji FeeHub Main Server on the LAN..."; Flags: waituntilterminated

[UninstallRun]
Filename: "{app}\uninstall-client-pc.bat"; Flags: runhidden waituntilterminated
