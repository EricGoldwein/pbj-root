# Local memory profile (app must run with PBJ_MEM_DEBUG=1 on port 10000).
# Terminal 1:  $env:PBJ_MEM_DEBUG='1'; python app.py
# Terminal 2:  .\scripts\profile_mem_local.ps1

$base = if ($env:PBJ_BASE_URL) { $env:PBJ_BASE_URL } else { 'http://127.0.0.1:10000' }

function Get-MemJson {
    (Invoke-WebRequest "$base/debug/mem" -UseBasicParsing).Content | ConvertFrom-Json
}

function Show-Mem($label) {
    $m = Get-MemJson
    Write-Host "[$label] RSS=$($m.rss_mb) MB | provider_ccns=$($m.caches.provider_info_ccns) | full_cache=$($m.caches.provider_info_full_cache) | csv_caches=$($m.caches.load_csv)"
}

Write-Host "PBJ memory profile -> $base"
Write-Host ""

Write-Host '=== Health ==='
(Invoke-WebRequest "$base/health" -UseBasicParsing).Content | Out-Host
Show-Mem 'after health'

Write-Host ''
Write-Host '=== Provider 075325 ==='
$r = Invoke-WebRequest "$base/provider/075325" -UseBasicParsing
Write-Host "status=$($r.StatusCode) cache=$($r.Headers['X-PBJ-Provider-Cache'])"
Show-Mem 'after provider'

Write-Host ''
$si = Get-Content (Join-Path $PSScriptRoot '..\search_index.json') -Raw | ConvertFrom-Json
$eid = ($si.e | Select-Object -First 1).i
if (-not $eid) { $eid = 1 }
Write-Host "=== Entity $eid ==="
Invoke-WebRequest "$base/entity/$eid" -UseBasicParsing -TimeoutSec 120 | Out-Null
Show-Mem 'after entity'

Write-Host ''
Write-Host '=== Owner 8820069735 ==='
try {
    Invoke-WebRequest "$base/owners/8820069735" -UseBasicParsing -TimeoutSec 120 | Out-Null
    Show-Mem 'after owner'
} catch {
    Write-Host "owner skipped: $($_.Exception.Message)"
}

Write-Host ''
Write-Host '=== Full /debug/mem ==='
(Get-MemJson | ConvertTo-Json -Compress) | Out-Host
