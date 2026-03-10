# Changelog 📝

All notable changes to this project are recorded here. This file follows a simple "Unreleased → Release" flow.

## [Unreleased]

### Added 🚀
- `headless/` folder for storing JSON configs (easily loadable at runtime)
- `--export-headless` CLI to write current settings to `headless/` (optional name)
- Interactive headless selection menu (a/b/c/d choices + e for custom path)
- `--nohup` detached runtime prints cancel commands and writes `runtime_live.pid`
- Documentation updates: README refreshed with examples and usage notes
- Consolidated packaging runtimes in `runtimes/` for `AppImage`, `EXE`, and `DMG`
- Shared packaging engine: `runtimes/runtime_package.py`
- `--SOS` / `--sos` CLI shortcut for immediate emergency SOS mode
- Runtime heads-up output now includes `sudo ./runtime.sh --SOS`

### Changed ✨
- Default headless config path moved to `headless/headless_settings.json`
- Pattern `4` now maps to `Random` (SOS removed from regular numeric pattern slots)
- Runtime shortcut/help text now documents SOS via `--SOS` or `--pattern -1`

