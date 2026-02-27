# WS281X Pattern Runner 🚀

![CI](https://github.com/Drizztdowhateva/Lights_PI_Show/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)

Beautiful, keyboard-driven LED patterns for WS281X strips — with safe ASCII simulation, headless JSON configs, and easy detached runtime options.

## Quick Start ✨

Run a quick ASCII test (no hardware):

```bash
cd /home/blackmox/code/ws281x
python3 into.py --test --pattern 1 --chase-color 4 --speed 3 --frames 20
```

## Donate & GitHub ❤️

- Donation (Cash App): https://cash.app/$teerRight
- GitHub Profile: https://github.com/Drizztdowhateva
- Full page with QR codes: [DONATION_AND_GITHUB_QR.md](DONATION_AND_GITHUB_QR.md)

## Run (hardware) — Easy mode 🔧

```bash
cd /home/blackmox/code/ws281x
sudo -n python3 into.py --pattern 1 --chase-color 4 --speed 3 --frames 0
```

## One-file runtime (install + save + run) 🧰

Installs required runtime package(s) and optionally pins them to `requirements.txt`:

```bash
python3 runtime.py -- --pattern 1 --chase-color 4 --speed 3 --frames 0
# or run detached with nohup:
sudo python3 runtime.py --skip-install --no-save --nohup -- --pattern 1 --chase-color 4 --speed 3 --frames 0
```

When using `--nohup` the runtime prints a cancel command and writes a PID file (`runtime_live.pid`):

Preferred cancel command:

```bash
kill $(cat runtime_live.pid)
```

Fallback:

```bash
pkill -f 'into.py'
```

## Headless mode & configs 📁

Store and load JSON configs from the `headless/` folder. The interactive prompt now presents a short a/b/c/d menu for available `headless/*.json` files and an `e` option to enter a custom path.

Load headless config and run:

```bash
python3 into.py --headless --headless-config headless/headless_settings.json
```

Export current settings into a headless JSON file (new):

```bash
python3 into.py --export-headless          # writes headless/<pattern>_<name>.json
python3 into.py --export-headless my_sos   # writes headless/my_sos.json
```

## Features & handy commands 💡

- Pi input support: digital or analog

```bash
python3 into.py --pi-input-mode digital --pi-input-pin 23
python3 into.py --pi-input-mode analog --analog-path /sys/bus/iio/devices/iio:device0/in_voltage0_raw --analog-max 4095
```

- Brightness control

```bash
python3 into.py --brightness 128 --max-brightness 200
# Runtime keys: + / - to adjust brightness
```

- Timer options

```bash
python3 into.py --frames 600 --duration-seconds 30 --start-delay-seconds 2
```

- Emergency-only panic mode (SOS in 3 repeating colors):

```bash
python3 into.py --emergency-only
```

## Interactive Controls (while running) ⌨️

- `1`/`2`/`3`/`4` — Switch pattern
- `p` — Cycle pattern
- `s` — Cycle speed
- `c` — Cycle color option for current pattern
- `+` / `-` — Adjust brightness
- `h` — Show help
- `q` or `Ctrl+C` — Quit

## Example Output (ASCII)

Pattern: Chase | Speed: Fast | Color: Rainbow
Pattern: Random | Speed: Fast | Palette: Any RGB
Pattern: Bounce | Speed: Fast | Color: Blue

---

If you'd like, I can also update the README examples to use `headless/` everywhere and add screenshots or animated GIFs for the ASCII output.
