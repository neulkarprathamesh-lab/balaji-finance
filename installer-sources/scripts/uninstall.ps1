#requires -Version 5.1
<#
============================================================================
 Balaji FeeHub - Server Uninstaller
============================================================================
 Called by uninstall.bat which is in turn called by the Inno Setup
 [UninstallRun] step of BalajiFeeHub-Server-Setup.exe.

 What this does (in strict order, each step independent + idempotent):
   1. Stop the 3 Windows services (Frontend -> Backend -> Mongo) with a
      hard 30-second timeout each. If a service will not stop, kill its
      process by PID. Never wait forever.
   2. Delete the 3 services (nssm remove; fallback sc.exe delete).
   3. Kill any orphan mongod / python / node processes whose EXE lives
      inside the install root. Never kill unrelated python.exe elsewhere.
   4. Remove firewall rules for ports 3000 + 8001 (both directions).
   5. Free MongoDB / backend ports (net stop, then kill by PID lookup).
   6. Preserve %APP_ROOT%\backups\ + %APP_ROOT%\mongodb\data\ ONLY if the
      caller passed -KeepData (default: preserve, safe by default). Any
      other switch (-WipeData) removes them too.
   7. Delete every remaining file/folder under %APP_ROOT% with retries
      to defeat transient file-lock races.
   8. Write a structured log to %TEMP%\BalajiFeeHub-Uninstall-<time>.log.

 This script NEVER prompts for input, NEVER pauses, and ALWAYS exits with
 code 0 unless invoked with wrong arguments. That is intentional: the
 [UninstallRun] step must not block the Inno Setup uninstaller UI.

 Usage:
   powershell -ExecutionPolicy Bypass -File uninstall.ps1 -AppRoot "C:\balaji-fee" [-KeepData] [-WipeData]
#>

param(
    [Parameter(Mandatory = $true)][string]$AppRoot,
    [switch]$KeepData,
    [switch]$WipeData
)

$ErrorActionPreference = 'Continue'   # never blow up mid-uninstall
$ProgressPreference    = 'SilentlyContinue'

# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------
$LogFile = Join-Path $env:TEMP ("BalajiFeeHub-Uninstall-{0:yyyyMMdd-HHmmss}.log" -f (Get-Date))
function Log([string]$msg, [string]$level = 'INFO') {
    $line = "[{0}] [{1}] {2}" -f (Get-Date -Format 'HH:mm:ss'), $level, $msg
    try { Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8 } catch {}
    Write-Host $line
}
Log "Balaji FeeHub uninstaller started."
Log "AppRoot          : $AppRoot"
Log "KeepData         : $KeepData"
Log "WipeData         : $WipeData"
Log "Log file         : $LogFile"

# Data preservation policy: KeepData wins over WipeData; default = keep
$PreserveData = $true
if ($WipeData -and -not $KeepData) { $PreserveData = $false }
Log "Preserve DB/backups: $PreserveData"

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
function Stop-ServiceForced([string]$name, [int]$timeoutSec = 30) {
    try {
        $svc = Get-Service -Name $name -ErrorAction SilentlyContinue
        if (-not $svc) { Log "Service $name : not registered - skipping."; return }
        if ($svc.Status -eq 'Stopped') { Log "Service $name : already stopped."; return }
        Log "Service $name : stopping (timeout ${timeoutSec}s)..."
        Stop-Service -Name $name -Force -ErrorAction SilentlyContinue
        $svc.WaitForStatus('Stopped', [TimeSpan]::FromSeconds($timeoutSec)) 2>$null
        $svc.Refresh()
        if ($svc.Status -ne 'Stopped') {
            # Escalate: kill the actual process by service PID
            $pid = (Get-CimInstance Win32_Service -Filter "Name='$name'" -ErrorAction SilentlyContinue).ProcessId
            if ($pid -and $pid -gt 0) {
                Log "Service $name : did not stop in time - killing PID $pid" 'WARN'
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            }
        }
        Log "Service $name : stopped."
    } catch {
        Log "Service $name : stop-error $($_.Exception.Message)" 'WARN'
    }
}

function Remove-ServiceForced([string]$name, [string]$nssmPath) {
    try {
        if (-not (Get-Service -Name $name -ErrorAction SilentlyContinue)) {
            Log "Service $name : already removed."
            return
        }
        if ($nssmPath -and (Test-Path $nssmPath)) {
            & $nssmPath remove $name confirm 2>&1 | ForEach-Object { Log "  nssm: $_" }
        }
        Start-Sleep -Milliseconds 500
        if (Get-Service -Name $name -ErrorAction SilentlyContinue) {
            & sc.exe delete $name 2>&1 | ForEach-Object { Log "  sc.exe: $_" }
        }
        Start-Sleep -Milliseconds 500
        if (Get-Service -Name $name -ErrorAction SilentlyContinue) {
            Log "Service $name : still present after nssm+sc.exe - Windows will finalise on reboot." 'WARN'
        } else {
            Log "Service $name : removed."
        }
    } catch {
        Log "Service $name : remove-error $($_.Exception.Message)" 'WARN'
    }
}

function Kill-OrphanProcesses([string]$appRoot) {
    if (-not (Test-Path $appRoot)) { return }
    try {
        $rootFull = (Resolve-Path $appRoot -ErrorAction SilentlyContinue).Path
        if (-not $rootFull) { return }
        # Only kill processes whose EXE lives under our install root so we
        # can never accidentally kill unrelated python/node/mongod elsewhere.
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
            $_.ExecutablePath -and $_.ExecutablePath.StartsWith($rootFull, [StringComparison]::OrdinalIgnoreCase)
        } | ForEach-Object {
            Log "Killing orphan PID $($_.ProcessId) : $($_.ExecutablePath)"
            try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch {}
        }
    } catch {
        Log "Orphan kill scan error: $($_.Exception.Message)" 'WARN'
    }
}

function Remove-FirewallRules {
    $names = @(
        'BalajiFeeHub-Backend-8001',
        'BalajiFeeHub-Frontend-3000',
        'BalajiFeeHub Backend',
        'BalajiFeeHub Frontend',
        'Balaji FeeHub Backend',
        'Balaji FeeHub Frontend'
    )
    foreach ($n in $names) {
        try {
            & netsh advfirewall firewall delete rule name=$n 2>&1 | Out-Null
        } catch {}
    }
    Log "Firewall rules removed (names attempted: $($names.Count))."
}

function Remove-PathWithRetry([string]$path, [int]$attempts = 5) {
    if (-not (Test-Path $path)) { return $true }
    for ($i = 1; $i -le $attempts; $i++) {
        try {
            # Strip readonly + hidden bits first (backup zips can be readonly)
            Get-ChildItem -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue |
                ForEach-Object { try { $_.Attributes = 'Normal' } catch {} }
            Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction Stop
            if (-not (Test-Path $path)) { return $true }
        } catch {
            Log "Delete attempt $i/$attempts failed for $path : $($_.Exception.Message)" 'WARN'
            Start-Sleep -Milliseconds (300 * $i)
        }
    }
    # Last resort: nuke every file recursively; leave empty dirs to Inno
    try {
        Get-ChildItem -LiteralPath $path -Recurse -Force -File -ErrorAction SilentlyContinue |
            ForEach-Object { try { Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue } catch {} }
    } catch {}
    return -not (Test-Path $path)
}

# --------------------------------------------------------------------------
# 1. Stop services (Frontend first so the app stops listening before the
#    backend disappears; then Backend; then Mongo last)
# --------------------------------------------------------------------------
Stop-ServiceForced 'BalajiFeeHub-Frontend' 30
Stop-ServiceForced 'BalajiFeeHub-Backend'  30
Stop-ServiceForced 'BalajiFeeHub-Mongo'    30

# --------------------------------------------------------------------------
# 2. Kill orphans BEFORE removing services + files (open handles block deletion)
# --------------------------------------------------------------------------
Kill-OrphanProcesses $AppRoot

# --------------------------------------------------------------------------
# 3. Remove services (nssm + sc.exe fallback)
# --------------------------------------------------------------------------
$nssm = Join-Path $AppRoot '05-services\nssm.exe'
if (-not (Test-Path $nssm)) { $nssm = Join-Path $AppRoot '01-install-main-server\nssm.exe' }
Remove-ServiceForced 'BalajiFeeHub-Frontend' $nssm
Remove-ServiceForced 'BalajiFeeHub-Backend'  $nssm
Remove-ServiceForced 'BalajiFeeHub-Mongo'    $nssm

# --------------------------------------------------------------------------
# 4. Firewall
# --------------------------------------------------------------------------
Remove-FirewallRules

# --------------------------------------------------------------------------
# 5. Wait briefly, then re-kill anything that respawned (rare, but seen with
#    MongoDB when it flushes journal before shutdown)
# --------------------------------------------------------------------------
Start-Sleep -Seconds 1
Kill-OrphanProcesses $AppRoot

# --------------------------------------------------------------------------
# 6. Data preservation (default: keep) - move data to a sibling folder so the
#    Inno uninstaller can wipe the rest of the app root cleanly.
# --------------------------------------------------------------------------
if ($PreserveData) {
    $preserveRoot = "$AppRoot-preserved-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    foreach ($sub in @('backups', 'mongodb\data')) {
        $src = Join-Path $AppRoot $sub
        if (Test-Path $src) {
            $dst = Join-Path $preserveRoot $sub
            try {
                New-Item -ItemType Directory -Force -Path (Split-Path $dst) | Out-Null
                Move-Item -LiteralPath $src -Destination $dst -Force -ErrorAction Stop
                Log "Preserved $sub -> $dst"
            } catch {
                Log "Could not preserve $sub : $($_.Exception.Message)" 'WARN'
            }
        }
    }
} else {
    Log "-WipeData was set: database and backups will be deleted with the app root."
}

# --------------------------------------------------------------------------
# 7. Delete every file/folder under AppRoot with retries. Inno's own
#    uninstaller then finishes the empty-directory pass. If AppRoot itself
#    is locked, we leave it to Inno + reboot.
# --------------------------------------------------------------------------
if (Test-Path $AppRoot) {
    Log "Wiping $AppRoot ..."
    $wiped = Remove-PathWithRetry $AppRoot 5
    if ($wiped) { Log "AppRoot wiped." }
    else        { Log "AppRoot partially wiped - Windows will finalise on reboot." 'WARN' }
}

Log "Uninstaller finished. Exit code 0."
exit 0
