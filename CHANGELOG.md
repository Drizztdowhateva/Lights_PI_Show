# Changelog 📝

All notable changes to this project are recorded here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added 🚀
- **GTK3 GUI** (`gui.py`) — full graphical interface with welcome screen, pattern
  toggle buttons, speed/brightness sliders, 256-color HSV wheel, live Cairo LED
  preview, and Start/Stop animation control
- **3 new patterns**: Fire Flame (10), Meteor Shower (11), Twinkle Stars (12)
- **5 new random palettes**: Pastel, Neon, Ocean, Fire, Forest (palettes 4–8)
- **Custom color system**: `--custom-color`, `--show-colors`, `NAMED_COLORS` dict
  with ~30 presets, `parse_custom_color()` accepting `name`/`#RRGGBB`/`r,g,b`
- **`n` runtime hotkey** — prints named color swatch table mid-run
- **Arrow key controls**: `←`/`→` cycle pattern, `↑`/`↓` adjust brightness ±16
- **`+`/`=`/`-` speed hotkeys** — replaces old `s` speed-cycle key
- **`PATTERN_CYCLE_ORDER`** constant for clean arrow-key pattern cycling
- **Distribution builder `--gui` flag** in `runtimes/runtime_package.py` — bundles
  `gui.py` with GTK3 typelib data files into AppImage / EXE / DMG
- **`if __name__ == "__main__"` guard** in `into.py` so it can be safely imported
  by `gui.py` and other tools
- `headless/` folder for storing JSON configs (easily loadable at runtime)
- `--export-headless` CLI to write current settings to `headless/` (optional name)
- `--SOS` / `--sos` CLI shortcut for immediate emergency SOS mode
- Consolidated packaging runtimes in `runtimes/` for AppImage, EXE, and DMG

### Changed ✨
- `runtime.sh` renamed to `Lights.sh` (primary CLI launcher)
- Removed redundant `runtime.py` Python launcher (shell script covers all cases)
- Removed thin wrapper scripts (`runtime_appimage.sh`, `runtime_dmg.sh`,
  `runtime_exe.ps1`) — call `runtimes/runtime_package.py` directly
- `AppState` dataclass extended: `custom_color`, `meteor_position`, `fire_heat`,
  `twinkle_pixels` fields added; `__post_init__` initializes mutable list fields
- `PATTERN_NAMES` extended from 9 to 13 entries
- `RANDOM_PALETTES` extended from 3 to 8 palettes
- `CHASE_COLORS` and `BOUNCE_COLORS` gained option `"5": Custom`
- `SPEED_MAP` extended with entries for patterns 10, 11, 12
- `maybe_read_key()` rewritten — removed all Ctrl+digit handling; detects
  `\x1b[A/B/C/D` escape sequences for arrow keys
- `handle_key()` rewritten — arrow keys, `+`/`=`/`-` speed, `n` colors, no `s`
- `print_status()` rewritten — ANSI color swatch, all 13 patterns handled
- `interactive_setup()` lists all 13 patterns, prompts for custom color
- `parse_args()` updated — new `--pattern` choices, `--custom-color`, `--show-colors`
- Default headless config path `headless/headless_settings.json`
- Pattern `4` maps to `Random` (SOS only via `--SOS` or `--pattern -1`)
- README fully rewritten for new GUI and CLI features
- `runtimes/README.md` updated to reflect simplified packaging structure

