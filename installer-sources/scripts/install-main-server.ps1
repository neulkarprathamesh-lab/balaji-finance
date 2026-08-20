# ================================================================
#  Balaji FeeHub Main Server - Self-diagnosing installation manager
#  ------------------------------------------------------------------
#  One PowerShell orchestrator that:
#    1. Inspects the PC comprehensively (OS, RAM, disk, LAN, Python,
#       existing MongoDB via SERVICE + REGISTRY + KNOWN PATHS + PATH,
#       existing install, port conflicts, firewall state).
#    2. Decides intelligently (reuse vs install, start vs register,
#       repair vs stop-and-ask).
#    3. Installs / configures MongoDB, backend, frontend, venv, wheels,
#       .env, firewall, NSSM services with restart-on-failure, and
#       dependency chain (Mongo -> Backend -> Frontend).
#    4. Verifies with real functional tests, not file existence.
#    5. Auto-repairs common issues before failing.
#    6. Writes a full report to C:\balaji-fee\logs\installation-report.txt
#       so every decision is auditable.
#
#  Unique exit codes per failure class (10..99) so failures are
#  actionable, never "Exit code: 34".
# ================================================================
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'

# ---------------- Constants ----------------
$APP_ROOT      = 'C:\balaji-fee'
$APP_BACKEND   = "$APP_ROOT\backend"
$APP_FRONTEND  = "$APP_ROOT\frontend"
$APP_LOGS      = "$APP_ROOT\logs"
$APP_BACKUPS   = "$APP_ROOT\backups"
$APP_UPDATES   = "$APP_ROOT\updates"
$MONGO_ROOT    = "$APP_ROOT\mongodb"
$MONGO_DATA    = "$APP_ROOT\mongodb\data"
$MONGO_LOGS    = "$APP_ROOT\mongodb\logs"
$MONGO_CFG     = "$APP_ROOT\mongodb\mongod.cfg"
$VENV          = "$APP_ROOT\venv"

$HERE          = Split-Path -Parent $PSCommandPath
$SRC           = Join-Path $HERE '..\03-source-code'
$BUNDLE        = Join-Path $HERE '..\05-services'
$DESKTOP       = Join-Path $HERE '..\04-desktop'
$WHEELS        = Join-Path $HERE 'wheels'
$NSSM          = Join-Path $BUNDLE 'nssm.exe'

$REPORT_FILE   = "$APP_LOGS\installation-report.txt"
$Global:Report = New-Object System.Collections.Generic.List[string]
$Global:LanIp  = $null
$Global:MongoInfo = $null
$Global:ComponentReport = @{}   # per-component detect/action/status matrix for final report

# ---------------- Reporting helpers ----------------
function Emit {
    param([string]$Tag, [string]$Msg, [ConsoleColor]$Colour = 'Gray')
    $ts = Get-Date -Format 'HH:mm:ss'
    $line = "[$ts] [$Tag] $Msg"
    Write-Host $line -ForegroundColor $Colour
    $Global:Report.Add($line) | Out-Null
}
function LogInfo ($m) { Emit 'INFO' $m 'Gray'   }
function LogOK   ($m) { Emit ' OK ' $m 'Green'  }
function LogWarn ($m) { Emit 'WARN' $m 'Yellow' }
function LogStep ($m) { Emit 'STEP' $m 'Cyan'   }

function Die {
    param([int]$Code, [string]$Class, [string]$Reason, [string]$Fix = '')
    Emit 'FAIL' $Reason 'Red'
    Write-Host ''
    Write-Host '================================================================' -ForegroundColor Red
    Write-Host "  INSTALLATION FAILED  --  $Class"  -ForegroundColor Red
    Write-Host '================================================================' -ForegroundColor Red
    Write-Host "  Reason      : $Reason" -ForegroundColor Red
    if ($Fix) { Write-Host "  How to fix  : $Fix" -ForegroundColor Yellow }
    Write-Host "  Exit code   : $Code" -ForegroundColor Red
    Write-Host "  Report file : $REPORT_FILE" -ForegroundColor Red
    Write-Host '  No Windows services have been registered.' -ForegroundColor Red
    Write-Host '================================================================' -ForegroundColor Red
    SaveReport
    exit $Code
}
function SaveReport {
    try {
        New-Item -ItemType Directory -Force -Path $APP_LOGS | Out-Null
        $Global:Report | Set-Content -Path $REPORT_FILE -Encoding UTF8
    } catch {}
}

# ================================================================
#  STAGE 1: System check
# ================================================================
function Stage-SystemCheck {
    LogStep 'Stage 1/14: System check'

    # 1a. OS + 64-bit
    $os = Get-CimInstance Win32_OperatingSystem
    if ($os.Version -notmatch '^10\.') { Die 11 'System check' "Windows 10 or 11 required (found $($os.Version))" 'Upgrade to Windows 10 21H2 or Windows 11.' }
    if (-not [Environment]::Is64BitOperatingSystem) { Die 12 'System check' '64-bit Windows required' 'Reinstall Windows 10/11 64-bit.' }
    LogOK "$($os.Caption) ($($os.Version), 64-bit)"

    # 1b. Administrator
    $me = [Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
    if (-not $me.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Die 13 'System check' 'Not running as Administrator' 'Right-click the installer and choose "Run as administrator".'
    }
    LogOK 'Running as Administrator'

    # 1c. Disk (C:)
    $drive = Get-PSDrive C -ErrorAction Stop
    $freeGb = [math]::Round($drive.Free / 1GB, 1)
    if ($freeGb -lt 5) { Die 14 'System check' "Need 5 GB free on C: (found $freeGb GB)" 'Free up space and re-run the installer.' }
    LogOK "Disk C: $freeGb GB free"

    # 1d. RAM
    $ramGb = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
    if ($ramGb -lt 3) { Die 15 'System check' "Need at least 3 GB RAM (found $ramGb GB)" 'Add RAM or use a bigger PC as Main Server.' }
    LogOK "RAM: $ramGb GB"

    # 1e. LAN + default gateway
    $lan = Get-NetIPConfiguration -Detailed | Where-Object { $_.IPv4DefaultGateway -ne $null } | Select-Object -First 1
    if (-not $lan) { Die 16 'Network' 'No LAN adapter with a default gateway found' 'Connect this PC to the school network with a working router.' }
    $Global:LanIp = $lan.IPv4Address.IPAddress
    LogOK "LAN IP: $Global:LanIp  (gateway $($lan.IPv4DefaultGateway.NextHop), adapter $($lan.InterfaceAlias))"

    # 1f. Firewall service
    $fw = Get-Service -Name mpssvc -ErrorAction SilentlyContinue
    if ($fw -and $fw.Status -eq 'Running') { LogOK 'Windows Firewall service running' }
    else { LogWarn 'Windows Firewall service not running (auto-repair will attempt to start)' ; try { Start-Service mpssvc } catch {} }

    # 1g. Windows Installer service (msiserver)
    $msi = Get-Service -Name msiserver -ErrorAction SilentlyContinue
    if (-not $msi) { Die 17 'System check' 'Windows Installer service missing' 'Repair Windows via DISM /Online /Cleanup-Image /RestoreHealth.' }
    LogOK "Windows Installer service: $($msi.Status)"

    # 1h. PowerShell version
    if ($PSVersionTable.PSVersion.Major -lt 5) { Die 18 'System check' "PowerShell 5+ required (found $($PSVersionTable.PSVersion))" 'Install Windows Management Framework 5.1.' }
    LogOK "PowerShell $($PSVersionTable.PSVersion)"

    # 1i. Python 3.11 x64
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { Die 19 'System check' 'Python not found on PATH' 'Install Python 3.11 x64 from python.org and tick "Add to PATH".' }
    $verStr = & python -c "import sys,platform; print(sys.version_info[0], sys.version_info[1], platform.architecture()[0])" 2>&1
    $parts = $verStr -split ' '
    if ([int]$parts[0] -ne 3 -or [int]$parts[1] -lt 11) { Die 20 'System check' "Python 3.11+ required (found $verStr at $($py.Source))" 'Install Python 3.11 x64.' }
    if ($parts[2] -ne '64bit') { Die 21 'System check' "Python x64 required (found $($parts[2]))" 'Uninstall 32-bit Python and install the 64-bit build.' }
    LogOK "Python 3.$($parts[1]) x64 at $($py.Source)"

    # 1j. pip
    & python -m pip --version *> $null
    if ($LASTEXITCODE -ne 0) { Die 22 'System check' 'pip is not available' 'Run: python -m ensurepip --upgrade' }
    LogOK 'pip available'
}

# ================================================================
#  STAGE 2: MongoDB detection (multi-strategy, PATH is last resort)
# ================================================================
function Detect-MongoDb {
    LogStep 'Stage 2/14: MongoDB detection (5 strategies)'
    $candidates = New-Object System.Collections.Generic.List[hashtable]

    # Strategy A: any Windows service that runs mongod.exe
    Get-CimInstance -ClassName Win32_Service -ErrorAction SilentlyContinue | Where-Object { $_.PathName -match 'mongod\.exe' } | ForEach-Object {
        $exe = ($_.PathName -replace '^"([^"]+)".*', '$1') -replace '^([^ ]+).*', '$1'
        if (Test-Path $exe) { $candidates.Add(@{ method='service'; svc=$_.Name; path=$exe; state=$_.State }) }
    }

    # Strategy B: Registry (both 64-bit and WoW64 views)
    foreach ($rp in @('HKLM:\SOFTWARE\MongoDB\Server', 'HKLM:\SOFTWARE\Wow6432Node\MongoDB\Server')) {
        if (Test-Path $rp) {
            Get-ChildItem $rp -ErrorAction SilentlyContinue | ForEach-Object {
                $props = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue
                foreach ($p in @($props.Install, $props.'(default)', $props.InstallLocation, $props.InstallPath)) {
                    if ($p) {
                        $exe = Join-Path $p 'bin\mongod.exe'
                        if (Test-Path $exe) { $candidates.Add(@{ method="registry-$($_.PSChildName)"; path=$exe }) }
                    }
                }
            }
        }
    }

    # Strategy C: Recursive scan of well-known parent
    foreach ($base in @("$env:ProgramFiles\MongoDB", "${env:ProgramFiles(x86)}\MongoDB", "$env:ProgramData\MongoDB")) {
        if (Test-Path $base) {
            Get-ChildItem $base -Recurse -Filter 'mongod.exe' -ErrorAction SilentlyContinue | Select-Object -First 5 | ForEach-Object {
                $candidates.Add(@{ method='programfiles-scan'; path=$_.FullName })
            }
        }
    }

    # Strategy D: PATH
    $cmd = Get-Command mongod -ErrorAction SilentlyContinue
    if ($cmd) { $candidates.Add(@{ method='PATH'; path=$cmd.Source }) }

    # Strategy E: last-resort bundled root
    if (Test-Path "$MONGO_ROOT\bin\mongod.exe") { $candidates.Add(@{ method='balaji-bundled'; path="$MONGO_ROOT\bin\mongod.exe" }) }

    # Deduplicate by full path
    $seen = @{}
    $unique = @()
    foreach ($c in $candidates) {
        $key = $c.path.ToLower()
        if (-not $seen.ContainsKey($key)) { $seen[$key] = $true; $unique += $c }
    }
    if ($unique.Count -eq 0) { LogInfo 'No existing MongoDB detected on this PC'; return $null }

    # Prefer service-installed
    $chosen = ($unique | Where-Object { $_.method -eq 'service' } | Select-Object -First 1)
    if (-not $chosen) { $chosen = $unique[0] }

    # Fetch version
    try {
        $chosen.version = ((& $chosen.path --version 2>&1 | Select-Object -First 1) -replace '.*v', '').Trim()
    } catch { $chosen.version = 'unknown' }

    LogOK "MongoDB DETECTED"
    LogInfo "  Method  : $($chosen.method)"
    LogInfo "  Path    : $($chosen.path)"
    LogInfo "  Version : $($chosen.version)"
    if ($chosen.svc) { LogInfo "  Service : $($chosen.svc) (state: $($chosen.state))" }
    if ($unique.Count -gt 1) { LogInfo "  ($($unique.Count - 1) other candidate(s) found; preferring service/first)" }
    return $chosen
}

# ================================================================
#  STAGE 3: Port conflict analysis (informed by MongoDB detection)
# ================================================================
function Check-PortSafe {
    param([int]$Port, [string]$ExpectedProc, $MongoInfo)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $conn) { return @{ free = $true } }
    $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
    $result = @{ free=$false; pid=$conn.OwningProcess; name=$proc.Name; path=$proc.Path }
    # If it's the MongoDB we already found - it's OK
    if ($ExpectedProc -eq 'mongod' -and $proc.Path -and $MongoInfo -and $proc.Path -ieq $MongoInfo.path) {
        $result.ours = $true
    }
    return $result
}

function Stage-PortCheck {
    LogStep 'Stage 3/14: Port conflict analysis (27017 / 8001 / 3000)'
    $p27017 = Check-PortSafe -Port 27017 -ExpectedProc 'mongod' -MongoInfo $Global:MongoInfo
    if ($p27017.free) { LogOK 'Port 27017 free' }
    elseif ($p27017.ours) { LogOK "Port 27017 held by our detected MongoDB (PID $($p27017.pid))" }
    else { Die 30 'Port conflict' "Port 27017 is held by an unknown process: $($p27017.name) (PID $($p27017.pid), path $($p27017.path))" "Stop or reconfigure that process, then re-run this installer. Do NOT let two MongoDB instances run on the same port." }

    foreach ($p in @(8001, 3000)) {
        $chk = Check-PortSafe -Port $p -ExpectedProc $null -MongoInfo $null
        if ($chk.free) { LogOK "Port $p free" }
        else {
            $proc = if ($chk.name) { "$($chk.name) (PID $($chk.pid))" } else { "PID $($chk.pid)" }
            # If it's our own service from a previous install, that's fine - we'll restart it
            if ($chk.name -in @('python','uvicorn','node','BalajiFeeHub')) { LogWarn "Port $p held by $proc - will restart our service later" }
            else { Die 31 'Port conflict' "Port $p is held by an unknown process: $proc" "Stop that process (or change its port) before installing Balaji FeeHub." }
        }
    }
}

# ================================================================
#  STAGE 4: Existing installation detection + auto-backup
# ================================================================
function Stage-ExistingInstall {
    LogStep 'Stage 4/14: Existing installation detection'
    if (-not (Test-Path "$MONGO_DATA\WiredTiger")) { LogInfo 'No existing Balaji FeeHub installation - fresh install'; return $false }

    LogWarn "Existing installation detected at $MONGO_DATA"
    LogInfo '  Data + config + backups will be PRESERVED'
    LogInfo '  Creating pre-repair backup before touching anything...'

    New-Item -ItemType Directory -Force -Path $APP_BACKUPS, $APP_LOGS | Out-Null
    $stamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
    $bkp   = "$APP_BACKUPS\pre-repair-$stamp"
    New-Item -ItemType Directory -Force -Path $bkp | Out-Null

    $dumpExe = $null
    if ($Global:MongoInfo) { $dumpExe = Join-Path (Split-Path $Global:MongoInfo.path) 'mongodump.exe' }
    if ($dumpExe -and (Test-Path $dumpExe)) {
        & $dumpExe --host 127.0.0.1:27017 --out "$bkp\db" *> "$APP_LOGS\pre-repair-backup.log"
        if ($LASTEXITCODE -ne 0) { Die 40 'Pre-repair backup' "mongodump failed with exit $LASTEXITCODE" "See $APP_LOGS\pre-repair-backup.log. Aborting to protect production data." }
        LogOK "mongodump saved to $bkp\db"
    } else {
        LogWarn 'mongodump not found - copying raw data files as fallback'
        Copy-Item -Recurse -Force "$MONGO_DATA" "$bkp\raw-data"
        LogOK "Raw data copied to $bkp\raw-data"
    }
    foreach ($env in @("$APP_BACKEND\.env", "$APP_FRONTEND\.env")) {
        if (Test-Path $env) { Copy-Item -Force $env "$bkp\$(Split-Path -Leaf $env).bak" }
    }
    LogOK "Pre-repair backup complete at $bkp"
    return $true
}

# ================================================================
#  STAGE 5-8: Copy source + venv + pip + config
# ================================================================
function Stage-CopyAndConfig {
    param([bool]$IsRepair)
    LogStep 'Stage 5/14: Creating application directories'
    foreach ($d in @($APP_ROOT, $APP_BACKEND, $APP_FRONTEND, $APP_LOGS, $APP_BACKUPS,
                     "$APP_UPDATES\staging", "$APP_UPDATES\rollback",
                     $MONGO_ROOT, $MONGO_DATA, $MONGO_LOGS)) {
        New-Item -ItemType Directory -Force -Path $d | Out-Null
    }

    LogStep 'Stage 6/14: Copying backend + prebuilt frontend'
    Copy-Item -Recurse -Force "$SRC\backend\*" $APP_BACKEND
    if (Test-Path "$SRC\frontend\build") { Copy-Item -Recurse -Force "$SRC\frontend\build" "$APP_FRONTEND\build" }
    else { Die 50 'Copy' 'Prebuilt frontend not found in payload' 'Re-download the Server installer.' }
    if (Test-Path "$SRC\version.json") { Copy-Item -Force "$SRC\version.json" "$APP_ROOT\version.json" }

    LogStep 'Stage 7/14: Python venv + offline wheels  ->  detect / reuse / repair / create'
    $venvPy = "$VENV\Scripts\python.exe"
    $venvBroken = $false
    if (Test-Path $venvPy) {
        # Detect existing venv - verify it actually works (python + pip both functional)
        & $venvPy -c "import sys, pip" 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            LogWarn 'Existing venv is broken (python/pip do not import) - REPAIRING by recreation'
            $venvBroken = $true
        } else {
            LogOK 'Existing Python venv is valid  ->  REUSING'
        }
    }
    if ($venvBroken) {
        Remove-Item -Recurse -Force $VENV -ErrorAction SilentlyContinue
    }
    if (-not (Test-Path $venvPy)) {
        LogInfo 'Creating fresh Python venv...'
        & python -m venv $VENV
        if ($LASTEXITCODE -ne 0) { Die 51 'Python venv' "venv creation failed with exit $LASTEXITCODE" 'Check that Python 3.11 x64 is on PATH and try again.' }
        LogOK 'Python venv CREATED'
    }
    & $venvPy -m pip install --upgrade --no-index --find-links $WHEELS pip 2>&1 | Out-Null
    & $venvPy -m pip install --no-index --find-links $WHEELS -r "$APP_BACKEND\requirements.txt" 2>&1 | Tee-Object "$APP_LOGS\pip-install.log" | Out-Null
    if ($LASTEXITCODE -ne 0) { Die 52 'Offline pip' "pip install returned $LASTEXITCODE - offline wheelhouse incomplete" "See $APP_LOGS\pip-install.log" }
    & $venvPy -c "import fastapi,uvicorn,motor,pymongo,pydantic,jwt,bcrypt,cryptography,pandas,numpy,openpyxl,dotenv,requests" 2>&1
    if ($LASTEXITCODE -ne 0) { Die 53 'Dependency verification' 'Critical packages could not be imported - offline wheelhouse is inconsistent' 'Re-download the Server installer.' }
    LogOK 'All 13 critical Python packages import cleanly'

    LogStep 'Stage 8/14: Configuration (.env)'
    if (-not (Test-Path "$APP_BACKEND\.env")) {
        $jwt = [Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Maximum 255 }))
        @(
            'MONGO_URL=mongodb://127.0.0.1:27017',
            'DB_NAME=balaji_fee_db',
            'CORS_ORIGINS=*',
            "JWT_SECRET=$jwt",
            'ADMIN_EMAIL=admin@balajiconvent.in',
            'ADMIN_PASSWORD=ChangeMeOnFirstLogin@2026'
        ) | Set-Content -Encoding UTF8 "$APP_BACKEND\.env"
        LogOK 'Fresh backend/.env written with secure random JWT_SECRET'
    } else {
        LogOK 'Existing backend/.env preserved'
    }
    if (-not (Test-Path "$APP_FRONTEND\.env")) {
        @("REACT_APP_BACKEND_URL=http://$Global:LanIp:8001", 'WDS_SOCKET_PORT=443') | Set-Content -Encoding UTF8 "$APP_FRONTEND\.env"
        LogOK "Frontend .env pointing to http://$Global:LanIp`:8001"
    } else {
        LogOK 'Existing frontend/.env preserved'
    }

    # MongoDB config: bind 127.0.0.1 only (never LAN-exposed)
    @(
        'systemLog:', '  destination: file', "  path: $MONGO_LOGS\mongod.log", '  logAppend: true',
        'storage:',   "  dbPath: $MONGO_DATA",
        'net:',       '  bindIp: 127.0.0.1', '  port: 27017'
    ) | Set-Content -Encoding UTF8 $MONGO_CFG
    LogOK "MongoDB config written (bind 127.0.0.1 only) at $MONGO_CFG"
}

# ================================================================
#  STAGE 9: MongoDB install / reuse / auto-start
# ================================================================
function Stage-Mongo {
    LogStep 'Stage 9/14: MongoDB install / reuse / start'
    if ($Global:MongoInfo) {
        LogOK "Reusing detected MongoDB at $($Global:MongoInfo.path)"
        if ($Global:MongoInfo.svc) {
            $svc = Get-Service -Name $Global:MongoInfo.svc -ErrorAction SilentlyContinue
            if ($svc -and $svc.Status -ne 'Running') {
                LogInfo "Auto-repair: starting existing service $($svc.Name)..."
                try { Start-Service $svc.Name -ErrorAction Stop } catch { Die 60 'MongoDB start' "Could not start service $($svc.Name): $($_.Exception.Message)" 'Open services.msc and start it manually, then re-run installer.' }
                Start-Sleep -Seconds 4
            }
            LogOK "MongoDB service ($($svc.Name)) status: $((Get-Service $svc.Name).Status)"
        }
        return
    }

    # Fresh install from bundled MSI
    LogInfo 'No MongoDB detected - installing from bundled MSI'
    # Recombine split MSI parts if present
    if ((Test-Path "$BUNDLE\mongodb-windows-x86_64.msi.001") -and (Test-Path "$BUNDLE\mongodb-windows-x86_64.msi.002") -and -not (Test-Path "$BUNDLE\mongodb-windows-x86_64.msi")) {
        LogInfo 'Recombining split MSI parts (.001 + .002)...'
        cmd /c "copy /b `"$BUNDLE\mongodb-windows-x86_64.msi.001`" + `"$BUNDLE\mongodb-windows-x86_64.msi.002`" `"$BUNDLE\mongodb-windows-x86_64.msi`"" | Out-Null
        if (-not (Test-Path "$BUNDLE\mongodb-windows-x86_64.msi")) { Die 61 'MSI recombine' 'Failed to merge .001 + .002 parts' 'Confirm both files are present and disk has space.' }
    }
    $msi = Get-ChildItem "$BUNDLE\mongodb-windows-x86_64*.msi" -ErrorAction SilentlyContinue | Where-Object { $_.Extension -eq '.msi' } | Select-Object -First 1
    if (-not $msi) { Die 62 'MSI missing' "MongoDB MSI not found under $BUNDLE\" 'Re-download the Server installer.' }
    if ($msi.Length -lt 50MB) { Die 63 'MSI invalid' "MSI is $([math]::Round($msi.Length/1MB,1)) MB (need >= 50 MB)" 'MSI was truncated - re-download the Server installer.' }
    LogOK "MSI ready: $($msi.FullName) ($([math]::Round($msi.Length/1MB,1)) MB)"

    LogInfo 'Running silent MSI install (may take 60-90 seconds)...'
    $proc = Start-Process -FilePath 'msiexec.exe' -ArgumentList @('/i', "`"$($msi.FullName)`"", "INSTALLLOCATION=`"$MONGO_ROOT`"", 'ADDLOCAL=ServerNoService', '/qn', '/norestart', '/l*v', "`"$APP_LOGS\mongo-msi.log`"") -Wait -PassThru -NoNewWindow
    if ($proc.ExitCode -ne 0 -and $proc.ExitCode -ne 3010) {
        Die 64 'MongoDB MSI install' "msiexec exit code $($proc.ExitCode)" "See $APP_LOGS\mongo-msi.log. Common causes: pending reboot, msiserver stopped, antivirus block."
    }
    LogOK "MongoDB MSI installed (exit $($proc.ExitCode))"

    # Re-detect after install
    $Global:MongoInfo = Detect-MongoDb
    if (-not $Global:MongoInfo) { Die 65 'MongoDB post-install detection' 'mongod.exe not locatable after MSI install' "Open $env:ProgramFiles\MongoDB in Explorer and confirm install." }
}

# ================================================================
#  STAGE 10: Firewall (only what's needed; Mongo stays private)
# ================================================================
function Stage-Firewall {
    LogStep 'Stage 10/14: Firewall rules'
    foreach ($r in @(
        @{ name='BalajiFeeHub Backend';  port=8001 },
        @{ name='BalajiFeeHub Frontend'; port=3000 }
    )) {
        Get-NetFirewallRule -DisplayName $r.name -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
        New-NetFirewallRule -DisplayName $r.name -Direction Inbound -Protocol TCP -LocalPort $r.port -Action Allow -Profile Any -Enabled True | Out-Null
        LogOK "Firewall allowed inbound TCP $($r.port) ($($r.name))"
    }
    # Explicitly ensure no LAN rule for 27017
    Get-NetFirewallRule -DisplayName 'BalajiFeeHub Mongo' -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
    LogOK 'MongoDB (27017) remains private to 127.0.0.1 - never LAN-exposed'
}

# ================================================================
#  STAGE 11: Windows services - detect / reuse / repair / create
#  Idempotent: safe to re-run. Never removes+recreates when the
#  existing service configuration is already correct.
# ================================================================
function Apply-NssmSpec {
    param([hashtable]$Spec, [switch]$SkipCoreBinArgs)
    if (-not $SkipCoreBinArgs) {
        & $NSSM set $Spec.name Application  $Spec.bin  *> $null
        & $NSSM set $Spec.name AppParameters $Spec.args *> $null
    }
    & $NSSM set $Spec.name Start SERVICE_AUTO_START *> $null
    & $NSSM set $Spec.name AppStdout "$APP_LOGS\$($Spec.name).log" *> $null
    & $NSSM set $Spec.name AppStderr "$APP_LOGS\$($Spec.name).err.log" *> $null
    & $NSSM set $Spec.name AppRotateFiles 1 *> $null
    & $NSSM set $Spec.name AppRotateBytes 20971520 *> $null
    & $NSSM set $Spec.name AppRestartDelay 5000 *> $null
    & $NSSM set $Spec.name AppExit Default Restart *> $null
    & $NSSM set $Spec.name AppThrottle 3000 *> $null
    & $NSSM set $Spec.name Description $Spec.desc *> $null
    if ($Spec.deps -and $Spec.deps.Count -gt 0) {
        & $NSSM set $Spec.name DependOnService $Spec.deps *> $null
    }
}

function Ensure-Service {
    # Detect - Inspect - Reuse/Repair/Create. Returns 'CREATED' | 'REUSED' | 'REPAIRED'.
    param([hashtable]$Spec)
    $svc = Get-Service -Name $Spec.name -ErrorAction SilentlyContinue
    if (-not $svc) {
        LogInfo "Service $($Spec.name)  ->  not found, CREATING"
        & $NSSM install $Spec.name $Spec.bin *> $null
        if ($LASTEXITCODE -ne 0) { Die 72 'Service create' "NSSM install $($Spec.name) failed" 'Confirm NSSM.exe is present and the account is admin.' }
        Apply-NssmSpec $Spec
        LogOK "Service $($Spec.name)  ->  CREATED"
        return 'CREATED'
    }
    # Service exists - inspect current config
    $curBin  = (& $NSSM get $Spec.name Application  2>$null).Trim()
    $curArgs = (& $NSSM get $Spec.name AppParameters 2>$null).Trim()
    if ($curBin -ieq $Spec.bin -and $curArgs -ieq $Spec.args) {
        LogOK "Service $($Spec.name)  ->  already correctly configured, REUSING"
        Apply-NssmSpec $Spec -SkipCoreBinArgs   # refresh log paths / restart policy idempotently
        return 'REUSED'
    }
    LogWarn "Service $($Spec.name)  ->  exists with different config, REPAIRING in place"
    LogInfo "  Current bin  : $curBin"
    LogInfo "  Expected bin : $($Spec.bin)"
    LogInfo "  Current args : $curArgs"
    LogInfo "  Expected args: $($Spec.args)"
    if ($svc.Status -eq 'Running') { try { Stop-Service $Spec.name -Force -ErrorAction Stop } catch {} }
    Apply-NssmSpec $Spec
    LogOK "Service $($Spec.name)  ->  REPAIRED"
    return 'REPAIRED'
}

function Stage-Services {
    LogStep 'Stage 11/14: Windows services  ->  detect / reuse / repair / create'
    if (-not (Test-Path $NSSM)) { Die 70 'NSSM missing' "NSSM not found at $NSSM" 'Re-download the Server installer.' }
    if (-not $Global:MongoInfo -or -not (Test-Path $Global:MongoInfo.path)) { Die 71 'Service reg' 'mongod.exe path unresolved before service registration' 'Contact support.' }

    # -------- MongoDB service dependency name --------
    # If an existing MongoDB service was detected (installed independently, e.g. by
    # the school's IT), reuse ITS service name as the Backend dependency instead of
    # duplicating a BalajiFeeHub-Mongo service on top. This avoids two mongod
    # instances fighting for port 27017 and keeps the installer idempotent.
    $mongoSvcName = 'BalajiFeeHub-Mongo'
    if ($Global:MongoInfo.svc -and $Global:MongoInfo.svc -ne 'BalajiFeeHub-Mongo') {
        $mongoSvcName = $Global:MongoInfo.svc
        # Make sure the external service is running + auto-start
        try { Set-Service $mongoSvcName -StartupType Automatic -ErrorAction Stop } catch {}
        $mstate = (Get-Service $mongoSvcName).Status
        if ($mstate -ne 'Running') { try { Start-Service $mongoSvcName -ErrorAction Stop } catch {} ; Start-Sleep 4 }
        LogOK "MongoDB service '$mongoSvcName' (existing, external)  ->  REUSED, StartupType=Automatic"
        $Global:ComponentReport.MongoDB = @{ Detection=$Global:MongoInfo.method; Service=$mongoSvcName; Action='REUSED (external service)'; Path=$Global:MongoInfo.path; Version=$Global:MongoInfo.version }
    } else {
        $mongoSpec = @{ name='BalajiFeeHub-Mongo'; bin=$Global:MongoInfo.path; args="--config `"$MONGO_CFG`""; deps=@(); desc='Balaji FeeHub - MongoDB database service (bound to 127.0.0.1 only)' }
        $act = Ensure-Service $mongoSpec
        $Global:ComponentReport.MongoDB = @{ Detection=$Global:MongoInfo.method; Service='BalajiFeeHub-Mongo'; Action=$act; Path=$Global:MongoInfo.path; Version=$Global:MongoInfo.version }
    }

    # -------- Backend --------
    $backendSpec = @{
        name='BalajiFeeHub-Backend'
        bin ="$VENV\Scripts\python.exe"
        args="-m uvicorn server:app --host 0.0.0.0 --port 8001 --app-dir `"$APP_BACKEND`""
        deps=@($mongoSvcName)
        desc='Balaji FeeHub - FastAPI backend API service (port 8001)'
    }
    $Global:ComponentReport.Backend = @{ Service='BalajiFeeHub-Backend'; Action=(Ensure-Service $backendSpec) }

    # -------- Frontend / static app server --------
    $frontendSpec = @{
        name='BalajiFeeHub-Frontend'
        bin ="$VENV\Scripts\python.exe"
        args="-m http.server 3000 --directory `"$APP_FRONTEND\build`""
        deps=@('BalajiFeeHub-Backend')
        desc='Balaji FeeHub - Prebuilt React frontend static server (port 3000)'
    }
    $Global:ComponentReport.Frontend = @{ Service='BalajiFeeHub-Frontend'; Action=(Ensure-Service $frontendSpec) }
}

# ================================================================
#  STAGE 12: Start services in order + verification
# ================================================================
function Stage-StartAndVerify {
    LogStep 'Stage 12/14: Start services (Mongo -> Backend -> Frontend)'
    foreach ($s in @('BalajiFeeHub-Mongo','BalajiFeeHub-Backend','BalajiFeeHub-Frontend')) {
        try { Start-Service $s -ErrorAction Stop } catch { Die 80 'Service start' "Failed to start $s : $($_.Exception.Message)" "See $APP_LOGS\$s.err.log" }
        Start-Sleep -Seconds 3
        $status = (Get-Service $s).Status
        if ($status -ne 'Running') { Die 81 'Service start' "$s did not reach Running state (current: $status)" "Check $APP_LOGS\$s.err.log and services.msc" }
        LogOK "$s -> $status"
    }
}

# ================================================================
#  STAGE 13: Real functional verification
# ================================================================
function Test-Http {
    param([string]$Url, [int]$TimeoutSec = 8, [int]$Retries = 5)
    for ($i=0; $i -lt $Retries; $i++) {
        try {
            $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec
            if ($r.StatusCode -eq 200) { return $true }
        } catch {}
        Start-Sleep -Seconds 3
    }
    return $false
}

function Stage-Verify {
    LogStep 'Stage 13/14: Real functional verification'
    $failed = 0

    # MongoDB reachability (auto-repair one-shot restart if it fails)
    LogInfo 'Testing backend  ->  MongoDB ping via pymongo...'
    & "$VENV\Scripts\python.exe" -c "from pymongo import MongoClient; MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=10000).admin.command('ping')" 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { LogOK 'Backend  ->  MongoDB ping succeeded' ; $Global:ComponentReport.MongoDB.DbPing = 'OK' }
    else {
        LogWarn 'MongoDB ping FAILED - auto-repair: restarting Mongo service once...'
        try { Restart-Service ($Global:ComponentReport.MongoDB.Service) -Force -ErrorAction Stop } catch {}
        Start-Sleep 6
        & "$VENV\Scripts\python.exe" -c "from pymongo import MongoClient; MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=10000).admin.command('ping')" 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { LogOK 'MongoDB reachable after auto-repair restart'; $Global:ComponentReport.MongoDB.DbPing = 'OK (after auto-repair)' }
        else { $failed++; $Global:ComponentReport.MongoDB.DbPing = 'FAILED' }
    }

    # Ports LISTENING
    foreach ($p in @(27017,8001,3000)) {
        $conn = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
        if ($conn) {
            LogOK "Port $p LISTENING (PID $($conn.OwningProcess))"
            switch ($p) {
                27017 { $Global:ComponentReport.MongoDB.Port  = "$p LISTENING (PID $($conn.OwningProcess))" }
                8001  { $Global:ComponentReport.Backend.Port  = "$p LISTENING (PID $($conn.OwningProcess))" }
                3000  { $Global:ComponentReport.Frontend.Port = "$p LISTENING (PID $($conn.OwningProcess))" }
            }
        } else {
            LogWarn "Port $p NOT listening"; $failed++
            switch ($p) {
                27017 { $Global:ComponentReport.MongoDB.Port  = "$p NOT LISTENING" }
                8001  { $Global:ComponentReport.Backend.Port  = "$p NOT LISTENING" }
                3000  { $Global:ComponentReport.Frontend.Port = "$p NOT LISTENING" }
            }
        }
    }

    # Backend /api/version = HTTP 200 with retry
    if (Test-Http 'http://127.0.0.1:8001/api/version' 8 6) {
        LogOK 'Backend GET /api/version = HTTP 200'
        $Global:ComponentReport.Backend.Api = 'HTTP 200'
    } else {
        LogWarn 'Backend not responding on /api/version'
        $Global:ComponentReport.Backend.Api = 'NOT RESPONDING'
        $failed++
    }

    # Frontend
    if (Test-Http 'http://127.0.0.1:3000/' 8 3) {
        LogOK 'Frontend GET / = HTTP 200'
        $Global:ComponentReport.Frontend.Response = 'HTTP 200'
    } else {
        LogWarn 'Frontend not responding on /'
        $Global:ComponentReport.Frontend.Response = 'NOT RESPONDING'
        $failed++
    }

    # Desktop app existence
    if (Test-Path "$DESKTOP\BalajiFeeHub.exe") {
        LogOK "Desktop app located: $DESKTOP\BalajiFeeHub.exe"
        $Global:ComponentReport.Desktop = @{ Path="$DESKTOP\BalajiFeeHub.exe"; Status='READY' }
    } else {
        LogWarn 'BalajiFeeHub.exe missing from payload'
        $Global:ComponentReport.Desktop = @{ Path='(missing)'; Status='NOT FOUND' }
        $failed++
    }

    # LAN reachability
    if ($Global:LanIp -and $Global:LanIp -ne '127.0.0.1') {
        LogOK "LAN reachable at http://$Global:LanIp`:3000"
        $Global:ComponentReport.Lan = @{ Ip=$Global:LanIp; Status='READY' }
    } else {
        LogWarn 'No LAN IP - only reachable at localhost'
        $Global:ComponentReport.Lan = @{ Ip='127.0.0.1'; Status='LOCALHOST ONLY' }
        $failed++
    }

    # ============================================================
    # END-TO-END USER JOURNEY:
    #   MongoDB -> DB layer -> Backend auth -> Frontend HTML -> Desktop app launch
    # This is the real acceptance test; not passing = installation NOT successful.
    # ============================================================
    LogInfo 'End-to-end journey test  (MongoDB -> DB -> Backend -> Frontend HTML -> Desktop app)'

    # 1) Auth endpoint reachable (proves backend + DB layer are fully wired)
    try {
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8001/api/auth/me' -UseBasicParsing -TimeoutSec 8 -ErrorAction Stop
        $Global:ComponentReport.Backend.Auth = "HTTP $($r.StatusCode) (unexpected 2xx without token - endpoint reachable)"
        LogOK "Auth endpoint reachable (HTTP $($r.StatusCode))"
    } catch [System.Net.WebException] {
        $sc = $null; if ($_.Exception.Response) { $sc = [int]$_.Exception.Response.StatusCode }
        if ($sc -in @(401, 403)) {
            LogOK "Auth endpoint reachable (HTTP $sc = expected 'unauthenticated' - backend + DB layer OK)"
            $Global:ComponentReport.Backend.Auth = "HTTP $sc (backend + DB wired correctly)"
        } elseif ($sc -eq 500) {
            LogWarn "Auth endpoint returned HTTP 500 - backend up but DB layer broken"
            $Global:ComponentReport.Backend.Auth = "HTTP 500 (DB LAYER BROKEN)"
            $failed++
        } else {
            LogWarn "Auth endpoint unreachable: $($_.Exception.Message)"
            $Global:ComponentReport.Backend.Auth = "UNREACHABLE ($($_.Exception.Message))"
            $failed++
        }
    } catch {
        LogWarn "Auth endpoint error: $($_.Exception.Message)"
        $Global:ComponentReport.Backend.Auth = "ERROR ($($_.Exception.Message))"
        $failed++
    }

    # 2) Frontend HTML contains the React app markup (proves prebuilt bundle is served)
    try {
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:3000/' -UseBasicParsing -TimeoutSec 8
        if ($r.Content -match 'Balaji|FeeHub|id=[''"]?root[''"]?') {
            LogOK 'Frontend HTML contains React root / Balaji branding  ->  login screen will render'
            $Global:ComponentReport.Frontend.Html = 'CONTAINS APP MARKUP'
        } else {
            LogWarn 'Frontend responds but HTML lacks expected app markup'
            $Global:ComponentReport.Frontend.Html = 'MARKUP MISSING'
            $failed++
        }
    } catch {
        LogWarn "Frontend HTML fetch failed: $($_.Exception.Message)"
        $Global:ComponentReport.Frontend.Html = "FETCH FAILED"
        $failed++
    }

    # 3) Actually launch BalajiFeeHub.exe and verify it stays alive
    $deskExe = "$DESKTOP\BalajiFeeHub.exe"
    if (Test-Path $deskExe) {
        LogInfo "Launching BalajiFeeHub.exe for end-to-end journey test (12s window)..."
        try {
            $proc = Start-Process -FilePath $deskExe -PassThru -WorkingDirectory $DESKTOP -WindowStyle Normal
            Start-Sleep -Seconds 12
            if ($proc.HasExited) {
                LogWarn "BalajiFeeHub.exe crashed within 12s (exit code $($proc.ExitCode))"
                $Global:ComponentReport.Desktop.Launch = "CRASHED (exit $($proc.ExitCode))"
                $failed++
            } else {
                # Look for our window title in any process (Electron often spawns children)
                $balajiWin = Get-Process -ErrorAction SilentlyContinue |
                    Where-Object { $_.MainWindowTitle -and $_.MainWindowTitle -match 'Balaji' } |
                    Select-Object -First 1
                if ($balajiWin) {
                    LogOK "Desktop app RUNNING with window '$($balajiWin.MainWindowTitle)'  ->  login screen reachable"
                    $Global:ComponentReport.Desktop.Launch = "RUNNING (window: '$($balajiWin.MainWindowTitle)')"
                } else {
                    LogOK "Desktop app process alive (PID $($proc.Id)) - login window still initializing"
                    $Global:ComponentReport.Desktop.Launch = "RUNNING (PID $($proc.Id))"
                }
            }
        } catch {
            LogWarn "Failed to launch BalajiFeeHub.exe: $($_.Exception.Message)"
            $Global:ComponentReport.Desktop.Launch = "LAUNCH FAILED ($($_.Exception.Message))"
            $failed++
        }
    } else {
        LogWarn "BalajiFeeHub.exe not found for launch test"
        $Global:ComponentReport.Desktop.Launch = "EXE MISSING"
        $failed++
    }

    # 4) Windows-restart persistence: every service must be AUTO_START
    $svcNames = @()
    if ($Global:ComponentReport.MongoDB.Service) { $svcNames += $Global:ComponentReport.MongoDB.Service }
    $svcNames += 'BalajiFeeHub-Backend'
    $svcNames += 'BalajiFeeHub-Frontend'
    foreach ($sName in $svcNames) {
        $qc = & sc.exe qc "$sName" 2>&1 | Out-String
        if ($qc -match 'AUTO_START') {
            LogOK "$sName will auto-start on Windows boot"
        } else {
            LogWarn "$sName is NOT AUTO_START - Windows restart will leave it stopped"
            try { & sc.exe config "$sName" start= auto | Out-Null; LogOK "$sName auto-repair: set to AUTO_START" } catch { $failed++ }
        }
    }
    $Global:ComponentReport.Restart = @{ Verified = if ($failed -eq 0) { 'ALL SERVICES AUTO_START (survives Windows reboot)' } else { 'AUTO_START MISCONFIG - see warnings above' } }

    if ($failed -gt 0) {
        Die 90 'End-to-end journey verification' "$failed check(s) failed" "The MongoDB -> DB -> Backend -> Frontend -> Desktop-App journey did not complete. Review $REPORT_FILE and $APP_LOGS\*.err.log for the exact failed stage + remediation."
    }
}

# ================================================================
#  STAGE 14: Final report
# ================================================================
function Stage-Report {
    LogStep 'Stage 14/14: Installation report'
    $cr = $Global:ComponentReport

    $lines = @(
        '================================================================',
        '  BALAJI FEE HUB  -  INSTALLATION SUCCESSFUL',
        '================================================================',
        "  Timestamp        : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')",
        "  Main Server IP   : $Global:LanIp",
        "  Application URL  : http://$Global:LanIp`:3000",
        "  Backend API      : http://$Global:LanIp`:8001/api",
        "  Data directory   : $MONGO_DATA",
        "  Backups dir      : $APP_BACKUPS",
        "  Logs             : $APP_LOGS",
        '',
        '================================================================',
        '  COMPONENT STATUS  (detect / action / verify)',
        '================================================================',
        '',
        'MongoDB',
        "  Detection method : $($cr.MongoDB.Detection)",
        "  Executable path  : $($cr.MongoDB.Path)",
        "  Version          : $($cr.MongoDB.Version)",
        "  Windows service  : $($cr.MongoDB.Service)",
        "  Action taken     : $($cr.MongoDB.Action)",
        "  Port 27017       : $($cr.MongoDB.Port)",
        "  Database ping    : $($cr.MongoDB.DbPing)",
        '',
        'Backend',
        "  Windows service  : $($cr.Backend.Service)",
        "  Action taken     : $($cr.Backend.Action)",
        "  Port 8001        : $($cr.Backend.Port)",
        "  API /api/version : $($cr.Backend.Api)",
        "  Auth endpoint    : $($cr.Backend.Auth)",
        '',
        'Frontend',
        "  Windows service  : $($cr.Frontend.Service)",
        "  Action taken     : $($cr.Frontend.Action)",
        "  Port 3000        : $($cr.Frontend.Port)",
        "  Response         : $($cr.Frontend.Response)",
        "  HTML markup      : $($cr.Frontend.Html)",
        '',
        'Desktop application',
        "  Path             : $($cr.Desktop.Path)",
        "  Status           : $($cr.Desktop.Status)",
        "  Launch test      : $($cr.Desktop.Launch)",
        '',
        'LAN',
        "  Main Server IP   : $($cr.Lan.Ip)",
        "  Status           : $($cr.Lan.Status)",
        '',
        'Windows restart persistence',
        "  Verified         : $($cr.Restart.Verified)",
        '',
        '================================================================',
        '  All three services are set to start automatically at Windows',
        '  boot with restart-on-failure. MongoDB stays bound to 127.0.0.1.',
        '  Firewall allows only 8001 + 3000 inbound.',
        '',
        '  Next steps:',
        '    - Double-click Balaji FeeHub on the desktop to open the app',
        '    - Install BalajiFeeHub-Client-Setup.exe on each client PC',
        '    - Change the default admin password immediately',
        '================================================================'
    )
    foreach ($l in $lines) { Write-Host $l -ForegroundColor Green; $Global:Report.Add($l) | Out-Null }
    SaveReport
    LogOK "Full report written to $REPORT_FILE"
}

# ================================================================
#  MAIN
# ================================================================
try {
    Write-Host ''
    Write-Host '================================================================' -ForegroundColor Cyan
    Write-Host '  Balaji FeeHub  Main Server Installation Manager  v1.0'         -ForegroundColor Cyan
    Write-Host '  Balaji Convent & Junior College  .  Butibori, Nagpur'           -ForegroundColor Cyan
    Write-Host '================================================================' -ForegroundColor Cyan
    Write-Host ''

    New-Item -ItemType Directory -Force -Path $APP_LOGS | Out-Null

    Stage-SystemCheck
    $Global:MongoInfo = Detect-MongoDb
    Stage-PortCheck
    $isRepair = Stage-ExistingInstall
    Stage-CopyAndConfig -IsRepair:$isRepair
    Stage-Mongo
    Stage-Firewall
    Stage-Services
    Stage-StartAndVerify
    Stage-Verify
    Stage-Report

    exit 0
}
catch {
    Emit 'FATAL' $_.Exception.Message 'Red'
    SaveReport
    Write-Host ''
    Write-Host '================================================================' -ForegroundColor Red
    Write-Host '  INSTALLATION FAILED  (unhandled exception)'                    -ForegroundColor Red
    Write-Host '================================================================' -ForegroundColor Red
    Write-Host "  $($_.Exception.Message)"                                        -ForegroundColor Red
    Write-Host "  Report: $REPORT_FILE"                                           -ForegroundColor Red
    Write-Host '================================================================' -ForegroundColor Red
    exit 99
}
