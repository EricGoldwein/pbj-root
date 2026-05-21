# Kill stale Flask on 10000, start app.py, verify FEC contributions UI (not legacy stub).
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$onPort = Get-NetTCPConnection -LocalPort 10000 -ErrorAction SilentlyContinue
foreach ($procId in ($onPort.OwningProcess | Select-Object -Unique)) {
    if ($procId) { Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue }
}
Start-Sleep -Seconds 2

$env:PYTHONIOENCODING = 'utf-8'
$job = Start-Job -ScriptBlock {
    Set-Location $using:root
    $env:PYTHONIOENCODING = 'utf-8'
    python app.py 2>&1
}

$ready = $false
for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Seconds 1
    try {
        $ping = Invoke-RestMethod -Uri 'http://127.0.0.1:10000/owner/_dev/ping' -TimeoutSec 3
        if ($ping.fec_ui -eq 'may17_restored') { $ready = $true; break }
    } catch { }
}
if (-not $ready) {
    Stop-Job $job -ErrorAction SilentlyContinue
    Remove-Job $job -Force -ErrorAction SilentlyContinue
    Write-Host 'FAIL: Server did not report may17_restored UI on disk.'
    Receive-Job $job -ErrorAction SilentlyContinue | Select-Object -Last 30
    exit 1
}

Write-Host "Disk check: $($ping.fec_ui) (py lines $($ping.owner_donor_dashboard_py_lines))"

$html = curl.exe -s -m 120 'http://127.0.0.1:10000/owner/'
$stats = Invoke-RestMethod -Uri 'http://127.0.0.1:10000/owner/api/stats' -TimeoutSec 120

$ok = $true
if ($html -notmatch 'class="navbar"') { Write-Host 'FAIL: missing navbar'; $ok = $false }
if ($html -notmatch 'page-title">Nursing Home Owner Political Contributions') { Write-Host 'FAIL: wrong title'; $ok = $false }
if ($html -match 'Nursing Home Owner Political Donations</h1>') { Write-Host 'FAIL: legacy Donations title'; $ok = $false }
if ($html -notmatch 'Search by Owner') { Write-Host 'FAIL: missing Search by Owner'; $ok = $false }
if ($stats.total_owners -lt 1000) { Write-Host "FAIL: stats total_owners=$($stats.total_owners)"; $ok = $false }

Stop-Job $job -ErrorAction SilentlyContinue
Remove-Job $job -Force -ErrorAction SilentlyContinue
foreach ($procId in (Get-NetTCPConnection -LocalPort 10000 -ErrorAction SilentlyContinue).OwningProcess | Select-Object -Unique) {
    if ($procId) { Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue }
}

if ($ok) {
    Write-Host "PASS: FEC contributions UI OK (owners=$($stats.total_owners))"
    exit 0
}
Write-Host 'FAIL: HTTP response does not match restored UI'
exit 1
