#!/usr/bin/env python3
"""Cross-platform packaging runtime for Lights PI Show.

Targets:
- appimage (Linux)
- exe      (Windows)
- dmg      (macOS)

Modes:
- CLI (default) — bundles into.py as a terminal application
- GUI  (--gui)  — bundles gui.py (GTK3) as a graphical application

Usage:
    # CLI builds
    python3 runtime_package.py appimage
    python3 runtime_package.py exe
    python3 runtime_package.py dmg

    # GUI builds
    python3 runtime_package.py appimage --gui
    python3 runtime_package.py exe      --gui
    python3 runtime_package.py dmg      --gui

Platform notes:
- AppImage: Linux only; appimagetool must be on PATH (see releases on GitHub).
- EXE:      Windows only; GTK3 GUI builds require MSYS2 + mingw-w64 GTK3 packages.
- DMG:      macOS only; GTK3 GUI builds require Homebrew GTK3 and pygobject3.

GUI GTK3 dependencies:
    sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0   # Debian/Ubuntu/Pi OS
    brew install gtk+3 pygobject3                                   # macOS
    pacman -S mingw-w64-x86_64-gtk3 mingw-w64-x86_64-python-gobject  # MSYS2 Windows
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


APP_NAME    = "LightsPIShow"
APP_NAME_GUI = "LightsPIShow-GUI"
ROOT        = Path(__file__).resolve().parent.parent
CLI_ENTRY   = ROOT / "into.py"
GUI_ENTRY   = ROOT / "gui.py"
DIST_DIR    = ROOT / "dist"

# GTK3 typelib modules needed for gi.repository to work inside the bundle.
TYPELIB_MODULES = [
    "Gtk-3.0", "Gdk-3.0", "GLib-2.0", "GObject-2.0", "Gio-2.0",
    "GdkPixbuf-2.0", "Pango-1.0", "PangoCairo-1.0", "cairo-1.0",
    "Atk-1.0", "HarfBuzz-0.0", "GModule-2.0", "GdkX11-3.0", "xlib-2.0",
]

# Linux search paths for typelib files.
_TYPELIB_SEARCH_DIRS = [
    "/usr/lib/girepository-1.0",
    "/usr/lib64/girepository-1.0",
    "/usr/lib/x86_64-linux-gnu/girepository-1.0",
    "/usr/lib/aarch64-linux-gnu/girepository-1.0",
]


def run(cmd: list[str]) -> None:
    print("+", " ".join(str(c) for c in cmd))
    subprocess.check_call(cmd)


def ensure_pyinstaller(skip_install: bool) -> None:
    if skip_install:
        return
    run([sys.executable, "-m", "pip", "install", "--upgrade", "pyinstaller"])


def _find_typelibs() -> list[tuple[str, str]]:
    """Return (src_path, dest_dir) tuples for GTK3 typelib files found on this system."""
    result: list[tuple[str, str]] = []
    for d in _TYPELIB_SEARCH_DIRS:
        if not os.path.isdir(d):
            continue
        for mod in TYPELIB_MODULES:
            path = os.path.join(d, f"{mod}.typelib")
            if os.path.exists(path):
                result.append((path, "gi_typelibs"))
    return result


def _gtk_hidden_imports() -> list[str]:
    return [
        "gi", "gi._gi", "gi._gi_cairo",
        "gi.repository.Gtk", "gi.repository.Gdk", "gi.repository.GLib",
        "gi.repository.GObject", "gi.repository.Gio", "gi.repository.GdkPixbuf",
        "gi.repository.Pango", "gi.repository.PangoCairo", "gi.repository.cairo",
        "cairo", "into",
    ]


def build_with_pyinstaller(extra_args: list[str], gui: bool) -> None:
    entrypoint = GUI_ENTRY if gui else CLI_ENTRY
    app_name   = APP_NAME_GUI if gui else APP_NAME

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--name", app_name,
    ]
    cmd.extend(extra_args)

    if gui:
        for imp in _gtk_hidden_imports():
            cmd += ["--hidden-import", imp]
        # Include source module so gui.py can `import into`
        cmd += ["--add-data", f"{CLI_ENTRY}{os.pathsep}."]

        if platform.system() == "Linux":
            for src, dest in _find_typelibs():
                cmd += ["--add-data", f"{src}{os.pathsep}{dest}"]

    cmd.append(str(entrypoint))
    run(cmd)


def package_appimage(gui: bool = False) -> None:
    if platform.system() != "Linux":
        raise SystemExit("AppImage packaging must be run on Linux.")

    build_with_pyinstaller(["--onefile"], gui=gui)

    app_name = APP_NAME_GUI if gui else APP_NAME
    binary   = DIST_DIR / app_name
    if not binary.exists():
        raise SystemExit(f"Missing expected binary: {binary}")

    appimagetool = shutil.which("appimagetool")
    if not appimagetool:
        print("appimagetool not found — built Linux binary only:")
        print(f"  {binary}")
        print()
        print("To finish the AppImage, install appimagetool:")
        print("  https://github.com/AppImage/AppImageKit/releases")
        print("Then re-run this script.")
        return

    appdir = ROOT / "build" / "AppDir"
    if appdir.exists():
        shutil.rmtree(appdir)

    (appdir / "usr" / "bin").mkdir(parents=True, exist_ok=True)
    shutil.copy2(binary, appdir / "usr" / "bin" / app_name)

    apprun = appdir / "AppRun"
    apprun.write_text(
        "#!/bin/sh\n"
        'HERE="$(dirname "$(readlink -f "$0")")"\n'
        f'exec "$HERE/usr/bin/{app_name}" "$@"\n',
        encoding="utf-8",
    )
    apprun.chmod(0o755)

    terminal_flag = "false" if gui else "true"
    desktop = appdir / f"{app_name}.desktop"
    display_name = "Lights PI Show" + (" GUI" if gui else "")
    desktop.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={display_name}\n"
        f"Exec={app_name}\n"
        f"Icon={app_name}\n"
        f"Terminal={terminal_flag}\n"
        "Categories=Utility;\n",
        encoding="utf-8",
    )
    # AppImageKit requires a .png icon — use a placeholder if none exists.
    icon_src = ROOT / "media" / "icon.png"
    icon_dst = appdir / f"{app_name}.png"
    if icon_src.exists():
        shutil.copy2(icon_src, icon_dst)
    else:
        # 1×1 transparent PNG so appimagetool doesn't abort
        icon_dst.write_bytes(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00"
            b"\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9c"
            b"b\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )

    arch = platform.machine() or "x86_64"
    suffix = "-gui" if gui else ""
    output = DIST_DIR / f"{app_name}-{arch}{suffix}.AppImage"
    run([appimagetool, str(appdir), str(output)])
    print(f"\nCreated: {output}")


def package_exe(gui: bool = False) -> None:
    if platform.system() != "Windows":
        raise SystemExit("EXE packaging must be run on Windows.")

    if gui:
        print(
            "NOTE: GUI EXE builds require MSYS2 with GTK3 and PyGObject installed.\n"
            "  pacman -S mingw-w64-x86_64-gtk3 mingw-w64-x86_64-python-gobject\n"
            "Run this script from the MSYS2 MinGW64 shell.\n"
        )

    # --windowed suppresses the console window for the GUI build
    extra = ["--onefile", "--windowed"] if gui else ["--onefile"]
    build_with_pyinstaller(extra, gui=gui)

    app_name = APP_NAME_GUI if gui else APP_NAME
    exe = DIST_DIR / f"{app_name}.exe"
    if not exe.exists():
        raise SystemExit(f"Missing expected EXE: {exe}")
    print(f"\nCreated: {exe}")


def package_dmg(gui: bool = False) -> None:
    if platform.system() != "Darwin":
        raise SystemExit("DMG packaging must be run on macOS.")

    if gui:
        print(
            "NOTE: GUI DMG builds require Homebrew GTK3 + pygobject3:\n"
            "  brew install gtk+3 pygobject3\n"
        )

    extra = ["--windowed"] if gui else ["--windowed"]
    build_with_pyinstaller(extra, gui=gui)

    app_name  = APP_NAME_GUI if gui else APP_NAME
    app_bundle = DIST_DIR / f"{app_name}.app"
    if not app_bundle.exists():
        raise SystemExit(f"Missing expected app bundle: {app_bundle}")

    hdiutil = shutil.which("hdiutil")
    if not hdiutil:
        raise SystemExit("hdiutil is required to create DMG on macOS.")

    dmg = DIST_DIR / f"{app_name}.dmg"
    if dmg.exists():
        dmg.unlink()

    run([
        hdiutil, "create",
        "-volname", app_name,
        "-srcfolder", str(app_bundle),
        "-ov", "-format", "UDZO",
        str(dmg),
    ])
    print(f"\nCreated: {dmg}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build runtime packages for AppImage, EXE, or DMG.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 runtime_package.py appimage          # CLI AppImage\n"
            "  python3 runtime_package.py appimage --gui    # GTK3 GUI AppImage\n"
            "  python3 runtime_package.py exe      --gui    # GTK3 GUI .exe (Windows)\n"
            "  python3 runtime_package.py dmg      --gui    # GTK3 GUI .dmg (macOS)\n"
        ),
    )
    parser.add_argument("target", choices=["appimage", "exe", "dmg"])
    parser.add_argument(
        "--gui",
        action="store_true",
        help=(
            "Package the GTK3 GUI application (gui.py) instead of the CLI (into.py). "
            "Requires PyGObject / GTK3 libraries on the build machine."
        ),
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip installing/updating PyInstaller before packaging.",
    )
    args = parser.parse_args()

    entry = GUI_ENTRY if args.gui else CLI_ENTRY
    if not entry.exists():
        raise SystemExit(f"Missing entrypoint: {entry}")

    ensure_pyinstaller(skip_install=args.skip_install)

    if args.target == "appimage":
        package_appimage(gui=args.gui)
    elif args.target == "exe":
        package_exe(gui=args.gui)
    elif args.target == "dmg":
        package_dmg(gui=args.gui)


if __name__ == "__main__":
    main()
