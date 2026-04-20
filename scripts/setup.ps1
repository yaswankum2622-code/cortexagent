$ErrorActionPreference = "Stop"

Write-Host "============================================================"
Write-Host "CortexAgent - Local Development Setup"
Write-Host "============================================================"

$pythonVersion = python --version 2>&1
if (-not ($pythonVersion -match "3\.11")) {
    Write-Host "ERROR: Python 3.11 required. Found: $pythonVersion"
    Write-Host "Download: https://www.python.org/downloads/release/python-3110/"
    exit 1
}

$uvCheck = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvCheck) {
    Write-Host "Installing uv..."
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
}

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    uv venv --python 3.11
}

Write-Host "Installing dependencies (this may take 2-3 minutes)..."
.\.venv\Scripts\Activate.ps1
uv pip install -e ".[dev]"

if (-not (Test-Path ".env")) {
    Write-Host ""
    Write-Host "WARNING: .env file not found!" -ForegroundColor Yellow
    Write-Host "  Run: Copy-Item .env.example .env"
    Write-Host "  Then edit .env and add your API keys."
}

Write-Host ""
Write-Host "Validating configuration..."
python config\settings.py

Write-Host ""
Write-Host "============================================================"
Write-Host "Setup complete!"
Write-Host "============================================================"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Ingest the SEC corpus (one-time, ~5 minutes):"
Write-Host "     python -m rag.ingestion"
Write-Host ""
Write-Host "  2. Start the API server (keep this terminal open):"
Write-Host "     python -m api.main"
Write-Host ""
Write-Host "  3. In a new terminal, start the dashboard:"
Write-Host "     streamlit run dashboard\app.py --server.address 0.0.0.0"
Write-Host ""
Write-Host "  4. Open http://localhost:8501"
Write-Host ""
Write-Host "Or use Docker:"
Write-Host "  docker-compose up"
