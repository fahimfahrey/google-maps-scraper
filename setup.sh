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

# Fetch standalone browser binary (Chromium preferred; Firefox fallback for
# distros not yet in Playwright's Chromium support matrix, e.g. Ubuntu 26.04)
BROWSER_ENGINE="chromium"
if ! .venv/bin/playwright install chromium 2>&1; then
    echo "WARNING: Chromium not supported on this platform. Trying Firefox..." >&2
    if ! .venv/bin/playwright install firefox 2>&1; then
        echo "WARNING: Firefox not supported on this platform. Trying system-installed browsers..." >&2

        # Fallback 3: use system-installed browser
        SYSTEM_CHROMIUM=""
        for candidate in google-chrome-stable google-chrome chromium-browser chromium; do
            if command -v "$candidate" &>/dev/null; then
                SYSTEM_CHROMIUM=$(command -v "$candidate")
                break
            fi
        done

        SYSTEM_FIREFOX=""
        if [[ -z "$SYSTEM_CHROMIUM" ]]; then
            if command -v firefox &>/dev/null; then
                SYSTEM_FIREFOX=$(command -v firefox)
            fi
        fi

        if [[ -n "$SYSTEM_CHROMIUM" ]]; then
            echo "Using system Chromium: $SYSTEM_CHROMIUM" >&2
            BROWSER_ENGINE="chromium"
            echo "$SYSTEM_CHROMIUM" > .playwright_browser_path
        elif [[ -n "$SYSTEM_FIREFOX" ]]; then
            echo "Using system Firefox: $SYSTEM_FIREFOX" >&2
            BROWSER_ENGINE="firefox"
            echo "$SYSTEM_FIREFOX" > .playwright_browser_path
        else
            echo "ERROR: Neither Chromium nor Firefox could be installed." >&2
            exit 1
        fi
    else
        BROWSER_ENGINE="firefox"
    fi
fi
echo "$BROWSER_ENGINE" > .playwright_browser
echo "Browser engine: $BROWSER_ENGINE (written to .playwright_browser)"

echo ""
echo "Setup complete. Activate with: source .venv/bin/activate"
echo "Run UI with:                   streamlit run app.py"
echo "Browser engine:                $(cat .playwright_browser 2>/dev/null || echo chromium)"
