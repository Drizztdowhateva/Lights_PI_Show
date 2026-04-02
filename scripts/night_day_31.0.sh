#!/usr/bin/env sh
set -euo pipefail

sudo sh -c 'nohup /home/blackmox/code/Lights_Pi_Show/.venv/bin/python3 /home/blackmox/code/Lights_Pi_Show/into.py --speed 0 --chase-color 1 --random-palette 1 --bounce-color 1 --brightness 31 --max-brightness 255 --pi-input-mode off --pi-input-pin 23 --analog-path /sys/bus/iio/devices/iio:device0/in_voltage0_raw --analog-max 4095 --effect-color 3 --pattern 12 --schedule-enable --schedule-on 1800 --schedule-off 0600 --force > runtime_live.log 2>&1 & echo $! > runtime_live.pid'
