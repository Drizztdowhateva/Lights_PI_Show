# Lights PI Show

Keyboard-driven WS281X LED pattern runner with safe local testing, headless config workflows, and runtime helper tooling.

![Lights PI Show Banner](media/lights-pi-show-banner.svg)

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

## Media

- Project banner: `media/lights-pi-show-banner.svg`
- Add screenshots and GIFs to `media/` and reference them here for release posts

## Support and Donations

If this project helps your workflow, support is appreciated:

- GitHub Sponsors: `https://github.com/sponsors/Drizztdowhateva`
- Cash App: `https://cash.app/$teerRight`
- GitHub Profile: `https://github.com/Drizztdowhateva`

## Notes

- Keep paths relative and avoid hard-coded home-directory locations.
- Keep API keys and secrets out of version control.
