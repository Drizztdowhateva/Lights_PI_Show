# Lights PI Show

Keyboard-driven WS281X LED pattern runner with safe local testing, headless config workflows, and runtime helper tooling.

[![CI](https://github.com/Drizztdowhateva/Lights_PI_Show/actions/workflows/ci.yml/badge.svg)](https://github.com/Drizztdowhateva/Lights_PI_Show/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

![Lights PI Show Banner](media/lights-pi-show-banner.svg)

## Support and Donations

If this project helps your workflow, support is appreciated:

- GitHub Sponsors: `https://github.com/sponsors/Drizztdowhateva`
- Cash App: `https://cash.app/$teerRight`
- GitHub Profile: `https://github.com/Drizztdowhateva`

## Table of Contents

- [SOS / Emergency Quick Start](#sos--emergency-quick-start)
- [Technical Profile](#technical-profile)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Support Task Manager](#support-task-manager)
- [Project Structure](#project-structure)
- [Quality and Standards](#quality-and-standards)
- [Governance](#governance)

## SOS / Emergency Quick Start

Launch the emergency SOS pattern immediately in the background using the dedicated headless config:

```bash
sudo python3 runtime.py --nohup -- --headless --headless-config headless/headless_emergency_sos_red.json
```

To stop it at any time:

```bash
kill $(cat runtime_live.pid) 2>/dev/null || echo "No running process found"
```

## Technical Profile

Lights PI Show is built as a practical operations tool for LED demonstrations and scripted light-control routines on Raspberry Pi hardware.

- Local-first execution for hardware control and quick test loops
- Headless JSON config support for repeatable runs
- Runtime wrapper scripts for easier background execution
- Simple project layout that is easy to fork and customize

## Clone

```bash
git clone https://github.com/Drizztdowhateva/Lights_PI_Show.git
cd Lights_PI_Show
```

## Installation

The `rpi-ws281x` package is only required for real Raspberry Pi LED output.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run with hardware LEDs:

```bash
source .venv/bin/activate
sudo .venv/bin/python3 into.py
```

Or use the runtime launcher:

```bash
sudo ./runtime.sh
```

## Quick Start

Safe test mode (no hardware required):

```bash
python3 into.py --test --pattern 1 --speed 3 --frames 30
```

Hardware run:

```bash
sudo -n python3 into.py --pattern 1 --speed 3 --frames 0
```

Headless config run:

```bash
python3 into.py --headless --headless-config headless/headless_settings.json
```

## Support Task Manager

Use the runtime support manager to track ideas/features as todo tasks and hand them off to Copilot.

- Open manager while runtime is active: `Alt+M`
- Actions: `a` add, `l` list, `e` edit, `d` done, `r` reopen, `x` delete, `s` send, `u` unsend
- Priority support: `high`, `med`, `low` (open tasks are sorted by priority first)

Files created under `LessonProg/`:

- `support_tickets.json`: primary task store (read/modify/check-off)
- `copilot_queue.md`: Copilot-ready handoff queue (append-only markdown)

Non-interactive export to Copilot queue:

```bash
# Send all open tasks
python3 into.py --support-export

# Send only specific IDs
python3 into.py --support-export 1,2,5
```

## Project Structure

```text
Lights_PI_Show/
|- into.py                    # Main pattern runner
|- runtime.py                 # Runtime helper wrapper
|- runtime.sh                 # Shell launcher
|- setup_permissions.sh       # Linux capability setup helper
|- headless/                  # JSON headless configs
|- media/                     # README assets and screenshots
|- runtimes/                  # Runtime artifacts/log helpers
|- .github/workflows/ci.yml   # CI validation workflow
```

## Quality and Standards

- CI checks are defined in `.github/workflows/ci.yml`.
- Keep paths relative and avoid hard-coded home-directory locations.
- Keep API keys and secrets out of version control.
- Prefer test mode (`--test`) during development when hardware is unavailable.

## Media

- Project banner: `media/lights-pi-show-banner.svg`
- Add screenshots and GIFs to `media/` and reference them here for release posts

## Governance

- Code of Conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- License: [LICENSE](LICENSE)
- Changelog: [CHANGELOG.md](CHANGELOG.md)

## Chat

- WhatsApp: https://wa.me/13127235816
