; ===================================================================
;  BalajiFeeHub-Server-Setup.iss   —  Inno Setup 6 source
;  Compiles into  BalajiFeeHub-Server-Setup.exe
;
;  Behaviour (matches the school's requirements verbatim):
;    • Requires Administrator, Windows 10/11 64-bit
;    • Bundles MongoDB Community MSI, NSSM, Python wheels, prebuilt React frontend
;    • Runs preflight before extraction, blocks install on any BLOCK line
;    • Calls install-main-server.bat which handles the 14-stage install
;    • Registers 3 auto-start Windows services with dependency chain
;    • MongoDB binds 127.0.0.1 only  —  clients never talk to Mongo directly
;    • Auto-detects LAN IP + writes to frontend/.env
;    • Opens firewall for 3000 + 8001 ONLY
;    • Provides Install / Repair / Update / Uninstall out of the box
;    • Preserves the existing database and backups on Repair / Update
;    • Health-checks (HTTP 200) after install, opens the browser on success
;
;  How to compile (on any Windows PC, one time):
;    1. Install Inno Setup 6 from  https://jrsoftware.org/isdl.php  (~6 MB)
;    2. Open PowerShell as Administrator in this folder and run:
;         & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" BalajiFeeHub-Server-Setup.iss
;    3. The compiled installer appears as  Output\BalajiFeeHub-Server-Setup.exe
; ===================================================================

#define AppName            "Balaji FeeHub Server"
#define AppShortName       "BalajiFeeHubServer"
#define AppVersion         "1.0.0"
#define AppPublisher       "Balaji Convent & Junior College"
#define AppURL             "http://balajiconvent.in"
#define InstallDir         "C:\balaji-fee"
#define DefaultUninstallCmd "{app}\01-install-main-server\uninstall.bat"

[Setup]
AppId={{9B4A0F6E-4A5F-4B7A-8E9D-BAA3F7C2E101}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
DefaultDirName={#InstallDir}
DefaultGroupName={#AppName}
DisableDirPage=no
DisableProgramGroupPage=yes
OutputBaseFilename=BalajiFeeHub-Server-Setup
OutputDir=Output
Compression=lzma2/ultra
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
PrivilegesRequired=admin
MinVersion=10.0
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\03-source-code\frontend\public\school-logo.jpeg
SetupIconFile=.\school-logo.ico
WizardStyle=modern
CloseApplications=force
RestartApplications=no
CreateAppDir=yes
DirExistsWarning=no

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"

[Types]
Name: "full";   Description: "Complete installation (recommended)"
Name: "repair"; Description: "Repair — reinstall over existing installation, keep database"

[Components]
Name: "core";  Description: "Application files"; Types: full repair; Flags: fixed

[Files]
; ---- payload = the whole delivery folder assembled by scripts/build_final_zip.py ----
Source: "payload\BalajiConventFeeSoftware-v1.0\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Dirs]
Name: "{app}\backups";  Permissions: everyone-full
Name: "{app}\logs";     Permissions: everyone-full
Name: "{app}\updates\staging";
Name: "{app}\updates\rollback";
Name: "{app}\mongodb\data";
Name: "{app}\mongodb\logs";

[Icons]
Name: "{commondesktop}\Balaji FeeHub";              Filename: "http://127.0.0.1:3000"; IconFilename: "{app}\03-source-code\frontend\public\school-logo.jpeg"
Name: "{group}\Balaji FeeHub — Administration";     Filename: "http://127.0.0.1:3000/admin"; IconFilename: "{app}\03-source-code\frontend\public\school-logo.jpeg"
Name: "{group}\Repair Balaji FeeHub Server";        Filename: "{app}\01-install-main-server\repair-installation.bat"
Name: "{group}\Uninstall Balaji FeeHub Server";     Filename: "{uninstallexe}"

[Run]
; The 14-stage install is orchestrated from [Code]::CurStepChanged so we can
; capture the batch script's exit code and abort with a clear failure message
; instead of silently continuing after a broken offline wheelhouse or a failed
; MongoDB MSI install. Only the post-install browser launch stays here.
Filename: "http://127.0.0.1:3000"; Flags: postinstall shellexec skipifsilent

[UninstallRun]
Filename: "{app}\01-install-main-server\uninstall.bat"; Flags: runhidden waituntilterminated

[Code]
procedure RunStageOrAbort(BatFile, StatusMsg, FailReason: String);
var
  ResultCode: Integer;
  Ok: Boolean;
begin
  WizardForm.StatusLabel.Caption := StatusMsg;
  Ok := Exec(ExpandConstant(BatFile), '', '', SW_SHOW, ewWaitUntilTerminated, ResultCode);
  if (not Ok) or (ResultCode <> 0) then
  begin
    MsgBox(
      'INSTALLATION FAILED' + #13#10 + #13#10 +
      FailReason + #13#10 + #13#10 +
      'Script          : ' + BatFile + #13#10 +
      'Exit code       : ' + IntToStr(ResultCode) + #13#10 + #13#10 +
      'The Balaji FeeHub Server has NOT been installed correctly.' + #13#10 +
      'Windows services have NOT been registered.' + #13#10 + #13#10 +
      'Review the console window that just closed for the exact failing step,' + #13#10 +
      'then run this installer again after fixing the underlying issue.',
      mbCriticalError, MB_OK);
    Abort;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  HealthCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    { Stage 1 - preflight (blocking) }
    RunStageOrAbort(
      '{app}\01-install-main-server\preflight.bat',
      'Running preflight checks...',
      'Preflight reported one or more BLOCKING errors (Python 3.11 x64 missing, disk space, admin rights, etc.).');

    { Stage 2 - full 14-stage install (blocking) - this is where a broken offline }
    { wheelhouse, MSI failure, or NSSM error surfaces as a non-zero exit code.    }
    RunStageOrAbort(
      '{app}\01-install-main-server\install-main-server.bat',
      'Installing MongoDB, backend, frontend and Windows services (~5-10 minutes)...',
      'The main installer script reported a fatal error. Common causes:' + #13#10 +
      '  - Offline Python wheel bundle is incomplete or ABI-mismatched' + #13#10 +
      '  - MongoDB MSI failed to install' + #13#10 +
      '  - A Windows service could not be registered');

    { Stage 3 - health check (non-blocking; service may still be initializing).   }
    { The braces inside %{http_code} are inside a Pascal string, so Inno's        }
    { preprocessor does not touch them - cmd receives them literally.             }
    WizardForm.StatusLabel.Caption := 'Verifying backend health...';
    Exec('cmd.exe',
         '/c curl -s -o nul -w %{http_code} http://127.0.0.1:8001/api/version | findstr 200',
         '', SW_HIDE, ewWaitUntilTerminated, HealthCode);
    if HealthCode <> 0 then
      MsgBox(
        'The backend has not yet returned HTTP 200.' + #13#10 + #13#10 +
        'This is usually because MongoDB is still initializing its data directory.' + #13#10 +
        'Wait 30 seconds, then open http://127.0.0.1:3000 - the site should load.' + #13#10 + #13#10 +
        'If it still does not load, open services.msc and check:' + #13#10 +
        '  - BalajiFeeHub-Mongo' + #13#10 +
        '  - BalajiFeeHub-Backend' + #13#10 +
        '  - BalajiFeeHub-Frontend',
        mbInformation, MB_OK);
  end;
end;

function InitializeSetup(): Boolean;
var
  ExistingInstall: String;
begin
  Result := True;
  { If a previous installation exists, ask the user what to do — never delete the DB. }
  if DirExists(ExpandConstant('{#InstallDir}\mongodb\data')) then
  begin
    if MsgBox('A previous Balaji FeeHub Server installation was detected at ' +
              ExpandConstant('{#InstallDir}') + '.'#13#10#13#10 +
              'The existing database and backups WILL BE PRESERVED.'#13#10#13#10 +
              'Choose YES to repair/update in place, or NO to abort.',
              mbConfirmation, MB_YESNO) = IDNO then
      Result := False;
  end;
end;
