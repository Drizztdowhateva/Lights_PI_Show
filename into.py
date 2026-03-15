import argparse
from datetime import datetime, timezone
import json
import math
import os
import random
import re
import select
import shutil
import signal
import sys
import termios
import time
import tty
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

try:
    from rpi_ws281x import Adafruit_NeoPixel, Color  # type: ignore[import-not-found]
    _HAVE_RPI_WS281X = True
except Exception:
    Adafruit_NeoPixel = None  # type: ignore[assignment]
    def Color(r: int, g: int, b: int) -> int:  # minimal fallback for ASCII mode
        return ((r & 0xFF) << 16) | ((g & 0xFF) << 8) | (b & 0xFF)
    _HAVE_RPI_WS281X = False

# LED configuration
LED_COUNT = 120
LED_PIN = 18
LED_BRIGHTNESS = 255
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_INVERT = False
LED_CHANNEL = 0
HEADLESS_DEFAULT_CONFIG = "headless/headless_settings.json"
NOHUP_LOG_FILE = "runtime_live.log"
NOHUP_PID_FILE = "runtime_live.pid"
NOHUP_SCRIPT_FILE = "runtime_live_nohup.sh"
SUPPORT_TICKET_DIR = "LessonProg"
SUPPORT_TICKET_FILE = "support_tickets.json"
SUPPORT_TICKET_LEGACY_FILE = "support_tickets.jsonl"
SUPPORT_COPILOT_QUEUE_FILE = "copilot_queue.md"
TASK_PRIORITY_RANK: dict[str, int] = {"high": 0, "med": 1, "low": 2}
EMERGENCY_DELAY_SECONDS = 0.12
EMERGENCY_COLORS: list[tuple[str, int]] = [
    ("Red", Color(255, 0, 0)),
    ("Blue", Color(0, 0, 255)),
    ("White", Color(255, 255, 255)),
]
EMERGENCY_SOS_STEPS: list[int] = [
    1, 0, 1, 0, 1, 0,
    1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0,
    1, 0, 1, 0, 1, 0,
    0, 0, 0, 0,
]

PATTERN_NAMES: dict[str, str] = {
    "-1": "Emergency SOS",
    "1": "Chase",
    "2": "Random",
    "4": "Random",
    "3": "Bounce",
    "5": "Comet",
    "6": "Theater Chase",
    "7": "Rainbow Sweep",
    "8": "Pulse",
    "9": "Sparkle",
    "10": "Fire Flame",
    "11": "Meteor Shower",
    "12": "Twinkle Stars",
}

# Ordered list of all pattern keys for left/right arrow cycling (SOS excluded)
PATTERN_CYCLE_ORDER: list[str] = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"]


def available_patterns(emergency_only: bool) -> dict[str, str]:
    if emergency_only:
        return {"-1": PATTERN_NAMES["-1"]}
    return dict(PATTERN_NAMES)


def normalize_pattern_for_mode(state: "AppState") -> None:
    if state.emergency_only:
        state.pattern = "-1"

SPEED_LABELS: dict[str, str] = {
    "0": "Constant",
    "1": "Level 1",
    "2": "Level 2",
    "3": "Level 3",
    "4": "Level 4",
    "5": "Level 5",
    "6": "Level 6",
    "7": "Level 7",
    "8": "Level 8",
    "9": "Level 9",
}

SPEED_MAP: dict[str, dict[str, float]] = {
    "1": {
        "0": 0.0,
        "1": 0.12,
        "2": 0.09,
        "3": 0.07,
        "4": 0.05,
        "5": 0.03,
        "6": 0.02,
        "7": 0.015,
        "8": 0.010,
        "9": 0.006,
    },
    "2": {
        "0": 0.0,
        "1": 0.45,
        "2": 0.35,
        "3": 0.27,
        "4": 0.20,
        "5": 0.12,
        "6": 0.08,
        "7": 0.06,
        "8": 0.04,
        "9": 0.02,
    },
    "4": {
        "0": 0.0,
        "1": 0.45,
        "2": 0.35,
        "3": 0.27,
        "4": 0.20,
        "5": 0.12,
        "6": 0.08,
        "7": 0.06,
        "8": 0.04,
        "9": 0.02,
    },
    "3": {
        "0": 0.0,
        "1": 0.10,
        "2": 0.08,
        "3": 0.06,
        "4": 0.04,
        "5": 0.025,
        "6": 0.018,
        "7": 0.012,
        "8": 0.008,
        "9": 0.004,
    },
    "5": {
        "0": 0.0,
        "1": 0.09,
        "2": 0.075,
        "3": 0.06,
        "4": 0.045,
        "5": 0.03,
        "6": 0.02,
        "7": 0.014,
        "8": 0.009,
        "9": 0.006,
    },
    "6": {
        "0": 0.0,
        "1": 0.16,
        "2": 0.13,
        "3": 0.10,
        "4": 0.08,
        "5": 0.06,
        "6": 0.04,
        "7": 0.03,
        "8": 0.02,
        "9": 0.014,
    },
    "7": {
        "0": 0.0,
        "1": 0.10,
        "2": 0.08,
        "3": 0.06,
        "4": 0.05,
        "5": 0.04,
        "6": 0.03,
        "7": 0.02,
        "8": 0.014,
        "9": 0.010,
    },
    "8": {
        "0": 0.0,
        "1": 0.08,
        "2": 0.07,
        "3": 0.06,
        "4": 0.05,
        "5": 0.04,
        "6": 0.03,
        "7": 0.02,
        "8": 0.014,
        "9": 0.010,
    },
    "9": {
        "0": 0.0,
        "1": 0.22,
        "2": 0.18,
        "3": 0.14,
        "4": 0.11,
        "5": 0.08,
        "6": 0.06,
        "7": 0.045,
        "8": 0.03,
        "9": 0.02,
    },
    "10": {
        "0": 0.0,
        "1": 0.10,
        "2": 0.08,
        "3": 0.065,
        "4": 0.05,
        "5": 0.035,
        "6": 0.025,
        "7": 0.018,
        "8": 0.012,
        "9": 0.008,
    },
    "11": {
        "0": 0.0,
        "1": 0.09,
        "2": 0.075,
        "3": 0.06,
        "4": 0.045,
        "5": 0.03,
        "6": 0.02,
        "7": 0.014,
        "8": 0.009,
        "9": 0.006,
    },
    "12": {
        "0": 0.0,
        "1": 0.20,
        "2": 0.16,
        "3": 0.12,
        "4": 0.09,
        "5": 0.07,
        "6": 0.05,
        "7": 0.035,
        "8": 0.025,
        "9": 0.015,
    },
}

CHASE_COLORS: dict[str, tuple[str, int]] = {
    "1": ("Orange", Color(255, 140, 0)),
    "2": ("Green", Color(0, 255, 0)),
    "3": ("Blue", Color(0, 0, 255)),
    "4": ("Rainbow", 0),
    "5": ("Custom", 0),  # uses state.custom_color
}

RANDOM_PALETTES: dict[str, tuple[str, list[int] | None]] = {
    "1": ("Any RGB", None),
    "2": ("Warm", [Color(255, 0, 0), Color(255, 120, 0), Color(255, 255, 0)]),
    "3": ("Cool", [Color(0, 255, 255), Color(0, 0, 255), Color(180, 0, 255)]),
    "4": ("Pastel", [Color(255, 182, 193), Color(152, 251, 152), Color(216, 191, 216), Color(255, 218, 185)]),
    "5": ("Neon", [Color(255, 0, 144), Color(0, 255, 255), Color(57, 255, 20), Color(255, 140, 0)]),
    "6": ("Ocean", [Color(0, 0, 139), Color(0, 128, 128), Color(0, 206, 209), Color(240, 248, 255)]),
    "7": ("Fire", [Color(255, 0, 0), Color(255, 80, 0), Color(255, 200, 0), Color(200, 20, 0)]),
    "8": ("Forest", [Color(0, 100, 0), Color(50, 205, 50), Color(101, 67, 33), Color(154, 205, 50)]),
}

BOUNCE_COLORS: dict[str, tuple[str, int]] = {
    "1": ("Blue", Color(0, 0, 255)),
    "2": ("Purple", Color(180, 0, 255)),
    "3": ("White", Color(255, 255, 255)),
    "4": ("Rainbow", 0),
    "5": ("Custom", 0),  # uses state.custom_color
}

# Shared named color presets for effect patterns (Theater Chase, Comet, Pulse, etc.)
EFFECT_COLORS: dict[str, tuple[str, int]] = {
    "1": ("White",   Color(255, 255, 255)),
    "2": ("Amber",   Color(255, 165,   0)),
    "3": ("Blue",    Color(  0,   0, 255)),
    "4": ("Red",     Color(255,   0,   0)),
    "5": ("Purple",  Color(180,   0, 255)),
    "6": ("Cyan",    Color(  0, 255, 200)),
    "7": ("Green",   Color(  0, 255,   0)),
    "8": ("Gold",    Color(255, 215,   0)),
    "9": ("Custom",  0),  # uses state.custom_color (0 = pattern built-in default)
}

# Named colors for CLI custom color selection (name → packed 0xRRGGBB int)
NAMED_COLORS: dict[str, int] = {
    "red":         Color(255,   0,   0),
    "green":       Color(  0, 255,   0),
    "blue":        Color(  0,   0, 255),
    "white":       Color(255, 255, 255),
    "gold":        Color(255, 215,   0),
    "orange":      Color(255, 140,   0),
    "yellow":      Color(255, 255,   0),
    "purple":      Color(128,   0, 128),
    "violet":      Color(148,   0, 211),
    "magenta":     Color(255,   0, 255),
    "cyan":        Color(  0, 255, 255),
    "teal":        Color(  0, 128, 128),
    "pink":        Color(255, 105, 180),
    "coral":       Color(255,  80,  80),
    "salmon":      Color(255, 140, 105),
    "mint":        Color( 60, 255, 180),
    "lime":        Color( 50, 205,  50),
    "sky":         Color(135, 206, 235),
    "lavender":    Color(230, 190, 255),
    "indigo":      Color( 75,   0, 130),
    "crimson":     Color(220,  20,  60),
    "amber":       Color(255, 191,   0),
    "turquoise":   Color( 64, 224, 208),
    "peach":       Color(255, 218, 185),
    "rose":        Color(255,   0, 127),
    "bronze":      Color(205, 127,  50),
    "maroon":      Color(128,   0,   0),
    "olive":       Color(128, 128,   0),
    "slate":       Color(112, 128, 144),
    "chartreuse":  Color(127, 255,   0),
}


def parse_custom_color(s: str) -> int:
    """Parse a color string into a packed int.

    Accepts:
      - Named: 'gold', 'cyan' (case-insensitive, from NAMED_COLORS)
      - Hex:   '#FF8800' or 'FF8800'
      - CSV:   '255,136,0'
    """
    cleaned = s.strip().lower()
    if cleaned in NAMED_COLORS:
        return NAMED_COLORS[cleaned]
    hex_clean = cleaned.lstrip("#")
    if len(hex_clean) == 6 and all(c in "0123456789abcdef" for c in hex_clean):
        r = int(hex_clean[0:2], 16)
        g = int(hex_clean[2:4], 16)
        b = int(hex_clean[4:6], 16)
        return Color(r, g, b)
    parts = cleaned.split(",")
    if len(parts) == 3:
        try:
            r, g, b = (int(p.strip()) for p in parts)
            if all(0 <= v <= 255 for v in (r, g, b)):
                return Color(r, g, b)
        except ValueError:
            pass
    valid_names = ", ".join(sorted(NAMED_COLORS.keys()))
    raise ValueError(
        f"Invalid color: {s!r}\n"
        f"  Use a name ({valid_names}),\n"
        f"  a hex value (#RRGGBB), or CSV r,g,b (e.g. 255,0,128)"
    )


def print_named_colors() -> None:
    """Print all named colors with ANSI 24-bit color swatches."""
    print("\nNamed colors (use with --custom-color or when prompted):")
    print("  Format options: name | #RRGGBB | r,g,b")
    print()
    names = sorted(NAMED_COLORS.keys())
    col_width = max(len(n) for n in names) + 2
    per_row = 3
    for i in range(0, len(names), per_row):
        row = names[i:i + per_row]
        parts = []
        for name in row:
            packed = NAMED_COLORS[name]
            r = (packed >> 16) & 0xFF
            g = (packed >> 8) & 0xFF
            b = packed & 0xFF
            swatch = f"\x1b[48;2;{r};{g};{b}m   \x1b[0m"
            parts.append(f"{swatch} {name:<{col_width}}")
        print("  " + "  ".join(parts))
    print()


SHORTCUTS_TEXT = """
Runtime shortcuts:
    1..9        Switch pattern directly
    a / d       Cycle pattern left / right
    w / s       Brightness up / down
    + / =       Speed up (Level 1-9)
    -           Speed down
    c           Cycle color option for current pattern
    n           Show named color list
    m / M       Open support task manager (add/edit/done/send/unsend)
    o / O       Print nohup command for current settings
    Ctrl+O      Nohup tools (print and/or save sudo nohup .sh script)
    h           Show this shortcuts help again
    q           Quit
    Ctrl+C      Quit
    (SOS via --SOS or --pattern -1 in interactive prompt or headless JSON)
""".strip()

OUTPUT_EXAMPLE_TEXT = """
Runtime shortcuts:
    1..9        Switch pattern directly
    a / d       Cycle pattern left / right
    w / s       Brightness up / down
    + / =       Speed up    -  Speed down
    c           Cycle color option for current pattern
    n           Show named color list
    h           Show this shortcuts help again
    q           Quit
    Ctrl+C      Quit
Pattern: Chase | Speed: Level 9 | Color: Rainbow
Pattern: Chase | Speed: Level 9 | Color: Rainbow
Pattern: Random | Speed: Level 9 | Palette: Any RGB
Pattern: Bounce | Speed: Level 9 | Color: Blue
Pattern: Chase | Speed: Level 9 | Color: Rainbow
Pattern: Random | Speed: Level 9 | Palette: Any RGB
Pattern: Bounce | Speed: Level 9 | Color: Blue
Pattern: Chase | Speed: Level 9 | Color: Rainbow
Pattern: Bounce | Speed: Level 9 | Color: Blue
Pattern: Random | Speed: Level 9 | Palette: Any RGB
""".strip()


@dataclass
class AppState:
    pattern: str
    speed: str
    chase_color: str
    random_palette: str
    bounce_color: str
    max_brightness: int = LED_BRIGHTNESS
    brightness: int = LED_BRIGHTNESS
    input_mode: str = "off"
    input_pin: int = 23
    analog_path: str = "/sys/bus/iio/devices/iio:device0/in_voltage0_raw"
    analog_max: int = 4095
    emergency_only: bool = False
    emergency_step: int = 0
    emergency_color_index: int = 0
    chase_position: int = 0
    bounce_position: int = 0
    bounce_direction: int = 1
    comet_position: int = 0
    theater_phase: int = 0
    pulse_step: int = 0
    rainbow_offset: int = 0
    custom_color: int = 0  # packed 0xRRGGBB; 0 = use pattern default
    effect_color: str = "9"  # key into EFFECT_COLORS; "9" = Custom → custom_color / built-in default
    meteor_position: int = 0
    fire_heat: list = None  # type: ignore[assignment]
    twinkle_pixels: list = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.fire_heat is None:
            object.__setattr__(self, 'fire_heat', [0] * LED_COUNT)
        if self.twinkle_pixels is None:
            object.__setattr__(self, 'twinkle_pixels', [0] * LED_COUNT)


@dataclass
class RunOptions:
    frames: int = 0
    duration_seconds: float = 0.0
    start_delay_seconds: float = 0.0


strip: Any | None = None


class VirtualStrip:
    def __init__(self, count: int) -> None:
        self.count = count
        self.pixels: list[int] = [Color(0, 0, 0)] * count
        self.brightness = LED_BRIGHTNESS
        self.frame = 0
        terminal_width = shutil.get_terminal_size((120, 30)).columns
        self.render_width = max(20, terminal_width - 2)
        self._rendered_lines = 0
        self._has_animated = False

    def begin(self) -> None:
        return

    def setPixelColor(self, n: int, color: int) -> None:
        if 0 <= n < self.count:
            self.pixels[n] = color

    def setBrightness(self, brightness: int) -> None:
        self.brightness = max(0, min(255, int(brightness)))

    def show(self) -> None:
        self.frame += 1
        ascii_pixels = "".join(color_to_ascii(pixel) for pixel in self.pixels)
        if not sys.stdout.isatty():
            print(f"Frame {self.frame:04d} | {ascii_pixels}")
            return

        prefix = f"Frame {self.frame:04d} | "
        first_line_capacity = max(10, self.render_width - len(prefix))
        tail = ascii_pixels[first_line_capacity:]

        lines = [f"{prefix}{ascii_pixels[:first_line_capacity]}"]
        lines.extend(
            tail[i : i + self.render_width]
            for i in range(0, len(tail), self.render_width)
        )

        chunks = [
            line.ljust(self.render_width)
            for line in lines
        ]

        if self._has_animated:
            sys.stdout.write(f"\x1b[{self._rendered_lines}A\r")
        else:
            self._has_animated = True

        for chunk in chunks:
            sys.stdout.write("\x1b[2K\r")
            sys.stdout.write(f"{chunk}\n")

        self._rendered_lines = len(chunks) + 1
        sys.stdout.flush()

    def finish(self) -> None:
        if sys.stdout.isatty() and self._has_animated:
            sys.stdout.write("\n")
            sys.stdout.flush()


def init_strip() -> None:
    global strip
    if not _HAVE_RPI_WS281X:
        raise RuntimeError(
            "rpi_ws281x not installed.\n"
            "  • Run via the launcher (handles venv automatically):  ./runtime.sh\n"
            "  • Or set up manually: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt\n"
            "  • To run without hardware (ASCII simulation): add --test"
        )

    # Probe /dev/mem before handing control to the C library.  Without the
    # right permissions the C library segfaults rather than raising a catchable
    # Python exception.  This check works whether the process is root OR the
    # Python binary has been granted cap_sys_rawio via setup_permissions.sh.
    try:
        open("/dev/mem", "rb").close()
    except PermissionError:
        raise RuntimeError(
            "Hardware LED access requires elevated privileges.\n"
            "  • Run with sudo:          sudo .venv/bin/python3 into.py\n"
            "  • Or grant capabilities once (no sudo needed afterwards):\n"
            "        sudo bash setup_permissions.sh\n"
            "  • To run without hardware (ASCII simulation): add --test"
        )

    strip = Adafruit_NeoPixel(
        LED_COUNT,
        LED_PIN,
        LED_FREQ_HZ,
        LED_DMA,
        LED_INVERT,
        LED_BRIGHTNESS,
        LED_CHANNEL,
    )


def init_virtual_strip() -> None:
    global strip
    strip = VirtualStrip(LED_COUNT)


def get_strip() -> Any:
    if strip is None:
        raise RuntimeError("LED strip not initialized")
    return strip


def clear_strip(show_now: bool = True) -> None:
    if strip is None:
        return
    active_strip = get_strip()
    for i in range(LED_COUNT):
        active_strip.setPixelColor(i, Color(0, 0, 0))
    if show_now:
        active_strip.show()


def clamp_brightness(value: int) -> int:
    return max(0, min(255, value))


def as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return default


def as_str(value: Any, default: str) -> str:
    if isinstance(value, str):
        return value
    return default


def set_strip_brightness(value: int) -> None:
    active_strip = get_strip()
    brightness = clamp_brightness(value)
    if hasattr(active_strip, "setBrightness"):
        active_strip.setBrightness(brightness)


def apply_brightness_from_state(state: AppState) -> None:
    state.brightness = clamp_brightness(state.brightness)
    state.max_brightness = clamp_brightness(state.max_brightness)
    set_strip_brightness(state.brightness)


def read_digital_input(pin: int) -> int | None:
    try:
        import RPi.GPIO as GPIO  # type: ignore[import-not-found]
    except ImportError:
        return None

    if not getattr(read_digital_input, "_gpio_initialized", False):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin, GPIO.IN)
        setattr(read_digital_input, "_gpio_initialized", True)
        setattr(read_digital_input, "_gpio_pin", pin)
    elif getattr(read_digital_input, "_gpio_pin", pin) != pin:
        GPIO.setup(pin, GPIO.IN)
        setattr(read_digital_input, "_gpio_pin", pin)

    return int(GPIO.input(pin))


def read_analog_input(path: str) -> int | None:
    analog_file = Path(path)
    if not analog_file.exists():
        return None
    try:
        raw = analog_file.read_text(encoding="utf-8").strip()
        return int(raw)
    except (ValueError, OSError):
        return None


def apply_pi_input_response(state: AppState) -> None:
    if state.input_mode == "off":
        return

    if state.input_mode == "digital":
        digital_value = read_digital_input(state.input_pin)
        if digital_value is None:
            return
        state.brightness = state.max_brightness if digital_value > 0 else 0
        set_strip_brightness(state.brightness)
        return

    analog_value = read_analog_input(state.analog_path)
    if analog_value is None:
        return
    analog_max = max(1, int(state.analog_max))
    bounded = max(0, min(analog_max, analog_value))
    scaled = int((bounded / analog_max) * state.max_brightness)
    state.brightness = clamp_brightness(scaled)
    set_strip_brightness(state.brightness)


def color_to_ascii(color: int) -> str:
    if color == 0:
        return "."

    red = (color >> 16) & 0xFF
    green = (color >> 8) & 0xFF
    blue = color & 0xFF

    if red > 180 and green > 180 and blue > 180:
        return "W"
    if red >= green and red >= blue:
        return "R"
    if green >= red and green >= blue:
        return "G"
    return "B"


def resolve_effect_color(state: AppState) -> int:
    """Return the active effect color for Theater Chase, Comet, Pulse, etc.

    Returns a packed 0xRRGGBB int.  0 means 'use the pattern's built-in default'.
    When effect_color is "9" (Custom) the raw custom_color value is returned so
    the pattern falls back to its own default when custom_color is also 0.
    """
    if state.effect_color == "9":
        return state.custom_color
    entry = EFFECT_COLORS.get(state.effect_color)
    return entry[1] if entry else state.custom_color


def pattern_step_chase(state: AppState) -> None:
    active_strip = get_strip()
    clear_strip(show_now=False)
    try:
        if state.chase_color == "4":
            color = wheel((state.rainbow_offset + state.chase_position * 8) & 255)
            state.rainbow_offset = (state.rainbow_offset + 3) & 255
        elif state.chase_color == "5":
            color = state.custom_color if state.custom_color != 0 else Color(255, 215, 0)
        else:
            color = CHASE_COLORS.get(state.chase_color, CHASE_COLORS["1"])[1]
        active_strip.setPixelColor(state.chase_position, color)
        active_strip.show()
        state.chase_position = (state.chase_position + 1) % LED_COUNT
    except Exception as e:
        print(f"[ERROR] Chase pattern step failed: {e}")
        state.chase_color = "1"


def pattern_step_random(state: AppState) -> None:
    active_strip = get_strip()
    try:
        palette = RANDOM_PALETTES.get(state.random_palette, RANDOM_PALETTES["1"])[1]
        for i in range(LED_COUNT):
            if palette is None:
                active_strip.setPixelColor(
                    i,
                    Color(
                        random.randint(0, 255),
                        random.randint(0, 255),
                        random.randint(0, 255),
                    ),
                )
            else:
                active_strip.setPixelColor(i, random.choice(palette))
        active_strip.show()
    except Exception as e:
        print(f"[ERROR] Random pattern step failed: {e}")
        state.random_palette = "1"


def pattern_step_bounce(state: AppState) -> None:
    active_strip = get_strip()
    clear_strip(show_now=False)
    try:
        if state.bounce_color == "4":
            color = wheel((state.rainbow_offset + state.bounce_position * 8) & 255)
            state.rainbow_offset = (state.rainbow_offset + 3) & 255
        elif state.bounce_color == "5":
            color = state.custom_color if state.custom_color != 0 else Color(255, 215, 0)
        else:
            color = BOUNCE_COLORS.get(state.bounce_color, BOUNCE_COLORS["1"])[1]
        active_strip.setPixelColor(state.bounce_position, color)
        active_strip.show()

        if state.bounce_position == LED_COUNT - 1:
            state.bounce_direction = -1
        elif state.bounce_position == 0:
            state.bounce_direction = 1
        state.bounce_position += state.bounce_direction
    except Exception as e:
        print(f"[ERROR] Bounce pattern step failed: {e}")
        state.bounce_color = "1"


def pattern_step_emergency(state: AppState) -> None:
    active_strip = get_strip()
    try:
        step_on = EMERGENCY_SOS_STEPS[state.emergency_step] > 0
        color = EMERGENCY_COLORS[state.emergency_color_index % len(EMERGENCY_COLORS)][1]

        for i in range(LED_COUNT):
            active_strip.setPixelColor(i, color if step_on else Color(0, 0, 0))
        active_strip.show()

        state.emergency_step += 1
        if state.emergency_step >= len(EMERGENCY_SOS_STEPS):
            state.emergency_step = 0
            state.emergency_color_index = (state.emergency_color_index + 1) % len(EMERGENCY_COLORS)
    except Exception as e:
        print(f"[ERROR] Emergency pattern step failed: {e}")
        state.emergency_step = 0
        state.emergency_color_index = 0


def pattern_step_comet(state: AppState) -> None:
    active_strip = get_strip()
    clear_strip(show_now=False)
    try:
        head = state.comet_position % LED_COUNT
        eff = resolve_effect_color(state)
        # Use effect/custom color base if set, else amber
        base_r = (eff >> 16) & 0xFF if eff else 255
        base_g = (eff >> 8) & 0xFF if eff else 165
        base_b = eff & 0xFF if eff else 0
        for trail in range(10):
            idx = (head - trail) % LED_COUNT
            fade = max(0, 255 - trail * 28)
            r = int(base_r * fade / 255)
            g = int(base_g * fade / 255)
            b = int(base_b * fade / 255)
            active_strip.setPixelColor(idx, Color(r, g, b))
        active_strip.show()
        state.comet_position = (state.comet_position + 1) % LED_COUNT
    except Exception as e:
        print(f"[ERROR] Comet pattern step failed: {e}")


def pattern_step_theater_chase(state: AppState) -> None:
    active_strip = get_strip()
    clear_strip(show_now=False)
    try:
        eff = resolve_effect_color(state)
        slot_color = eff if eff != 0 else Color(200, 200, 220)
        for i in range(LED_COUNT):
            if (i + state.theater_phase) % 3 == 0:
                active_strip.setPixelColor(i, slot_color)
        active_strip.show()
        state.theater_phase = (state.theater_phase + 1) % 3
    except Exception as e:
        print(f"[ERROR] Theater chase pattern step failed: {e}")


def pattern_step_rainbow_sweep(state: AppState) -> None:
    active_strip = get_strip()
    try:
        for i in range(LED_COUNT):
            color_index = (i * 256 // LED_COUNT + state.rainbow_offset) & 255
            active_strip.setPixelColor(i, wheel(color_index))
        active_strip.show()
        state.rainbow_offset = (state.rainbow_offset + 4) & 255
    except Exception as e:
        print(f"[ERROR] Rainbow sweep pattern step failed: {e}")


def pattern_step_pulse(state: AppState) -> None:
    active_strip = get_strip()
    try:
        phase = (state.pulse_step % 256) / 255.0
        bright = int((math.sin(phase * math.tau) + 1.0) * 0.5 * 255)
        eff = resolve_effect_color(state)
        if eff != 0:
            base_r = (eff >> 16) & 0xFF
            base_g = (eff >> 8) & 0xFF
            base_b = eff & 0xFF
            color = Color(int(base_r * bright / 255), int(base_g * bright / 255), int(base_b * bright / 255))
        else:
            color = Color(bright, 0, max(0, bright // 3))
        for i in range(LED_COUNT):
            active_strip.setPixelColor(i, color)
        active_strip.show()
        state.pulse_step = (state.pulse_step + 5) % 256
    except Exception as e:
        print(f"[ERROR] Pulse pattern step failed: {e}")


def pattern_step_sparkle(state: AppState) -> None:
    active_strip = get_strip()
    clear_strip(show_now=False)
    try:
        sparkle_count = max(1, LED_COUNT // 10)
        eff = resolve_effect_color(state)
        for _ in range(sparkle_count):
            idx = random.randint(0, LED_COUNT - 1)
            twinkle = random.randint(120, 255)
            if eff != 0:
                base_r = (eff >> 16) & 0xFF
                base_g = (eff >> 8) & 0xFF
                base_b = eff & 0xFF
                color = Color(int(base_r * twinkle / 255), int(base_g * twinkle / 255), int(base_b * twinkle / 255))
            else:
                color = Color(twinkle, twinkle, twinkle)
            active_strip.setPixelColor(idx, color)
        active_strip.show()
    except Exception as e:
        print(f"[ERROR] Sparkle pattern step failed: {e}")


def get_delay(state: AppState) -> float:
    if state.pattern == "-1":
        return EMERGENCY_DELAY_SECONDS
    pattern_map = SPEED_MAP.get(state.pattern, SPEED_MAP["1"])
    return pattern_map.get(state.speed, pattern_map["5"])


def pattern_step_fire(state: AppState) -> None:
    """Fire Flame — flickering heat in orange/red/yellow (custom_color tints the base hue)."""
    active_strip = get_strip()
    try:
        heat = state.fire_heat
        # Cool down every cell a little
        for i in range(LED_COUNT):
            cooldown = random.randint(0, 3)
            heat[i] = max(0, heat[i] - cooldown)
        # Heat from each cell drifts up
        for k in range(LED_COUNT - 1, 2, -1):
            heat[k] = (heat[k - 1] + heat[k - 2] + heat[k - 2]) // 3
        # Randomly ignite new sparks near the bottom
        if random.randint(0, 9) < 7:
            y = random.randint(0, min(7, LED_COUNT - 1))
            heat[y] = min(255, heat[y] + random.randint(160, 255))
        # Convert heat to color
        eff = resolve_effect_color(state)
        base_r = (eff >> 16) & 0xFF if eff else 255
        base_g = (eff >> 8) & 0xFF if eff else 80
        base_b = eff & 0xFF if eff else 0
        for i in range(LED_COUNT):
            t = heat[i]
            if t < 85:
                r = int(base_r * t / 85)
                g = int(base_g * t / 85)
                b = int(base_b * t / 85)
            elif t < 170:
                r = base_r
                g = min(255, base_g + int((255 - base_g) * (t - 85) / 85))
                b = base_b
            else:
                r = base_r
                g = 255
                b = min(255, base_b + int((255 - base_b) * (t - 170) / 85))
            active_strip.setPixelColor(i, Color(r, g, b))
        active_strip.show()
    except Exception as e:
        print(f"[ERROR] Fire Flame pattern step failed: {e}")


def pattern_step_meteor(state: AppState) -> None:
    """Meteor Shower — bright head with a long fading tail, looping endlessly."""
    active_strip = get_strip()
    clear_strip(show_now=False)
    try:
        tail_length = 16
        eff = resolve_effect_color(state)
        base_r = (eff >> 16) & 0xFF if eff else 200
        base_g = (eff >> 8) & 0xFF if eff else 200
        base_b = eff & 0xFF if eff else 255
        for trail in range(tail_length):
            idx = (state.meteor_position - trail) % LED_COUNT
            fade = max(0, 255 - int(trail * 255 / tail_length))
            r = int(base_r * fade / 255)
            g = int(base_g * fade / 255)
            b = int(base_b * fade / 255)
            active_strip.setPixelColor(idx, Color(r, g, b))
        active_strip.show()
        state.meteor_position = (state.meteor_position + 1) % LED_COUNT
    except Exception as e:
        print(f"[ERROR] Meteor Shower pattern step failed: {e}")


def pattern_step_twinkle(state: AppState) -> None:
    """Twinkle Stars — pixels fade in/out independently."""
    active_strip = get_strip()
    try:
        px = state.twinkle_pixels
        # Each pixel changes brightness by a random delta each frame
        for i in range(LED_COUNT):
            delta = random.choice([-30, -20, -10, 10, 20, 30, 40])
            px[i] = max(0, min(255, px[i] + delta))
            # Small chance to switch on/off abruptly
            if random.randint(0, 40) == 0:
                px[i] = random.choice([0, 0, random.randint(160, 255)])
        eff = resolve_effect_color(state)
        base_r = (eff >> 16) & 0xFF if eff else 255
        base_g = (eff >> 8) & 0xFF if eff else 255
        base_b = eff & 0xFF if eff else 255
        for i in range(LED_COUNT):
            bright = px[i]
            r = int(base_r * bright / 255)
            g = int(base_g * bright / 255)
            b = int(base_b * bright / 255)
            active_strip.setPixelColor(i, Color(r, g, b))
        active_strip.show()
    except Exception as e:
        print(f"[ERROR] Twinkle Stars pattern step failed: {e}")


def wheel(position: int) -> int:
    pos = 255 - position
    if pos < 85:
        return Color(255 - pos * 3, 0, pos * 3)
    if pos < 170:
        pos -= 85
        return Color(0, pos * 3, 255 - pos * 3)
    pos -= 170
    return Color(pos * 3, 255 - pos * 3, 0)


def cycle_choice(current: str, choices: dict[str, Any]) -> str:
    keys = list(choices.keys())
    idx = keys.index(current)
    return keys[(idx + 1) % len(keys)]


def print_status(state: AppState) -> None:
    pattern_name = PATTERN_NAMES.get(state.pattern, f"Pattern {state.pattern}")
    speed_name = SPEED_LABELS[state.speed]

    def custom_color_label() -> str:
        if state.custom_color == 0:
            return "default"
        r = (state.custom_color >> 16) & 0xFF
        g = (state.custom_color >> 8) & 0xFF
        b = state.custom_color & 0xFF
        swatch = f"\x1b[48;2;{r};{g};{b}m   \x1b[0m" if sys.stdout.isatty() else ""
        return f"{swatch} #{r:02X}{g:02X}{b:02X}"

    if state.pattern == "1":
        color_name = CHASE_COLORS[state.chase_color][0]
        detail = f"Color: {color_name}" + (f" ({custom_color_label()})" if state.chase_color == "5" else "")
    elif state.pattern in {"2", "4"}:
        palette_name = RANDOM_PALETTES[state.random_palette][0]
        detail = f"Palette: {palette_name}"
    elif state.pattern == "3":
        color_name = BOUNCE_COLORS[state.bounce_color][0]
        detail = f"Color: {color_name}" + (f" ({custom_color_label()})" if state.bounce_color == "5" else "")
    elif state.pattern == "-1":
        color_name = EMERGENCY_COLORS[state.emergency_color_index][0]
        detail = f"Color: {color_name} | Panic SOS"
    elif state.pattern in {"5", "6", "8", "9", "10", "11", "12"}:
        effect_name = EFFECT_COLORS.get(state.effect_color, EFFECT_COLORS["9"])[0]
        eff_val = resolve_effect_color(state)
        if state.effect_color == "9" and eff_val != 0:
            # Custom wheel color — show hex swatch
            r = (eff_val >> 16) & 0xFF
            g = (eff_val >> 8) & 0xFF
            b = eff_val & 0xFF
            swatch = f"\x1b[48;2;{r};{g};{b}m   \x1b[0m" if sys.stdout.isatty() else ""
            detail = f"Color: {effect_name} ({swatch} #{r:02X}{g:02X}{b:02X})"
        else:
            detail = f"Color: {effect_name}"
    elif state.pattern == "7":
        detail = "Color: Full Rainbow"
    else:
        detail = ""

    brightness_pct = int((max(0, state.brightness) / max(1, state.max_brightness)) * 100)
    print(f"Pattern: {pattern_name} | Speed: {speed_name} | Brightness: {state.brightness} ({brightness_pct}%) | {detail}")


def maybe_read_key() -> str | None:
    ready, _, _ = select.select([sys.stdin], [], [], 0)
    if not ready:
        return None
    key = sys.stdin.read(1)
    # Swallow bare ESC and CSI sequences so they don't surface as noise.
    if key == "\x1b":
        # Drain any following bytes of the escape sequence quietly.
        while True:
            r, _, _ = select.select([sys.stdin], [], [], 0.05)
            if not r:
                break
            ch = sys.stdin.read(1)
            # End of CSI sequence — letter terminates it
            if ch.isalpha() or ch == "~":
                break
        return None
    return key


def support_ticket_store_path() -> Path:
    out_dir = Path(SUPPORT_TICKET_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / SUPPORT_TICKET_FILE


def _state_snapshot(state: AppState) -> dict[str, Any]:
    return {
        "pattern": state.pattern,
        "speed": state.speed,
        "brightness": state.brightness,
        "max_brightness": state.max_brightness,
        "chase_color": state.chase_color,
        "random_palette": state.random_palette,
        "bounce_color": state.bounce_color,
        "emergency_only": state.emergency_only,
    }


def _load_support_ticket_store(path: Path) -> dict[str, Any]:
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("tasks"), list):
                raw_tasks = data.get("tasks", [])
                tasks: list[dict[str, Any]] = []
                max_id = 0
                for raw_task in raw_tasks:
                    if not isinstance(raw_task, dict):
                        continue
                    task_id = int(raw_task.get("id", 0))
                    if task_id <= 0:
                        continue
                    max_id = max(max_id, task_id)
                    memo = str(raw_task.get("memo", "")).strip()
                    tasks.append(
                        {
                            "id": task_id,
                            "memo": memo,
                            "priority": normalize_priority(raw_task.get("priority", "med")),
                            "status": "done" if str(raw_task.get("status", "open")) == "done" else "open",
                            "created_utc": raw_task.get("created_utc"),
                            "updated_utc": raw_task.get("updated_utc"),
                            "completed_utc": raw_task.get("completed_utc"),
                            "sent_to_copilot_utc": raw_task.get("sent_to_copilot_utc"),
                            "state": raw_task.get("state", {}),
                        }
                    )

                next_id = int(data.get("next_id", max_id + 1))
                next_id = max(next_id, max_id + 1)
                return {"next_id": next_id, "tasks": tasks}
        except (json.JSONDecodeError, OSError):
            pass

    # Migrate legacy append-only jsonl entries if present.
    legacy_path = path.parent / SUPPORT_TICKET_LEGACY_FILE
    tasks: list[dict[str, Any]] = []
    next_id = 1
    if legacy_path.exists():
        try:
            for raw_line in legacy_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                row = json.loads(line)
                memo = str(row.get("memo", "")).strip()
                if not memo:
                    continue
                created = str(row.get("timestamp_utc", datetime.now(timezone.utc).isoformat()))
                tasks.append(
                    {
                        "id": next_id,
                        "memo": memo,
                        "priority": "med",
                        "status": "open",
                        "created_utc": created,
                        "updated_utc": created,
                        "completed_utc": None,
                        "sent_to_copilot_utc": None,
                        "state": row.get("state", {}),
                    }
                )
                next_id += 1
        except (json.JSONDecodeError, OSError):
            tasks = []
            next_id = 1

    return {"next_id": next_id, "tasks": tasks}


def _write_support_ticket_store(path: Path, store: dict[str, Any]) -> None:
    path.write_text(json.dumps(store, indent=2) + "\n", encoding="utf-8")


def normalize_priority(value: Any) -> str:
    normalized = str(value).strip().lower()
    if normalized in TASK_PRIORITY_RANK:
        return normalized
    return "med"


def _sorted_tasks(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        tasks,
        key=lambda t: (
            0 if str(t.get("status", "open")) == "open" else 1,
            TASK_PRIORITY_RANK.get(normalize_priority(t.get("priority", "med")), 1),
            int(t.get("id", 0)),
        ),
    )


def append_support_ticket_task(state: AppState, memo: str, priority: str = "med") -> tuple[Path, int]:
    path = support_ticket_store_path()
    store = _load_support_ticket_store(path)
    task_id = int(store.get("next_id", 1))
    now = datetime.now(timezone.utc).isoformat()
    task = {
        "id": task_id,
        "memo": memo,
        "priority": normalize_priority(priority),
        "status": "open",
        "created_utc": now,
        "updated_utc": now,
        "completed_utc": None,
        "sent_to_copilot_utc": None,
        "state": _state_snapshot(state),
    }

    tasks = store.get("tasks", [])
    if not isinstance(tasks, list):
        tasks = []
    tasks.append(task)
    store["tasks"] = _sorted_tasks(tasks)
    store["next_id"] = task_id + 1
    _write_support_ticket_store(path, store)
    return path, task_id


def list_support_ticket_tasks() -> tuple[Path, list[dict[str, Any]]]:
    path = support_ticket_store_path()
    store = _load_support_ticket_store(path)
    tasks = store.get("tasks", [])
    if not isinstance(tasks, list):
        tasks = []
    return path, _sorted_tasks(tasks)


def update_support_ticket_task(task_id: int, new_memo: str, new_priority: str | None = None) -> tuple[Path, bool]:
    path = support_ticket_store_path()
    store = _load_support_ticket_store(path)
    tasks = store.get("tasks", [])
    if not isinstance(tasks, list):
        return path, False

    now = datetime.now(timezone.utc).isoformat()
    changed = False
    for task in tasks:
        if int(task.get("id", 0)) == task_id:
            task["memo"] = new_memo
            if new_priority is not None:
                task["priority"] = normalize_priority(new_priority)
            task["updated_utc"] = now
            changed = True
            break

    if changed:
        store["tasks"] = _sorted_tasks(tasks)
        _write_support_ticket_store(path, store)
    return path, changed


def complete_support_ticket_task(task_id: int) -> tuple[Path, bool]:
    path = support_ticket_store_path()
    store = _load_support_ticket_store(path)
    tasks = store.get("tasks", [])
    if not isinstance(tasks, list):
        return path, False

    now = datetime.now(timezone.utc).isoformat()
    changed = False
    for task in tasks:
        if int(task.get("id", 0)) == task_id:
            task["status"] = "done"
            task["updated_utc"] = now
            task["completed_utc"] = now
            changed = True
            break

    if changed:
        store["tasks"] = _sorted_tasks(tasks)
        _write_support_ticket_store(path, store)
    return path, changed


def reopen_support_ticket_task(task_id: int) -> tuple[Path, bool]:
    path = support_ticket_store_path()
    store = _load_support_ticket_store(path)
    tasks = store.get("tasks", [])
    if not isinstance(tasks, list):
        return path, False

    now = datetime.now(timezone.utc).isoformat()
    changed = False
    for task in tasks:
        if int(task.get("id", 0)) == task_id:
            task["status"] = "open"
            task["updated_utc"] = now
            task["completed_utc"] = None
            changed = True
            break

    if changed:
        store["tasks"] = _sorted_tasks(tasks)
        _write_support_ticket_store(path, store)
    return path, changed


def delete_support_ticket_task(task_id: int) -> tuple[Path, bool]:
    path = support_ticket_store_path()
    store = _load_support_ticket_store(path)
    tasks = store.get("tasks", [])
    if not isinstance(tasks, list):
        return path, False

    original_len = len(tasks)
    tasks = [task for task in tasks if int(task.get("id", 0)) != task_id]
    changed = len(tasks) != original_len

    if changed:
        store["tasks"] = _sorted_tasks(tasks)
        _write_support_ticket_store(path, store)
    return path, changed


def unsend_support_ticket_task(task_id: int) -> tuple[Path, bool]:
    path = support_ticket_store_path()
    store = _load_support_ticket_store(path)
    tasks = store.get("tasks", [])
    if not isinstance(tasks, list):
        return path, False

    now = datetime.now(timezone.utc).isoformat()
    changed = False
    for task in tasks:
        if int(task.get("id", 0)) == task_id:
            task["sent_to_copilot_utc"] = None
            task["updated_utc"] = now
            changed = True
            break

    if changed:
        store["tasks"] = _sorted_tasks(tasks)
        _write_support_ticket_store(path, store)
    return path, changed


def parse_task_ids(raw_ids: str) -> list[int]:
    values: list[int] = []
    for token in raw_ids.split(","):
        cleaned = token.strip()
        if cleaned.isdigit():
            values.append(int(cleaned))
    return values


def send_tasks_to_copilot(raw_ids: str) -> tuple[Path, Path, int]:
    store_path = support_ticket_store_path()
    queue_path = store_path.parent / SUPPORT_COPILOT_QUEUE_FILE

    store = _load_support_ticket_store(store_path)
    tasks = store.get("tasks", [])
    if not isinstance(tasks, list):
        tasks = []

    selected_ids = parse_task_ids(raw_ids)
    if selected_ids:
        selected = [task for task in tasks if int(task.get("id", 0)) in selected_ids]
    else:
        selected = [task for task in tasks if str(task.get("status", "open")) == "open"]

    if not selected:
        return store_path, queue_path, 0

    now = datetime.now(timezone.utc).isoformat()
    lines = [
        f"\n## Copilot Handoff {now}",
        "",
        "Use the tasks below as implementation items:",
        "",
    ]
    for task in selected:
        task_id = int(task.get("id", 0))
        memo = str(task.get("memo", "")).strip()
        status = str(task.get("status", "open"))
        checkbox = "x" if status == "done" else " "
        lines.append(f"- [{checkbox}] #{task_id}: {memo}")

    with queue_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")

    selected_id_set = {int(task.get("id", 0)) for task in selected}
    for task in tasks:
        if int(task.get("id", 0)) in selected_id_set:
            task["sent_to_copilot_utc"] = now
            task["updated_utc"] = now

    store["tasks"] = _sorted_tasks(tasks)
    _write_support_ticket_store(store_path, store)
    return store_path, queue_path, len(selected)


def _print_support_tasks(tasks: list[dict[str, Any]]) -> None:
    if not tasks:
        print("No support tasks yet.")
        return
    print("ID | Pri  | Status | Sent | Memo")
    print("--------------------------------")
    for task in tasks:
        task_id = int(task.get("id", 0))
        priority = normalize_priority(task.get("priority", "med"))
        status = str(task.get("status", "open"))
        sent = "Y" if task.get("sent_to_copilot_utc") else "N"
        memo = str(task.get("memo", "")).strip()
        print(f"{task_id:>2} | {priority:<4} | {status:<6} | {sent:<4} | {memo}")


def prompt_support_ticket_manager(fd: int, old_settings: Any, state: AppState) -> None:
    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    try:
        print("\nSupport tasks: [a]dd [l]ist [e]dit [d]one [r]eopen [x]delete [s]end [u]unsend [q]cancel")
        action = (input("Action (default a): ").strip().lower() or "a")

        if action == "l":
            path, tasks = list_support_ticket_tasks()
            _print_support_tasks(tasks)
            print(f"File: {path}")
        elif action == "e":
            raw_id = input("Task ID to edit: ").strip()
            new_memo = input("Updated memo: ").strip()
            new_priority = input("Updated priority (high/med/low, blank=keep): ").strip().lower()
            if raw_id.isdigit() and new_memo:
                path, changed = update_support_ticket_task(
                    int(raw_id),
                    new_memo,
                    new_priority if new_priority else None,
                )
                if changed:
                    print(f"Support task updated in: {path}")
                else:
                    print("Task ID not found.")
            else:
                print("Edit canceled (invalid ID or empty memo).")
        elif action == "d":
            raw_id = input("Task ID to mark done: ").strip()
            if raw_id.isdigit():
                path, changed = complete_support_ticket_task(int(raw_id))
                if changed:
                    print(f"Support task marked done in: {path}")
                else:
                    print("Task ID not found.")
            else:
                print("Done action canceled (invalid ID).")
        elif action == "r":
            raw_id = input("Task ID to reopen: ").strip()
            if raw_id.isdigit():
                path, changed = reopen_support_ticket_task(int(raw_id))
                if changed:
                    print(f"Support task reopened in: {path}")
                else:
                    print("Task ID not found.")
            else:
                print("Reopen canceled (invalid ID).")
        elif action == "x":
            raw_id = input("Task ID to delete: ").strip()
            if raw_id.isdigit():
                path, changed = delete_support_ticket_task(int(raw_id))
                if changed:
                    print(f"Support task deleted from: {path}")
                else:
                    print("Task ID not found.")
            else:
                print("Delete canceled (invalid ID).")
        elif action == "s":
            raw_ids = input("Task IDs to send (comma-separated, blank=open tasks): ").strip()
            store_path, queue_path, sent_count = send_tasks_to_copilot(raw_ids)
            if sent_count > 0:
                print(f"Sent {sent_count} task(s) to Copilot queue: {queue_path}")
                print(f"Task store updated: {store_path}")
            else:
                print("No matching tasks to send.")
        elif action == "u":
            raw_id = input("Task ID to unsend: ").strip()
            if raw_id.isdigit():
                path, changed = unsend_support_ticket_task(int(raw_id))
                if changed:
                    print(f"Support task unsent in: {path}")
                else:
                    print("Task ID not found.")
            else:
                print("Unsend canceled (invalid ID).")
        elif action == "q":
            print("Support manager canceled.")
        else:
            memo = input("Support task memo: ").strip()
            priority = input("Priority (high/med/low, default med): ").strip().lower() or "med"
            if memo:
                path, task_id = append_support_ticket_task(state, memo, priority)
                print(f"Support task #{task_id} saved: {path}")
            else:
                print("Support task canceled (empty memo).")
    except (KeyboardInterrupt, EOFError):
        print("Support manager canceled.")
    finally:
        tty.setcbreak(fd)


def build_nohup_command(state: AppState, options: RunOptions, use_sudo: bool = False) -> str:
    command: list[str] = [
        "nohup",
        sys.executable,
        "into.py",
        "--speed",
        state.speed,
        "--chase-color",
        state.chase_color,
        "--random-palette",
        state.random_palette,
        "--bounce-color",
        state.bounce_color,
        "--brightness",
        str(state.brightness),
        "--max-brightness",
        str(state.max_brightness),
        "--pi-input-mode",
        state.input_mode,
        "--pi-input-pin",
        str(state.input_pin),
        "--analog-path",
        state.analog_path,
        "--analog-max",
        str(state.analog_max),
    ]

    if state.pattern == "-1":
        command.extend(["--SOS"])
    else:
        command.extend(["--pattern", state.pattern])

    if options.frames > 0:
        command.extend(["--frames", str(options.frames)])
    if options.duration_seconds > 0:
        command.extend(["--duration-seconds", str(options.duration_seconds)])
    if options.start_delay_seconds > 0:
        command.extend(["--start-delay-seconds", str(options.start_delay_seconds)])
    if state.emergency_only:
        command.append("--emergency-only")

    command.extend([">", NOHUP_LOG_FILE, "2>&1", "&", "echo", "$!", ">", NOHUP_PID_FILE])
    if use_sudo:
        command.insert(0, "sudo")
    return " ".join(command)


def print_nohup_command_block(command: str) -> None:
    sys.stdout.write(
        "\r\n=== Heads Up: Background (nohup) launch command ===\r\n"
        + command + "\r\n"
        f"# Stop with: kill $(cat {NOHUP_PID_FILE})\r\n"
        f"# Logs:      {NOHUP_LOG_FILE}\r\n"
        "=====================================================\r\n"
    )
    sys.stdout.flush()


def save_nohup_script(path: Path, command: str) -> Path:
    script = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n\n"
        f"{command}\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(script, encoding="utf-8")
    os.chmod(path, 0o750)
    return path


def prompt_nohup_tools(fd: int, old_settings: Any, state: AppState, options: RunOptions) -> None:
    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    try:
        cmd = build_nohup_command(state, options)
        sudo_cmd = build_nohup_command(state, options, use_sudo=True)
        print("\nNohup tools:")
        print("  [p] Print nohup command")
        print("  [s] Save sudo nohup script (.sh)")
        print("  [b] Both print and save")
        print("  [q] Cancel")
        choice = (input("Choose option [p/s/b/q] (default p): ").strip().lower() or "p")

        if choice == "q":
            print("Nohup tools canceled.")
            return

        if choice in {"p", "b"}:
            print_nohup_command_block(cmd)

        if choice in {"s", "b"}:
            default_path = NOHUP_SCRIPT_FILE
            raw_path = input(f"Script path (default {default_path}): ").strip()
            out_path = Path(raw_path or default_path).expanduser()
            saved = save_nohup_script(out_path, sudo_cmd)
            print(f"Saved script: {saved}")
            print(f"Run with: bash {saved}")
    except (KeyboardInterrupt, EOFError):
        print("Nohup tools canceled.")
    finally:
        tty.setcbreak(fd)


def handle_key(state: AppState, options: RunOptions, key: str, fd: int, old_settings: Any) -> bool:
    allowed = available_patterns(state.emergency_only)

    # Arrow left/right: cycle through non-SOS patterns
    if key == "d":
        if state.pattern in PATTERN_CYCLE_ORDER:
            idx = PATTERN_CYCLE_ORDER.index(state.pattern)
            state.pattern = PATTERN_CYCLE_ORDER[(idx + 1) % len(PATTERN_CYCLE_ORDER)]
        elif not state.emergency_only:
            state.pattern = PATTERN_CYCLE_ORDER[0]
        print_status(state)
        return True
    if key == "a":
        if state.pattern in PATTERN_CYCLE_ORDER:
            idx = PATTERN_CYCLE_ORDER.index(state.pattern)
            state.pattern = PATTERN_CYCLE_ORDER[(idx - 1) % len(PATTERN_CYCLE_ORDER)]
        elif not state.emergency_only:
            state.pattern = PATTERN_CYCLE_ORDER[-1]
        print_status(state)
        return True

    # w/s: brightness
    if key == "w":
        state.brightness = clamp_brightness(state.brightness + 16)
        set_strip_brightness(state.brightness)
        print_status(state)
        return True
    if key == "s":
        state.brightness = clamp_brightness(state.brightness - 16)
        set_strip_brightness(state.brightness)
        print_status(state)
        return True

    # +/= speed up, - speed down
    if key in {"+", "="}:
        keys = list(SPEED_LABELS.keys())
        idx = keys.index(state.speed) if state.speed in keys else 4
        state.speed = keys[min(idx + 1, len(keys) - 1)]
        print_status(state)
        return True
    if key == "-":
        keys = list(SPEED_LABELS.keys())
        idx = keys.index(state.speed) if state.speed in keys else 4
        state.speed = keys[max(idx - 1, 0)]
        print_status(state)
        return True

    # Direct pattern selection by digit key
    if key in allowed:
        state.pattern = key
        print_status(state)
        return True
    if key == "c":
        if state.pattern == "1":
            state.chase_color = cycle_choice(state.chase_color, CHASE_COLORS)
        elif state.pattern in {"2", "4"}:
            state.random_palette = cycle_choice(state.random_palette, RANDOM_PALETTES)
        elif state.pattern == "3":
            state.bounce_color = cycle_choice(state.bounce_color, BOUNCE_COLORS)
        elif state.pattern in {"5", "6", "8", "9", "10", "11", "12"}:
            state.effect_color = cycle_choice(state.effect_color, EFFECT_COLORS)
        print_status(state)
        return True
    if key == "n":
        print_named_colors()
        print_status(state)
        return True
    if key == "h":
        print(SHORTCUTS_TEXT)
        print_status(state)
        return True
    if key in {"m", "M"}:
        prompt_support_ticket_manager(fd, old_settings, state)
        print_status(state)
        return True
    if key == "\x0f":
        prompt_nohup_tools(fd, old_settings, state, options)
        print_status(state)
        return True
    if key in {"o", "O"}:
        cmd = build_nohup_command(state, options)
        print_nohup_command_block(cmd)
        return True
    if key == "q":
        return False
    return True


def run_pattern_step(state: AppState) -> None:
    if state.pattern == "1":
        pattern_step_chase(state)
    elif state.pattern in {"2", "4"}:
        pattern_step_random(state)
    elif state.pattern == "3":
        pattern_step_bounce(state)
    elif state.pattern == "-1":
        pattern_step_emergency(state)
    elif state.pattern == "5":
        pattern_step_comet(state)
    elif state.pattern == "6":
        pattern_step_theater_chase(state)
    elif state.pattern == "7":
        pattern_step_rainbow_sweep(state)
    elif state.pattern == "8":
        pattern_step_pulse(state)
    elif state.pattern == "9":
        pattern_step_sparkle(state)
    elif state.pattern == "10":
        pattern_step_fire(state)
    elif state.pattern == "11":
        pattern_step_meteor(state)
    elif state.pattern == "12":
        pattern_step_twinkle(state)
    else:
        pattern_step_chase(state)


def run_loop(state: AppState, options: RunOptions) -> None:
    if isinstance(get_strip(), VirtualStrip):
        print("Test mode: realtime ASCII overlay (press q to quit).")
    else:
        print(SHORTCUTS_TEXT)
    print_status(state)

    if options.start_delay_seconds > 0:
        time.sleep(max(0.0, options.start_delay_seconds))

    frame_count = 0
    start_time = time.monotonic()

    if not sys.stdin.isatty():
        while True:
            apply_pi_input_response(state)
            run_pattern_step(state)

            frame_count += 1
            if options.frames > 0 and frame_count >= options.frames:
                break
            if options.duration_seconds > 0 and (time.monotonic() - start_time) >= options.duration_seconds:
                break
            time.sleep(get_delay(state))
        return

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        tty.setcbreak(fd)
        while True:
            key = maybe_read_key()
            if key is not None and not handle_key(state, options, key, fd, old_settings):
                break

            apply_pi_input_response(state)
            run_pattern_step(state)

            frame_count += 1
            if options.frames > 0 and frame_count >= options.frames:
                break
            if options.duration_seconds > 0 and (time.monotonic() - start_time) >= options.duration_seconds:
                break

            time.sleep(get_delay(state))
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def ask_choice(prompt: str, default: str, options: dict[str, Any]) -> str:
    keys_list = ", ".join(options.keys())
    value = input(f"{prompt} ({keys_list}, default {default}): ").strip() or default
    if value not in options:
        return default
    return value


def ask_int(prompt: str, default: int, minimum: int = 0, maximum: int = 255) -> int:
    raw = input(f"{prompt} (default {default}): ").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


def ask_float(prompt: str, default: float, minimum: float = 0.0) -> float:
    raw = input(f"{prompt} (default {default}): ").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(minimum, value)


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    suffix = "Y/n" if default else "y/N"
    raw = input(f"{prompt} [{suffix}]: ").strip().lower()
    if not raw:
        return default
    return raw in {"y", "yes", "1", "true"}


def load_headless_config(path: str) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_headless_config(path: str, state: AppState, options: RunOptions, test_mode: bool) -> None:
    payload: dict[str, Any] = {
        "test": bool(test_mode),
        "pattern": state.pattern,
        "speed": state.speed,
        "chase_color": state.chase_color,
        "random_palette": state.random_palette,
        "bounce_color": state.bounce_color,
        "brightness": state.brightness,
        "max_brightness": state.max_brightness,
        "emergency_only": state.emergency_only,
        "custom_color": state.custom_color,
        "input": {
            "mode": state.input_mode,
            "pin": state.input_pin,
            "analog_path": state.analog_path,
            "analog_max": state.analog_max,
        },
        "run": {
            "frames": options.frames,
            "duration_seconds": options.duration_seconds,
            "start_delay_seconds": options.start_delay_seconds,
        },
    }
    Path(path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def state_options_from_headless_data(data: dict[str, Any]) -> tuple[AppState, RunOptions, bool]:
    raw_input_data = data.get("input")
    raw_run_data = data.get("run")
    input_data = cast(dict[str, Any], raw_input_data) if isinstance(raw_input_data, dict) else {}
    run_data = cast(dict[str, Any], raw_run_data) if isinstance(raw_run_data, dict) else {}

    state = AppState(
        pattern=as_str(data.get("pattern"), "1"),
        speed=as_str(data.get("speed"), "5"),
        chase_color=as_str(data.get("chase_color"), "1"),
        random_palette=as_str(data.get("random_palette"), "1"),
        bounce_color=as_str(data.get("bounce_color"), "1"),
        brightness=clamp_brightness(as_int(data.get("brightness"), LED_BRIGHTNESS)),
        max_brightness=clamp_brightness(as_int(data.get("max_brightness"), LED_BRIGHTNESS)),
        input_mode=as_str(input_data.get("mode"), "off"),
        input_pin=as_int(input_data.get("pin"), 23),
        analog_path=as_str(input_data.get("analog_path"), "/sys/bus/iio/devices/iio:device0/in_voltage0_raw"),
        analog_max=max(1, as_int(input_data.get("analog_max"), 4095)),
        emergency_only=as_bool(data.get("emergency_only"), False),
        custom_color=as_int(data.get("custom_color"), 0),
        effect_color=as_str(data.get("effect_color"), "9"),
    )
    options = RunOptions(
        frames=max(0, as_int(run_data.get("frames"), 0)),
        duration_seconds=max(0.0, as_float(run_data.get("duration_seconds"), 0.0)),
        start_delay_seconds=max(0.0, as_float(run_data.get("start_delay_seconds"), 0.0)),
    )
    test_mode = as_bool(data.get("test"), False)

    if state.pattern not in PATTERN_NAMES:
        state.pattern = "1"
    if state.speed not in SPEED_LABELS:
        state.speed = "5"
    if state.chase_color not in CHASE_COLORS:
        state.chase_color = "1"
    if state.random_palette not in RANDOM_PALETTES:
        state.random_palette = "1"
    if state.bounce_color not in BOUNCE_COLORS:
        state.bounce_color = "1"
    if state.effect_color not in EFFECT_COLORS:
        state.effect_color = "9"
    if state.input_mode not in {"off", "digital", "analog"}:
        state.input_mode = "off"

    normalize_pattern_for_mode(state)

    return state, options, test_mode


def interactive_setup() -> tuple[AppState, RunOptions, bool, bool, str]:
    use_headless = ask_yes_no("Headless config mode (load JSON settings)?", default=False)
    headless_path = HEADLESS_DEFAULT_CONFIG
    if use_headless:
        # Discover JSON files in the `headless/` directory to present as
        # selectable options (a-d), with option 'e' to enter a custom path.
        headless_dir = Path("headless")
        json_files = []
        if headless_dir.is_dir():
            json_files = sorted([p.name for p in headless_dir.glob('headless_*.json')])

        # Exclude the default config from the selectable options so all 4 pattern
        # configs are shown; the default remains accessible via custom path 'e'.
        default_name = Path(HEADLESS_DEFAULT_CONFIG).name
        if default_name in json_files:
            json_files.remove(default_name)

        options_list = json_files[:4]
        print("Select a headless JSON config:")
        letters = ['a', 'b', 'c', 'd']
        for i, fname in enumerate(options_list):
            print(f"{letters[i]}. {fname}")
        print("e. Enter custom path")

        choice = input("Choose (a-e, default a): ").strip().lower() or 'a'
        headless_path = HEADLESS_DEFAULT_CONFIG
        if choice in letters:
            idx = letters.index(choice)
            if idx < len(options_list):
                headless_path = str(headless_dir / options_list[idx])
            else:
                headless_path = HEADLESS_DEFAULT_CONFIG
        elif choice == 'e':
            entered = input(f"Headless JSON path (default {HEADLESS_DEFAULT_CONFIG}): ").strip()
            headless_path = entered or HEADLESS_DEFAULT_CONFIG

        data = load_headless_config(headless_path)
        state, options, test_mode = state_options_from_headless_data(data)
        return state, options, test_mode, True, headless_path

    print("Select a pattern:")
    for key, name in sorted(PATTERN_NAMES.items(), key=lambda kv: int(kv[0])):
        print(f"  {key:>3}. {name}")

    pattern = ask_choice("Enter pattern", "1", PATTERN_NAMES)
    speed = ask_choice("Enter speed (0=Constant, 1..9=Level)", "5", SPEED_LABELS)

    print("Chase color: 1=Orange  2=Green  3=Blue  4=Rainbow  5=Custom")
    chase_color = ask_choice("Chase color", "1", CHASE_COLORS)
    if chase_color == "5":
        print_named_colors()
        raw_cc = input("Custom color (name / #RRGGBB / r,g,b, default gold): ").strip() or "gold"
        try:
            custom_color_val = parse_custom_color(raw_cc)
        except ValueError as exc:
            print(exc)
            custom_color_val = NAMED_COLORS["gold"]
    else:
        custom_color_val = 0

    print("Random palette: " + "  ".join(f"{k}={v[0]}" for k, v in RANDOM_PALETTES.items()))
    random_palette = ask_choice("Random palette", "1", RANDOM_PALETTES)

    print("Bounce color: 1=Blue  2=Purple  3=White  4=Rainbow  5=Custom")
    bounce_color = ask_choice("Bounce color", "1", BOUNCE_COLORS)
    if bounce_color == "5" and custom_color_val == 0:
        print_named_colors()
        raw_cc = input("Custom color (name / #RRGGBB / r,g,b, default gold): ").strip() or "gold"
        try:
            custom_color_val = parse_custom_color(raw_cc)
        except ValueError as exc:
            print(exc)
            custom_color_val = NAMED_COLORS["gold"]

    # Custom color for patterns that aren't chase/bounce but support it
    if custom_color_val == 0 and pattern not in {"1", "2", "3", "4", "-1", "7"}:
        use_custom = ask_yes_no("Set a custom color for this pattern?", default=False)
        if use_custom:
            print_named_colors()
            raw_cc = input("Custom color (name / #RRGGBB / r,g,b, default gold): ").strip() or "gold"
            try:
                custom_color_val = parse_custom_color(raw_cc)
            except ValueError as exc:
                print(exc)
                custom_color_val = NAMED_COLORS["gold"]

    max_brightness = ask_int("Maximum brightness (0-255)", LED_BRIGHTNESS, 0, 255)
    brightness = ask_int("Startup brightness (0-255)", max_brightness, 0, 255)
    input_mode = ask_choice("Pi input mode (off/digital/analog)", "off", {"off": "Off", "digital": "Digital", "analog": "Analog"})
    input_pin = ask_int("Digital GPIO BCM pin", 23, 0, 40)
    analog_path = input("Analog input sysfs path (blank for default): ").strip() or "/sys/bus/iio/devices/iio:device0/in_voltage0_raw"
    analog_max = ask_int("Analog max value", 4095, 1, 999999)
    emergency_only = ask_yes_no("Emergency-only mode (panic SOS only)?", default=False)
    test_mode = ask_yes_no("Run in ASCII --test mode?", default=False)

    frames = ask_int("Timer: frames (0=continuous)", 0, 0, 10_000_000)
    duration_seconds = ask_float("Timer: duration seconds (0=disabled)", 0.0, 0.0)
    start_delay_seconds = ask_float("Timer: start delay seconds", 0.0, 0.0)

    state = AppState(
        pattern=pattern,
        speed=speed,
        chase_color=chase_color,
        random_palette=random_palette,
        bounce_color=bounce_color,
        max_brightness=max_brightness,
        brightness=min(brightness, max_brightness),
        input_mode=input_mode,
        input_pin=input_pin,
        analog_path=analog_path,
        analog_max=analog_max,
        emergency_only=emergency_only,
        custom_color=custom_color_val,
        effect_color="9",
    )
    normalize_pattern_for_mode(state)
    options = RunOptions(
        frames=frames,
        duration_seconds=duration_seconds,
        start_delay_seconds=start_delay_seconds,
    )

    return state, options, test_mode, False, headless_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="WS281X LED pattern runner with live keyboard switching.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Switch options:\n"
            "  --pattern {-1,1..12}       Startup pattern (-1=SOS, 1-12 see list below)\n"
            "  --SOS, --sos               Shortcut to emergency SOS mode\n"
            "  --speed {0,1,2,3,4,5,6,7,8,9}  Startup speed (0=Constant, 1..9=levels)\n"
            "  --chase-color {1,2,3,4,5}  Chase color option (5=Custom)\n"
            "  --random-palette {1..8}    Random palette option\n"
            "  --bounce-color {1,2,3,4,5} Bounce color option (5=Custom)\n"
            "  --custom-color COLOR       Custom color: name, #RRGGBB, or r,g,b\n"
            "                             (use --show-colors for a list of names)\n"
            "  --brightness N             Startup brightness 0..255\n"
            "  --max-brightness N         Brightness ceiling 0..255\n"
            "  --pi-input-mode MODE       off|digital|analog\n"
            "  --pi-input-pin N           GPIO pin for digital input (BCM)\n"
            "  --analog-path PATH         sysfs path for analog input\n"
            "  --analog-max N             Analog max value for scaling\n"
            "  --duration-seconds SEC     Stop after SEC (0 disables)\n"
            "  --start-delay-seconds SEC  Delay before animation starts\n"
            "  --headless                 Load settings from separate JSON\n"
            "  --headless-config FILE     JSON settings path\n"
            "  --emergency-only           Panic flash SOS only mode\n"
            "  --support-export [IDS]     Export task(s) to Copilot queue (IDs comma-separated, blank=open)\n"
            "  --test                     Safe ASCII simulation (no hardware)\n"
            "  --frames N                 Stop after N frames (useful for tests)\n"
            "  --show-colors              Print named color list and exit\n"
            "\n"
            "Patterns: -1=Emergency SOS, 1=Chase, 2=Random, 3=Bounce, 4=Random,\n"
            "          5=Comet, 6=Theater Chase, 7=Rainbow Sweep, 8=Pulse, 9=Sparkle,\n"
            "          10=Fire Flame, 11=Meteor Shower, 12=Twinkle Stars\n"
            "\n"
            "Shortcuts during run:\n"
            "  ←/→ cycle pattern, ↑/↓ brightness, +/= speed up, - speed down,\n"
            "  c color option, n named colors, m/M support manager, o/O nohup, Ctrl+O nohup tools, h help, q quit\n"
            "  SOS pattern is -1 (set via --SOS, --pattern -1, interactive prompt, or headless JSON).\n"
            "\n"
            "Defined output example:\n"
            f"{OUTPUT_EXAMPLE_TEXT}"
        ),
    )
    parser.add_argument("--pattern", choices=["-1", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"], help="Startup pattern")
    parser.add_argument("--SOS", "--sos", dest="sos", action="store_true", help="Shortcut for emergency SOS mode")
    parser.add_argument("--speed", choices=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"], help="Startup speed")
    parser.add_argument("--chase-color", choices=["1", "2", "3", "4", "5"], help="Chase color option (5=Custom)")
    parser.add_argument("--random-palette", choices=["1", "2", "3", "4", "5", "6", "7", "8"], help="Random palette option")
    parser.add_argument("--bounce-color", choices=["1", "2", "3", "4", "5"], help="Bounce color option (5=Custom)")
    parser.add_argument("--custom-color", dest="custom_color", default=None, help="Custom color: name, #RRGGBB, or r,g,b")
    parser.add_argument("--brightness", type=int, help="Startup brightness (0-255)")
    parser.add_argument("--max-brightness", type=int, help="Maximum brightness (0-255)")
    parser.add_argument("--pi-input-mode", choices=["off", "digital", "analog"], help="Pi input response mode")
    parser.add_argument("--pi-input-pin", type=int, help="GPIO BCM pin for digital input")
    parser.add_argument("--analog-path", help="Analog input path, e.g. /sys/bus/iio/.../in_voltage0_raw")
    parser.add_argument("--analog-max", type=int, help="Maximum analog reading for scaling")
    parser.add_argument("--test", action="store_true", help="Run safe ASCII simulation mode")
    parser.add_argument("--frames", type=int, default=None, help="Stop after N frames (0 runs continuously)")
    parser.add_argument("--duration-seconds", type=float, default=None, help="Stop after duration in seconds")
    parser.add_argument("--start-delay-seconds", type=float, default=None, help="Delay before starting animation")
    parser.add_argument("--headless", action="store_true", help="Load settings from JSON and run without prompts")
    parser.add_argument("--headless-config", default=HEADLESS_DEFAULT_CONFIG, help="Path to headless JSON settings file")
    parser.add_argument("--emergency-only", action="store_true", help="Run panic-flash SOS mode only")
    parser.add_argument(
        "--support-export",
        nargs="?",
        const="",
        help="Send support task IDs to Copilot queue markdown (blank sends all open tasks)",
    )
    parser.add_argument(
        "--show-colors",
        action="store_true",
        help="Print named color list and exit",
    )
    parser.add_argument(
        "--show-shortcuts",
        action="store_true",
        help="Print runtime shortcuts and exit",
    )
    parser.add_argument(
        "--export-headless",
        nargs="?",
        const="",
        help="Export current settings to headless JSON file (optionally specify name) and exit",
    )
    return parser.parse_args()


def has_non_interactive_cli_options(args: argparse.Namespace) -> bool:
    return any(
        [
            args.pattern is not None,
            args.speed is not None,
            args.chase_color is not None,
            args.random_palette is not None,
            args.bounce_color is not None,
            args.custom_color is not None,
            args.brightness is not None,
            args.max_brightness is not None,
            args.pi_input_mode is not None,
            args.pi_input_pin is not None,
            args.analog_path is not None,
            args.analog_max is not None,
            args.frames is not None,
            args.duration_seconds is not None,
            args.start_delay_seconds is not None,
            args.emergency_only,
            args.sos,
        ]
    )


def _resolve_custom_color(args: argparse.Namespace) -> int:
    if args.custom_color is None:
        return 0
    try:
        return parse_custom_color(args.custom_color)
    except ValueError as exc:
        print(f"[WARN] {exc}")
        return 0


def state_from_args(args: argparse.Namespace) -> tuple[AppState, RunOptions]:
    state = AppState(
        pattern=args.pattern or "1",
        speed=args.speed or "5",
        chase_color=args.chase_color or "1",
        random_palette=args.random_palette or "1",
        bounce_color=args.bounce_color or "1",
        brightness=clamp_brightness(args.brightness if args.brightness is not None else LED_BRIGHTNESS),
        max_brightness=clamp_brightness(args.max_brightness if args.max_brightness is not None else LED_BRIGHTNESS),
        input_mode=args.pi_input_mode or "off",
        input_pin=args.pi_input_pin if args.pi_input_pin is not None else 23,
        analog_path=args.analog_path or "/sys/bus/iio/devices/iio:device0/in_voltage0_raw",
        analog_max=max(1, args.analog_max if args.analog_max is not None else 4095),
        emergency_only=bool(args.emergency_only or args.sos),
        custom_color=_resolve_custom_color(args),
        effect_color="9",
    )
    state.brightness = min(state.brightness, state.max_brightness)
    if args.sos:
        state.pattern = "-1"
    normalize_pattern_for_mode(state)
    options = RunOptions(
        frames=max(0, args.frames if args.frames is not None else 0),
        duration_seconds=max(0.0, args.duration_seconds if args.duration_seconds is not None else 0.0),
        start_delay_seconds=max(0.0, args.start_delay_seconds if args.start_delay_seconds is not None else 0.0),
    )
    return state, options


def apply_cli_overrides(state: AppState, options: RunOptions, args: argparse.Namespace) -> tuple[AppState, RunOptions]:
    if args.pattern is not None:
        state.pattern = args.pattern
    if args.speed is not None:
        state.speed = args.speed
    if args.chase_color is not None:
        state.chase_color = args.chase_color
    if args.random_palette is not None:
        state.random_palette = args.random_palette
    if args.bounce_color is not None:
        state.bounce_color = args.bounce_color
    if args.max_brightness is not None:
        state.max_brightness = clamp_brightness(args.max_brightness)
    if args.brightness is not None:
        state.brightness = clamp_brightness(args.brightness)
    state.brightness = min(state.brightness, state.max_brightness)
    if args.pi_input_mode is not None:
        state.input_mode = args.pi_input_mode
    if args.pi_input_pin is not None:
        state.input_pin = args.pi_input_pin
    if args.analog_path is not None:
        state.analog_path = args.analog_path
    if args.analog_max is not None:
        state.analog_max = max(1, args.analog_max)
    if args.frames is not None:
        options.frames = max(0, args.frames)
    if args.duration_seconds is not None:
        options.duration_seconds = max(0.0, args.duration_seconds)
    if args.start_delay_seconds is not None:
        options.start_delay_seconds = max(0.0, args.start_delay_seconds)
    if args.emergency_only:
        state.emergency_only = True
    if args.sos:
        state.pattern = "-1"
        state.emergency_only = True
    if args.custom_color is not None:
        state.custom_color = _resolve_custom_color(args)
    normalize_pattern_for_mode(state)
    return state, options


def main() -> None:
    args = parse_args()

    if args.show_shortcuts:
        print(SHORTCUTS_TEXT)
        return

    if args.show_colors:
        print_named_colors()
        return

    if args.support_export is not None:
        raw_ids = args.support_export or ""
        store_path, queue_path, sent_count = send_tasks_to_copilot(raw_ids)
        if sent_count > 0:
            print(f"Sent {sent_count} task(s) to Copilot queue: {queue_path}")
            print(f"Task store updated: {store_path}")
        else:
            print("No matching tasks to send.")
            print(f"Task store: {store_path}")
        return

    state: AppState
    options: RunOptions
    test_mode = bool(args.test)
    used_headless = bool(args.headless)
    headless_path = args.headless_config

    if args.headless:
        data = load_headless_config(args.headless_config)
        state, options, config_test_mode = state_options_from_headless_data(data)
        test_mode = test_mode or config_test_mode
        state, options = apply_cli_overrides(state, options, args)
    elif not has_non_interactive_cli_options(args):
        state, options, interactive_test_mode, used_headless, headless_path = interactive_setup()
        test_mode = test_mode or interactive_test_mode
    else:
        state, options = state_from_args(args)

    # Export current settings to headless JSON (and exit) if requested.
    if args.export_headless is not None:
        headless_dir = Path("headless")
        headless_dir.mkdir(parents=True, exist_ok=True)

        specified = args.export_headless or ""
        if specified:
            out_path = Path(specified)
            if not out_path.suffix:
                out_path = out_path.with_suffix('.json')
            if not out_path.is_absolute():
                out_path = headless_dir / out_path
        else:
            # Default filename: "<pattern>_<name>.json"
            patt_label = PATTERN_NAMES.get(state.pattern, state.pattern).lower().replace(" ", "_")
            filename = f"{state.pattern}_{patt_label}.json"
            out_path = headless_dir / filename

        save_headless_config(str(out_path), state, options, test_mode)
        print(f"Exported headless config to: {out_path}")
        return

    if test_mode:
        print("Running in --test ASCII mode (hardware disabled).")
        init_virtual_strip()
    else:
        init_strip()
    get_strip().begin()
    clear_strip(show_now=not test_mode)
    apply_brightness_from_state(state)

    if used_headless and not args.headless:
        save_headless_config(headless_path, state, options, test_mode)

    run_loop(state, options)


def _shutdown_handler(signum: int, frame: object) -> None:
    """Convert SIGTERM / SIGHUP into SystemExit so the finally block runs."""
    raise SystemExit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _shutdown_handler)
    signal.signal(signal.SIGHUP, _shutdown_handler)

    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        clear_strip(show_now=not isinstance(strip, VirtualStrip))
    if isinstance(strip, VirtualStrip):
        strip.finish()
