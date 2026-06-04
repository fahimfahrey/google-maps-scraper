#!/usr/bin/env bash
set -euo pipefail

# Require Python 3.11+
PYTHON=$(command -v python3 || true)
if [[ -z "$PYTHON" ]]; then
    echo "ERROR: python3 not found" >&2
    exit 1
fi

PY_VERSION=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
REQUIRED="3.11"
if [[ "$(printf '%s\n' "$REQUIRED" "$PY_VERSION" | sort -V | head -1)" != "$REQUIRED" ]]; then
    echo "ERROR: Python $PY_VERSION < $REQUIRED required" >&2
    exit 1
fi

# Create venv
"$PYTHON" -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Fetch standalone Chromium binary
playwright install chromium

echo ""
echo "Setup complete. Activate with: source .venv/bin/activate"
echo "Run UI with:                   streamlit run app.py"
