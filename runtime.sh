#!/usr/bin/env sh
# WS281X Pattern Runner — simple launcher
# Usage:
#   sudo ./runtime.sh                    # prompt for headless option, then start
#   sudo ./runtime.sh --pattern 1 ...   # pass args directly to into.py
#   sudo ./runtime.sh --headless        # skip prompt, use default headless config
#   sudo ./runtime.sh --test            # ASCII simulation (no hardware needed)

set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/.venv"

echo "=== WS281X Pattern Runner ==="
echo "Tip: Press O while running to print the background (nohup) launch command."
echo "     Press q or Ctrl+C to quit."
echo ""

if [ "$(id -u)" -ne 0 ]; then
    echo "Note: hardware LED access requires elevated privileges." >&2
    echo "  • Run with sudo:                sudo ./runtime.sh" >&2
    echo "  • Or grant capabilities once:   sudo bash setup_permissions.sh" >&2
    echo ""
fi

# Create virtual environment if it doesn't exist
if [ ! -f "$VENV_DIR/bin/python3" ]; then
    echo "Creating virtual environment at $VENV_DIR ..."
    python3 -m venv "$VENV_DIR"
fi

PYTHON="$VENV_DIR/bin/python3"

# Some distros create venvs without a pip shim in bin/. Use python -m pip
# and bootstrap ensurepip when needed.
if ! "$PYTHON" -m pip --version >/dev/null 2>&1; then
    echo "pip is missing in $VENV_DIR, bootstrapping with ensurepip ..."
    "$PYTHON" -m ensurepip --upgrade
fi

# Install / sync dependencies
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    "$PYTHON" -m pip install -r "$SCRIPT_DIR/requirements.txt"
fi

# If arguments are provided, pass them directly to into.py.
# Otherwise, run interactively so the user is prompted for the headless option
# before the runtime shortcuts are displayed.
if [ "$#" -gt 0 ]; then
    exec "$PYTHON" into.py "$@"
else
    exec "$PYTHON" into.py
fi
