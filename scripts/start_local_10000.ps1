$ErrorActionPreference = "Stop"

Write-Host "Stopping any existing listeners on port 10000..."
$listenerPids = @()
try {
    $lines = netstat -ano | Select-String "LISTENING" | Select-String ":10000"
    foreach ($line in $lines) {
        $parts = ($line -replace "\s+", " ").Trim().Split(" ")
        if ($parts.Length -ge 5) {
            $procId = $parts[-1]
            if ($procId -match "^\d+$") {
                $listenerPids += [int]$procId
            }
        }
    }
} catch {
    Write-Host "Could not inspect existing listeners: $($_.Exception.Message)"
}

$listenerPids = $listenerPids | Select-Object -Unique
foreach ($procId in $listenerPids) {
    if ($procId -ne 0) {
        try {
            Stop-Process -Id $procId -Force -ErrorAction Stop
            Write-Host "Stopped PID $procId"
        } catch {
            Write-Host "Failed to stop PID ${procId}: $($_.Exception.Message)"
        }
    }
}

Set-Location (Resolve-Path "$PSScriptRoot\..")
$env:PORT = "10000"
Write-Host "Starting Flask app on http://127.0.0.1:10000 ..."
python app.py
