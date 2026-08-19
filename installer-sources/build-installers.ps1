# Balaji FeeHub — One-command Windows EXE builder
# Run on any Windows 10/11 PC (any user account works — Admin required only for the final EXE install).
#
#   powershell -ExecutionPolicy Bypass -File build-installers.ps1
#
# Result:  .\Output\BalajiFeeHub-Server-Setup.exe   (~600 MB)
#          .\Output\BalajiFeeHub-Client-Setup.exe   (~150 KB)
#          .\Output\SHA256SUMS.txt
#
# The script is idempotent — safe to re-run after a failure.
[CmdletBinding()]
param(
  [string]$Base = "https://finance-hub-school.preview.emergentagent.com/downloads"
)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

function step($msg) { Write-Host "`n==>  $msg" -ForegroundColor Cyan }
function ok($msg)   { Write-Host "     $msg"   -ForegroundColor Green }

step "1/7  Installing Inno Setup 6 (if missing)"
$iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) {
    $exe = "$env:TEMP\innosetup-6.2.2.exe"
    Invoke-WebRequest "https://files.jrsoftware.org/is/6/innosetup-6.2.2.exe" -OutFile $exe
    Start-Process $exe -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART" -Wait
    Remove-Item $exe -Force
}
if (-not (Test-Path $iscc)) { throw "Inno Setup did not install to the expected path — install it manually and re-run." }
ok "Inno Setup ready"

step "2/7  Downloading payload (CORE zip + MongoDB MSI parts)"
New-Item -ItemType Directory -Force -Path work | Out-Null
$files = @(
  "BalajiConventFeeSoftware_v1.0_CORE.zip",
  "mongodb-windows-x86_64.msi.001",
  "mongodb-windows-x86_64.msi.002",
  "installer-sources.zip"
)
foreach ($f in $files) {
    $dest = "work\$f"
    if (Test-Path $dest) { ok "cached  $f"; continue }
    Write-Host "     downloading $f ..." -NoNewline
    Invoke-WebRequest "$Base/$f" -OutFile $dest
    Write-Host " done"
}

step "3/7  Verifying SHA-256 checksums"
$sha = (Invoke-WebRequest "$Base/SHA256SUM.txt").Content -split "`n"
$expected = @{}
foreach ($line in $sha) {
    if ($line -match "^([0-9a-f]{64})\s+(.+)$") { $expected[$Matches[2].Trim()] = $Matches[1].ToLower() }
}
foreach ($f in "BalajiConventFeeSoftware_v1.0_CORE.zip","mongodb-windows-x86_64.msi.001","mongodb-windows-x86_64.msi.002") {
    if (-not $expected.ContainsKey($f)) { continue }
    $got = (Get-FileHash "work\$f" -Algorithm SHA256).Hash.ToLower()
    if ($got -ne $expected[$f]) { throw "SHA-256 mismatch on $f — delete work\$f and re-run." }
    ok "sha256 OK  $f"
}

step "4/7  Extracting CORE + installer sources"
Expand-Archive -Force "work\BalajiConventFeeSoftware_v1.0_CORE.zip" -DestinationPath "work\dist\BalajiConventFeeSoftware-v1.0"
Expand-Archive -Force "work\installer-sources.zip"                 -DestinationPath "work"
ok "extracted"

step "5/7  Recombining the MongoDB MSI (001 + 002) inside 05-services"
$svc = "work\dist\BalajiConventFeeSoftware-v1.0\05-services"
Copy-Item "work\mongodb-windows-x86_64.msi.001" "$svc\mongodb-windows-x86_64.msi.001" -Force
Copy-Item "work\mongodb-windows-x86_64.msi.002" "$svc\mongodb-windows-x86_64.msi.002" -Force
cmd /c "copy /b `"$svc\mongodb-windows-x86_64.msi.001`" + `"$svc\mongodb-windows-x86_64.msi.002`" `"$svc\mongodb-windows-x86_64.msi`"" | Out-Null
$msiSize = (Get-Item "$svc\mongodb-windows-x86_64.msi").Length
if ($msiSize -lt 500MB) { throw "Recombined MSI is only $msiSize bytes — parts did not join correctly." }
ok ("recombined MSI: {0:N2} MB" -f ($msiSize/1MB))
# Delete the parts so the server EXE payload contains only the joined file
Remove-Item "$svc\mongodb-windows-x86_64.msi.001","$svc\mongodb-windows-x86_64.msi.002" -Force

step "6/7  Compiling both installers with Inno Setup"
Push-Location work\installer-sources
& $iscc BalajiFeeHub-Server-Setup.iss  | Tee-Object -Variable serverLog
& $iscc BalajiFeeHub-Client-Setup.iss  | Tee-Object -Variable clientLog
Pop-Location

$out = Join-Path $here "Output"
New-Item -ItemType Directory -Force -Path $out | Out-Null
Move-Item -Force work\installer-sources\Output\BalajiFeeHub-Server-Setup.exe $out
Move-Item -Force work\installer-sources\Output\BalajiFeeHub-Client-Setup.exe $out

step "7/7  SHA-256"
$sums = @()
foreach ($e in "BalajiFeeHub-Server-Setup.exe","BalajiFeeHub-Client-Setup.exe") {
    $p = Join-Path $out $e
    $h = (Get-FileHash $p -Algorithm SHA256).Hash.ToLower()
    $s = (Get-Item $p).Length
    $sums += "$h  $e"
    ok ("{0,-38}  {1,10:N0} bytes  {2}" -f $e,$s,$h)
}
$sums -join "`n" | Set-Content (Join-Path $out "SHA256SUMS.txt")

Write-Host "`nDONE.  Two EXE files ready in .\Output\" -ForegroundColor Green
