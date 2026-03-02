#!/usr/bin/env bash
# WS281X Pattern Runner — simple launcher
# Usage:
#   sudo ./runtime.sh                    # run with default headless config
#   sudo ./runtime.sh --pattern 1 ...   # pass args directly to into.py
#   sudo ./runtime.sh --test            # ASCII simulation (no hardware needed)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== WS281X Pattern Runner ==="
echo "Tip: Press Ctrl+O while running to print the background (nohup) launch command."
echo "     Press q or Ctrl+C to quit."
echo ""

if [ "$(id -u)" -ne 0 ]; then
    echo "Note: Hardware LED access typically requires root. Re-run with: sudo ./runtime.sh" >&2
    echo ""
fi

# If arguments are provided, pass them directly to into.py.
# Otherwise, use the default headless config for a prompt-free startup.
if [ "$#" -gt 0 ]; then
    exec python3 into.py "$@"
else
    exec python3 into.py --headless --headless-config headless/headless_settings.json
fi
