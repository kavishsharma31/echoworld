$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

python scripts/build_web.py --prepare-only
$Backend = Start-Process python `
    -ArgumentList "-m", "uvicorn", "backend_api:app", "--host", "127.0.0.1", "--port", "8787" `
    -PassThru -WindowStyle Hidden

try {
    Write-Host "Backend: http://127.0.0.1:8787/api/health"
    Write-Host "Pygbag will open its browser frontend; Ctrl+C stops development."
    python -m pygbag web_build
}
finally {
    if (-not $Backend.HasExited) {
        Stop-Process -Id $Backend.Id
    }
}
