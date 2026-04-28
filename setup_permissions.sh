#!/usr/bin/env bash
# Grant the venv Python binary the minimum Linux capabilities required to
# drive WS281x LEDs via DMA without running the entire process as root.
#
# Run this ONCE after setting up the virtual environment:
#
#   sudo bash setup_permissions.sh
#
# After this, any user can run:
#
#   .venv/bin/python3 into.py --pattern 1
#
# without prefixing the command with sudo.
#
# HOW IT WORKS
# ------------
# rpi_ws281x accesses /dev/mem to set up DMA for the LED data signal.
# Normally that requires root.  Linux "capabilities" let us grant just the
# specific permissions needed (cap_sys_rawio = raw I/O including /dev/mem)
# to the real Python binary rather than making the whole process root.
#
# NOTE: setcap must target a real file, not a symlink.  This script
# resolves the venv symlink automatically.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python3"

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: this script must be run with sudo." >&2
    echo "  sudo bash setup_permissions.sh" >&2
    exit 1
fi

if [ ! -f "$VENV_PYTHON" ]; then
    echo "Error: virtual environment not found at $SCRIPT_DIR/.venv" >&2
    echo "Create it first:" >&2
    echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
    echo "Or run: ./Lights.sh" >&2
    exit 1
fi

# Resolve the symlink so setcap targets the actual binary.
REAL_PYTHON="$(readlink -f "$VENV_PYTHON")"

echo "Setting capabilities on: $REAL_PYTHON"
setcap 'cap_sys_rawio+ep cap_dac_read_search+ep' "$REAL_PYTHON"
echo "Done. You can now run into.py without sudo:"
echo "  .venv/bin/python3 into.py --pattern 1"
echo ""
echo "Note: if Python is upgraded or the venv is recreated, run this script again."
