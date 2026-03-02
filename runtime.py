#!/usr/bin/env python3
"""WS281X runtime launcher.

Optionally installs required packages into a virtual environment then launches
into.py.  A venv is created at .venv/ next to this script when needed so that
the install never conflicts with an externally-managed system Python
(PEP 668 / Debian Bookworm and later).

Usage:
    python3 runtime.py -- --pattern 1 --chase-color 4 --speed 3 --frames 0
    sudo python3 runtime.py --skip-install --no-save --nohup -- --pattern 1 --speed 3
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

REQUIREMENTS_FILE = "requirements.txt"
VENV_DIR = ".venv"
PID_FILE = "runtime_live.pid"
LOG_FILE = "runtime_live.log"


def _ensure_venv(script_dir: Path) -> Path:
    """Create a venv at <script_dir>/.venv if it does not already exist.

    Returns the path to the venv's Python interpreter.
    """
    venv_path = script_dir / VENV_DIR
    python_bin = venv_path / "bin" / "python3"
    if not python_bin.exists():
        print(f"Creating virtual environment at {venv_path} ...")
        subprocess.check_call([sys.executable, "-m", "venv", str(venv_path)])
    return python_bin


def main() -> None:
    # Split argv at the "--" separator; everything after it is forwarded to into.py.
    argv = sys.argv[1:]
    if "--" in argv:
        sep = argv.index("--")
        own_args = argv[:sep]
        forward_args = argv[sep + 1:]
    else:
        own_args = argv
        forward_args = []

    parser = argparse.ArgumentParser(
        description="WS281X runtime launcher — installs deps and runs into.py."
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip pip install of requirements.txt",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not write/pin requirements.txt",
    )
    parser.add_argument(
        "--nohup",
        action="store_true",
        help="Launch into.py detached in the background via nohup",
    )
    args = parser.parse_args(own_args)

    script_dir = Path(__file__).parent
    req_path = script_dir / REQUIREMENTS_FILE
    into_path = script_dir / "into.py"

    venv_python = _ensure_venv(script_dir)

    if not args.skip_install and req_path.exists():
        subprocess.check_call(
            [str(venv_python), "-m", "pip", "install", "-r", str(req_path)],
        )

    cmd = [str(venv_python), str(into_path)] + forward_args

    if args.nohup:
        os.chdir(script_dir)
        log_file = open(LOG_FILE, "w")
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        pid = proc.pid
        Path(PID_FILE).write_text(str(pid) + "\n", encoding="utf-8")
        print("=== Heads Up: Starting in background (nohup) mode ===")
        print(f"PID:     {pid}")
        print(f"Logs:    {LOG_FILE}")
        print(f"Stop:    kill $(cat {PID_FILE})")
        print("=====================================================")
    else:
        result = subprocess.run(cmd)
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
