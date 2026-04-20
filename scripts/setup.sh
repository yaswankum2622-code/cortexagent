#!/usr/bin/env bash
set -euo pipefail

echo "============================================================"
echo "CortexAgent - Local Development Setup"
echo "============================================================"

PYTHON_BIN=""
if command -v python3.11 >/dev/null 2>&1; then
    PYTHON_BIN="python3.11"
elif command -v python3 >/dev/null 2>&1 && python3 --version 2>&1 | grep -q "3.11"; then
    PYTHON_BIN="python3"
fi

if [ -z "$PYTHON_BIN" ]; then
    echo "ERROR: Python 3.11 not found. Install it first."
    echo "  macOS: brew install python@3.11"
    echo "  Linux: check your distro package manager"
    exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    uv venv --python "$PYTHON_BIN"
fi

echo "Installing dependencies (this may take 2-3 minutes)..."
. .venv/bin/activate
uv pip install -e ".[dev]"

if [ ! -f ".env" ]; then
    echo ""
    echo "WARNING: .env file not found!"
    echo "  Run: cp .env.example .env"
    echo "  Then edit .env and add your API keys."
fi

echo ""
echo "Validating configuration..."
python config/settings.py

echo ""
echo "============================================================"
echo "Setup complete!"
echo "============================================================"
echo ""
echo "Next steps:"
echo "  1. Ingest the SEC corpus (one-time, ~5 minutes):"
echo "     python -m rag.ingestion"
echo ""
echo "  2. Start the API server (keep this terminal open):"
echo "     python -m api.main"
echo ""
echo "  3. In a new terminal, start the dashboard:"
echo "     streamlit run dashboard/app.py --server.address 0.0.0.0"
echo ""
echo "  4. Open http://localhost:8501"
echo ""
echo "Or use Docker:"
echo "  docker-compose up"
