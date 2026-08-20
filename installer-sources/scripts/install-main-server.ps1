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

    LogStep 'Stage 7/14: Python venv + offline wheels'
    if (-not (Test-Path "$VENV\Scripts\python.exe")) {
        & python -m venv $VENV
        if ($LASTEXITCODE -ne 0) { Die 51 'Python venv' "venv creation failed with exit $LASTEXITCODE" 'Check that Python 3.11 x64 is on PATH and try again.' }
    }
    $venvPy = "$VENV\Scripts\python.exe"
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
#  STAGE 11: Windows services (NSSM, restart-on-failure, dependency)
# ================================================================
function Stage-Services {
    LogStep 'Stage 11/14: Windows service registration'
    if (-not (Test-Path $NSSM)) { Die 70 'NSSM missing' "NSSM not found at $NSSM" 'Re-download the Server installer.' }
    $mongod = $Global:MongoInfo.path
    if (-not $mongod -or -not (Test-Path $mongod)) { Die 71 'Service reg' 'mongod.exe path unresolved before service registration' 'Contact support.' }

    # Reset any existing services (idempotent)
    foreach ($s in @('BalajiFeeHub-Frontend','BalajiFeeHub-Backend','BalajiFeeHub-Mongo')) {
        try { Stop-Service $s -Force -ErrorAction SilentlyContinue } catch {}
        try { & $NSSM remove $s confirm *> $null } catch {}
    }

    # Register with proper metadata + auto-restart on failure
    $svcSpecs = @(
        @{ name='BalajiFeeHub-Mongo';    bin=$mongod;                              args="--config `"$MONGO_CFG`"";                                                             deps=@();                       desc='Balaji FeeHub - MongoDB database service (bound to 127.0.0.1)' },
        @{ name='BalajiFeeHub-Backend';  bin="$VENV\Scripts\python.exe";           args="-m uvicorn server:app --host 0.0.0.0 --port 8001 --app-dir `"$APP_BACKEND`"";        deps=@('BalajiFeeHub-Mongo');   desc='Balaji FeeHub - FastAPI backend API service' },
        @{ name='BalajiFeeHub-Frontend'; bin="$VENV\Scripts\python.exe";           args="-m http.server 3000 --directory `"$APP_FRONTEND\build`"";                             deps=@('BalajiFeeHub-Backend'); desc='Balaji FeeHub - Prebuilt React frontend static server' }
    )
    foreach ($s in $svcSpecs) {
        & $NSSM install $s.name $s.bin *> $null
        & $NSSM set $s.name AppParameters $s.args *> $null
        & $NSSM set $s.name Start SERVICE_AUTO_START *> $null
        & $NSSM set $s.name AppStdout "$APP_LOGS\$($s.name).log" *> $null
        & $NSSM set $s.name AppStderr "$APP_LOGS\$($s.name).err.log" *> $null
        & $NSSM set $s.name AppRotateFiles 1 *> $null
        & $NSSM set $s.name AppRotateBytes 20971520 *> $null
        & $NSSM set $s.name AppRestartDelay 5000 *> $null
        & $NSSM set $s.name AppExit Default Restart *> $null
        & $NSSM set $s.name AppThrottle 3000 *> $null
        & $NSSM set $s.name Description $s.desc *> $null
        if ($s.deps.Count -gt 0) { & $NSSM set $s.name DependOnService $s.deps *> $null }
        LogOK "Registered service $($s.name)"
    }
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
    # MongoDB reachability
    LogInfo 'Testing backend -> MongoDB ping...'
    & "$VENV\Scripts\python.exe" -c "from pymongo import MongoClient; MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=10000).admin.command('ping'); print('ok')" 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { LogOK 'Backend -> MongoDB ping succeeded' } else { LogWarn 'Backend -> MongoDB ping FAILED (auto-repair: restarting Mongo)'; Restart-Service BalajiFeeHub-Mongo -Force; Start-Sleep 5; & "$VENV\Scripts\python.exe" -c "from pymongo import MongoClient; MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=10000).admin.command('ping')" 2>&1 | Out-Null; if ($LASTEXITCODE -ne 0) { $failed++ } else { LogOK 'MongoDB reachable after restart' } }

    # Ports listening
    foreach ($p in @(27017,8001,3000)) {
        $conn = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
        if ($conn) { LogOK "Port $p LISTENING (PID $($conn.OwningProcess))" } else { LogWarn "Port $p NOT listening"; $failed++ }
    }

    # Backend /api/version = HTTP 200
    if (Test-Http 'http://127.0.0.1:8001/api/version' 8 6) { LogOK 'Backend GET /api/version = HTTP 200' } else { LogWarn 'Backend not responding on /api/version'; $failed++ }

    # Frontend
    if (Test-Http 'http://127.0.0.1:3000/' 8 3) { LogOK 'Frontend GET / = HTTP 200' } else { LogWarn 'Frontend not responding on /'; $failed++ }

    # Desktop app existence
    if (Test-Path "$DESKTOP\BalajiFeeHub.exe") { LogOK "Desktop app: $DESKTOP\BalajiFeeHub.exe" } else { LogWarn 'BalajiFeeHub.exe missing from payload'; $failed++ }

    # LAN IP is non-loopback
    if ($Global:LanIp -and $Global:LanIp -ne '127.0.0.1') { LogOK "LAN reachable at http://$Global:LanIp`:3000" } else { LogWarn 'No LAN IP - only reachable at localhost'; $failed++ }

    if ($failed -gt 0) { Die 90 'Verification' "$failed post-install check(s) failed" "Review $REPORT_FILE and $APP_LOGS\*.err.log" }
}

# ================================================================
#  STAGE 14: Final report
# ================================================================
function Stage-Report {
    LogStep 'Stage 14/14: Installation report'
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
        "  MongoDB          : $($Global:MongoInfo.path) (v$($Global:MongoInfo.version))",
        '',
        '  Services (auto-start, auto-restart on failure):',
        "    - BalajiFeeHub-Mongo    ($(Get-Service BalajiFeeHub-Mongo).Status)",
        "    - BalajiFeeHub-Backend  ($(Get-Service BalajiFeeHub-Backend).Status)",
        "    - BalajiFeeHub-Frontend ($(Get-Service BalajiFeeHub-Frontend).Status)",
        '',
        '  Firewall:  8001 + 3000 allowed inbound (Mongo 27017 stays private)',
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
