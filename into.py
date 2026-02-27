import argparse
import json
import random
import select
import shutil
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
    "1": "Chase",
    "2": "Random",
    "3": "Bounce",
    "4": "Emergency SOS",
}


def available_patterns(emergency_only: bool) -> dict[str, str]:
    if emergency_only:
        return {"4": PATTERN_NAMES["4"]}
    return {k: v for k, v in PATTERN_NAMES.items() if k != "4"}


def normalize_pattern_for_mode(state: "AppState") -> None:
    if state.emergency_only:
        state.pattern = "4"
        return
    if state.pattern == "4":
        state.pattern = "1"

SPEED_LABELS: dict[str, str] = {
    "1": "Slow",
    "2": "Medium",
    "3": "Fast",
}

SPEED_MAP: dict[str, dict[str, float]] = {
    "1": {"1": 0.08, "2": 0.03, "3": 0.01},
    "2": {"1": 0.30, "2": 0.12, "3": 0.05},
    "3": {"1": 0.06, "2": 0.02, "3": 0.008},
}

CHASE_COLORS: dict[str, tuple[str, int]] = {
    "1": ("Orange", Color(255, 140, 0)),
    "2": ("Green", Color(0, 255, 0)),
    "3": ("Blue", Color(0, 0, 255)),
    "4": ("Rainbow", 0),
}

RANDOM_PALETTES: dict[str, tuple[str, list[int] | None]] = {
    "1": ("Any RGB", None),
    "2": ("Warm", [Color(255, 0, 0), Color(255, 120, 0), Color(255, 255, 0)]),
    "3": ("Cool", [Color(0, 255, 255), Color(0, 0, 255), Color(180, 0, 255)]),
}

BOUNCE_COLORS: dict[str, tuple[str, int]] = {
    "1": ("Blue", Color(0, 0, 255)),
    "2": ("Purple", Color(180, 0, 255)),
    "3": ("White", Color(255, 255, 255)),
    "4": ("Rainbow", 0),
}

SHORTCUTS_TEXT = """
Runtime shortcuts:
    1 / 2 / 3 / 4 Switch pattern (1=Chase, 2=Random, 3=Bounce, 4=SOS)
        p           Cycle pattern (Chase -> Random -> Bounce -> SOS)
  s           Cycle speed (Slow -> Medium -> Fast)
  c           Cycle color option for current pattern
    + / -       Brightness up/down
    Ctrl+O      Print nohup command for current settings
  h           Show this shortcuts help again
  q           Quit
  Ctrl+C      Quit
""".strip()

OUTPUT_EXAMPLE_TEXT = """
Runtime shortcuts:
    1 / 2 / 3   Switch pattern (1=Chase, 2=Random, 3=Bounce)
        p           Cycle pattern (Chase -> Random -> Bounce)
    s           Cycle speed (Slow -> Medium -> Fast)
    c           Cycle color option for current pattern
    h           Show this shortcuts help again
    q           Quit
    Ctrl+C      Quit
Pattern: Chase | Speed: Fast | Color: Rainbow
Pattern: Chase | Speed: Fast | Color: Rainbow
Pattern: Random | Speed: Fast | Palette: Any RGB
Pattern: Bounce | Speed: Fast | Color: Blue
Pattern: Chase | Speed: Fast | Color: Rainbow
Pattern: Random | Speed: Fast | Palette: Any RGB
Pattern: Bounce | Speed: Fast | Color: Blue
Pattern: Chase | Speed: Fast | Color: Rainbow
Pattern: Bounce | Speed: Fast | Color: Blue
Pattern: Random | Speed: Fast | Palette: Any RGB
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
    rainbow_offset: int = 0


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
            "rpi_ws281x not installed. Create a virtualenv and `pip install -r requirements.txt`,\n"
            "or run in test mode with `--test` to use the ASCII virtual strip."
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


def pattern_step_chase(state: AppState) -> None:
    active_strip = get_strip()
    clear_strip(show_now=False)
    if state.chase_color == "4":
        color = wheel((state.rainbow_offset + state.chase_position * 8) & 255)
        state.rainbow_offset = (state.rainbow_offset + 3) & 255
    else:
        color = CHASE_COLORS[state.chase_color][1]
    active_strip.setPixelColor(state.chase_position, color)
    active_strip.show()
    state.chase_position = (state.chase_position + 1) % LED_COUNT


def pattern_step_random(state: AppState) -> None:
    active_strip = get_strip()
    palette = RANDOM_PALETTES[state.random_palette][1]
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


def pattern_step_bounce(state: AppState) -> None:
    active_strip = get_strip()
    clear_strip(show_now=False)
    if state.bounce_color == "4":
        color = wheel((state.rainbow_offset + state.bounce_position * 8) & 255)
        state.rainbow_offset = (state.rainbow_offset + 3) & 255
    else:
        color = BOUNCE_COLORS[state.bounce_color][1]
    active_strip.setPixelColor(state.bounce_position, color)
    active_strip.show()

    if state.bounce_position == LED_COUNT - 1:
        state.bounce_direction = -1
    elif state.bounce_position == 0:
        state.bounce_direction = 1
    state.bounce_position += state.bounce_direction


def pattern_step_emergency(state: AppState) -> None:
    active_strip = get_strip()
    step_on = EMERGENCY_SOS_STEPS[state.emergency_step] > 0
    color = EMERGENCY_COLORS[state.emergency_color_index][1]

    for i in range(LED_COUNT):
        active_strip.setPixelColor(i, color if step_on else Color(0, 0, 0))
    active_strip.show()

    state.emergency_step += 1
    if state.emergency_step >= len(EMERGENCY_SOS_STEPS):
        state.emergency_step = 0
        state.emergency_color_index = (state.emergency_color_index + 1) % len(EMERGENCY_COLORS)


def get_delay(state: AppState) -> float:
    if state.pattern == "4":
        return EMERGENCY_DELAY_SECONDS
    return SPEED_MAP[state.pattern][state.speed]


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
    pattern_name = PATTERN_NAMES[state.pattern]
    speed_name = SPEED_LABELS[state.speed]
    if state.pattern == "1":
        color_name = CHASE_COLORS[state.chase_color][0]
        detail = f"Color: {color_name}"
    elif state.pattern == "2":
        palette_name = RANDOM_PALETTES[state.random_palette][0]
        detail = f"Palette: {palette_name}"
    elif state.pattern == "3":
        color_name = BOUNCE_COLORS[state.bounce_color][0]
        detail = f"Color: {color_name}"
    else:
        color_name = EMERGENCY_COLORS[state.emergency_color_index][0]
        detail = f"Color: {color_name} | Panic SOS"

    brightness_pct = int((max(0, state.brightness) / max(1, state.max_brightness)) * 100)
    print(f"Pattern: {pattern_name} | Speed: {speed_name} | Brightness: {state.brightness} ({brightness_pct}%) | {detail}")


def maybe_read_key() -> str | None:
    ready, _, _ = select.select([sys.stdin], [], [], 0)
    if not ready:
        return None
    return sys.stdin.read(1)


def build_nohup_command(state: AppState, options: RunOptions) -> str:
    command: list[str] = [
        "nohup",
        sys.executable,
        "into.py",
        "--pattern",
        state.pattern,
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

    if options.frames > 0:
        command.extend(["--frames", str(options.frames)])
    if options.duration_seconds > 0:
        command.extend(["--duration-seconds", str(options.duration_seconds)])
    if options.start_delay_seconds > 0:
        command.extend(["--start-delay-seconds", str(options.start_delay_seconds)])
    if state.emergency_only:
        command.append("--emergency-only")

    command.extend([">", "runtime_live.log", "2>&1", "&", "echo", "$!", ">", "runtime_live.pid"])
    return " ".join(command)


def handle_key(state: AppState, options: RunOptions, key: str) -> bool:
    allowed = available_patterns(state.emergency_only)

    if key in allowed:
        state.pattern = key
        print_status(state)
        return True
    if key == "p":
        state.pattern = cycle_choice(state.pattern, allowed)
        print_status(state)
        return True
    if key == "s":
        state.speed = cycle_choice(state.speed, SPEED_LABELS)
        print_status(state)
        return True
    if key == "c":
        if state.pattern == "1":
            state.chase_color = cycle_choice(state.chase_color, CHASE_COLORS)
        elif state.pattern == "2":
            state.random_palette = cycle_choice(state.random_palette, RANDOM_PALETTES)
        elif state.pattern == "3":
            state.bounce_color = cycle_choice(state.bounce_color, BOUNCE_COLORS)
        print_status(state)
        return True
    if key == "+":
        state.brightness = clamp_brightness(state.brightness + 16)
        set_strip_brightness(state.brightness)
        print_status(state)
        return True
    if key == "-":
        state.brightness = clamp_brightness(state.brightness - 16)
        set_strip_brightness(state.brightness)
        print_status(state)
        return True
    if key == "h":
        print(SHORTCUTS_TEXT)
        print_status(state)
        return True
    if key == "\x0f":
        print("nohup launch command:")
        print(build_nohup_command(state, options))
        return True
    if key == "q":
        return False
    return True


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
            if state.pattern == "1":
                pattern_step_chase(state)
            elif state.pattern == "2":
                pattern_step_random(state)
            elif state.pattern == "3":
                pattern_step_bounce(state)
            else:
                pattern_step_emergency(state)

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
            if key is not None and not handle_key(state, options, key):
                break

            apply_pi_input_response(state)
            if state.pattern == "1":
                pattern_step_chase(state)
            elif state.pattern == "2":
                pattern_step_random(state)
            elif state.pattern == "3":
                pattern_step_bounce(state)
            else:
                pattern_step_emergency(state)

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
        speed=as_str(data.get("speed"), "2"),
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
        state.speed = "2"
    if state.chase_color not in CHASE_COLORS:
        state.chase_color = "1"
    if state.random_palette not in RANDOM_PALETTES:
        state.random_palette = "1"
    if state.bounce_color not in BOUNCE_COLORS:
        state.bounce_color = "1"
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
            json_files = sorted([p.name for p in headless_dir.glob('*.json')])

        # Prefer to include the default config near the front if it's in headless/
        default_name = Path(HEADLESS_DEFAULT_CONFIG).name
        if default_name in json_files:
            json_files.remove(default_name)
            json_files.insert(0, default_name)

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
                headless_path = options_list[idx]
            else:
                headless_path = HEADLESS_DEFAULT_CONFIG
        elif choice == 'e':
            entered = input(f"Headless JSON path (default {HEADLESS_DEFAULT_CONFIG}): ").strip()
            headless_path = entered or HEADLESS_DEFAULT_CONFIG

        data = load_headless_config(headless_path)
        state, options, test_mode = state_options_from_headless_data(data)
        return state, options, test_mode, True, headless_path

    print("Select a pattern:")
    print("1. Chase")
    print("2. Random")
    print("3. Bounce")
    print("4. Emergency SOS")

    pattern = ask_choice("Enter pattern", "1", PATTERN_NAMES)
    speed = ask_choice("Enter speed (1=Slow, 2=Medium, 3=Fast)", "2", SPEED_LABELS)
    chase_color = ask_choice("Chase color (1=Orange, 2=Green, 3=Blue, 4=Rainbow)", "1", CHASE_COLORS)
    random_palette = ask_choice("Random mode (1=Any RGB, 2=Warm, 3=Cool)", "1", RANDOM_PALETTES)
    bounce_color = ask_choice("Bounce color (1=Blue, 2=Purple, 3=White, 4=Rainbow)", "1", BOUNCE_COLORS)
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
            "  --pattern {1,2,3,4}        Startup pattern\n"
            "  --speed {1,2,3}            Startup speed (1=Slow, 2=Medium, 3=Fast)\n"
            "  --chase-color {1,2,3,4}    Chase color option\n"
            "  --random-palette {1,2,3}   Random palette option\n"
            "  --bounce-color {1,2,3,4}   Bounce color option\n"
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
            "  --test                     Safe ASCII simulation (no hardware)\n"
            "  --frames N                 Stop after N frames (useful for tests)\n"
            "\n"
            "Shortcuts during run:\n"
            "  1/2/3/4 switch pattern, p cycle pattern, s speed, c color option, +/- brightness, h help, q quit\n"
            "\n"
            "Defined output example:\n"
            f"{OUTPUT_EXAMPLE_TEXT}"
        ),
    )
    parser.add_argument("--pattern", choices=["1", "2", "3", "4"], help="Startup pattern")
    parser.add_argument("--speed", choices=["1", "2", "3"], help="Startup speed")
    parser.add_argument("--chase-color", choices=["1", "2", "3", "4"], help="Chase color option")
    parser.add_argument("--random-palette", choices=["1", "2", "3"], help="Random palette option")
    parser.add_argument("--bounce-color", choices=["1", "2", "3", "4"], help="Bounce color option")
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
            args.brightness is not None,
            args.max_brightness is not None,
            args.pi_input_mode is not None,
            args.pi_input_pin is not None,
            args.analog_path is not None,
            args.analog_max is not None,
            args.test,
            args.frames is not None,
            args.duration_seconds is not None,
            args.start_delay_seconds is not None,
            args.emergency_only,
        ]
    )


def state_from_args(args: argparse.Namespace) -> tuple[AppState, RunOptions]:
    state = AppState(
        pattern=args.pattern or "1",
        speed=args.speed or "2",
        chase_color=args.chase_color or "1",
        random_palette=args.random_palette or "1",
        bounce_color=args.bounce_color or "1",
        brightness=clamp_brightness(args.brightness if args.brightness is not None else LED_BRIGHTNESS),
        max_brightness=clamp_brightness(args.max_brightness if args.max_brightness is not None else LED_BRIGHTNESS),
        input_mode=args.pi_input_mode or "off",
        input_pin=args.pi_input_pin if args.pi_input_pin is not None else 23,
        analog_path=args.analog_path or "/sys/bus/iio/devices/iio:device0/in_voltage0_raw",
        analog_max=max(1, args.analog_max if args.analog_max is not None else 4095),
        emergency_only=bool(args.emergency_only),
    )
    state.brightness = min(state.brightness, state.max_brightness)
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
    normalize_pattern_for_mode(state)
    return state, options


def main() -> None:
    args = parse_args()

    if args.show_shortcuts:
        print(SHORTCUTS_TEXT)
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


try:
    main()
except KeyboardInterrupt:
    pass
finally:
    clear_strip(show_now=not isinstance(strip, VirtualStrip))
    if isinstance(strip, VirtualStrip):
        strip.finish()
