# Local PBJ server: kill stale listeners on PORT, then start with reload.
# Usage (note semicolons — required between separate commands on one line):
#   .\scripts\start_local.ps1
#   .\scripts\start_local.ps1 -AiSupport all
#   $env:PBJ_AI_SUPPORT = "all"; .\scripts\start_local.ps1
# Wrong (causes "Unexpected token ... CACHE"):
#   $env:PBJ_AI_SUPPORT = "all" $env:PBJ_SKIP_PROVIDER_PAGE_CACHE = "1" .\scripts\start_local.ps1
param(
    [ValidateSet('off', 'dashboards', 'page', 'all', '')]
    [string]$AiSupport = '',
    [switch]$SkipProviderCache
)

Set-Location $PSScriptRoot\..

$port = if ($env:PORT) { [int]$env:PORT } else { 10000 }
Write-Host "Stopping any process listening on port $port..."
Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { $_.OwningProcess } |
    Sort-Object -Unique |
    ForEach-Object {
        Write-Host "  Stopping PID $_"
        Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
    }
Start-Sleep -Seconds 1

$env:FLASK_DEBUG = "1"
if ($SkipProviderCache -or -not $env:PBJ_SKIP_PROVIDER_PAGE_CACHE) {
    $env:PBJ_SKIP_PROVIDER_PAGE_CACHE = "1"
}
if ($AiSupport) {
    $env:PBJ_AI_SUPPORT = $AiSupport
} elseif (-not $env:PBJ_AI_SUPPORT) {
    # Local preview: AI page + dashboard helpers on localhost.
    $env:PBJ_AI_SUPPORT = "all"
}
$aiMode = $env:PBJ_AI_SUPPORT
Write-Host "Starting app.py (auto-reload, PBJ_AI_SUPPORT=$aiMode, PBJ_SKIP_PROVIDER_PAGE_CACHE=$env:PBJ_SKIP_PROVIDER_PAGE_CACHE)..."

$python = if ($env:PBJ_PYTHON) { $env:PBJ_PYTHON } else { "python" }
& $python "$PSScriptRoot\..\app.py"
