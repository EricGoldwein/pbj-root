# Point this repo at versioned hooks under .githooks/
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
git config core.hooksPath .githooks
Write-Host "Installed git hooks from .githooks (pre-push runs deploy + release guards)."
