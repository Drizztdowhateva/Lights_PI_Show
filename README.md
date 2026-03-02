# Lights PI Show

## SOS / Emergency Quick Start

Launch the **Emergency SOS** pattern immediately in the background
(the `--` separates launcher flags from the pattern arguments passed to `into.py`):

```bash
sudo python3 runtime.py --nohup -- --pattern 4
```

To stop it at any time:

```bash
kill $(cat runtime_live.pid) 2>/dev/null || echo "No running process found"
```

---

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
sudo ./runtime.sh
```

### Running without sudo (recommended for daily use)

The `rpi_ws281x` library uses DMA to drive the LED data signal and needs
access to `/dev/mem`.  Running the whole process as root is one way to
satisfy that requirement, but it is not the only way.

**Option A — grant Linux capabilities (recommended)**

Run the setup script once after creating the virtual environment:

```bash
sudo bash setup_permissions.sh
```

This grants only the minimum capabilities needed (`cap_sys_rawio` and
`cap_dac_read_search`) to the Python binary inside the venv.  After that,
any user can drive the LEDs without `sudo`:

```bash
.venv/bin/python3 into.py --pattern 1
# or
./runtime.sh --pattern 1
```

> **Note:** if you upgrade Python or recreate the virtual environment, run
> `sudo bash setup_permissions.sh` once more.

**Option B — ASCII simulation (no hardware required)**

Add `--test` to any command to run in safe ASCII simulation mode without
touching the hardware at all — no `sudo` needed:

```bash
.venv/bin/python3 into.py --test
./runtime.sh --test
```

## Note

Ensure that you do not use hard-coded absolute home-directory paths in your configurations. The paths should be relative or set up as environmental variables.
