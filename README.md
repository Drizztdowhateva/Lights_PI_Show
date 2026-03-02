# Lights PI Show

## Clone Instructions

To clone the repository, use the following command:

```bash
git clone https://github.com/Drizztdowhateva/Lights_PI_Show.git
```

## Installation Instructions

The `rpi-ws281x` library is only needed on Raspberry Pi hardware (ARM). It is
not available as an apt package; install it via pip inside a virtual
environment.

### Install via pip (recommended — works on all systems)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running on Raspberry Pi (hardware LEDs)

```bash
source .venv/bin/activate
sudo .venv/bin/python3 into.py
```

Or use the provided launcher which sets up the virtual environment automatically:

```bash
./runtime.sh
```

## Note

Ensure that you do not use hard-coded absolute home-directory paths in your configurations. The paths should be relative or set up as environmental variables.
