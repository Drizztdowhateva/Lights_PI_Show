# Packaging Runtimes

`runtime_package.py` is a single cross-platform packaging engine for all three
distribution formats. It uses [PyInstaller](https://pyinstaller.org/) to produce
self-contained bundles — no Python installation required on the target machine.

## Modes

| Flag | Entrypoint | Description |
|------|-----------|-------------|
| *(default)* | `into.py` | CLI terminal application |
| `--gui` | `gui.py` | GTK3 graphical application |

## Usage

Run from the repo root:

```bash
# CLI builds
python3 runtimes/runtime_package.py appimage
python3 runtimes/runtime_package.py exe
python3 runtimes/runtime_package.py dmg

# GUI builds
python3 runtimes/runtime_package.py appimage --gui
python3 runtimes/runtime_package.py exe      --gui
python3 runtimes/runtime_package.py dmg      --gui

# Skip reinstalling PyInstaller
python3 runtimes/runtime_package.py appimage --gui --skip-install
```

Output is placed in `dist/`.

## Platform Requirements

| Target | Must run on | Extra dependency |
|--------|-------------|------------------|
| `appimage` | Linux | `appimagetool` on PATH — [AppImageKit releases](https://github.com/AppImage/AppImageKit/releases) |
| `exe` | Windows | For GUI: MSYS2 MinGW64 + `pacman -S mingw-w64-x86_64-gtk3 mingw-w64-x86_64-python-gobject` |
| `dmg` | macOS | For GUI: `brew install gtk+3 pygobject3` |

Linux GUI build also requires GTK3 typelibs on the build machine:

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0
```

## Notes

- PyInstaller is installed/upgraded automatically unless `--skip-install` is passed.
- If `appimagetool` is missing, the Linux binary is still built; run again after installing the tool.
- A placeholder icon is embedded automatically if `media/icon.png` does not exist.
