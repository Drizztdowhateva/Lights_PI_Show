#!/usr/bin/env python3
"""GTK3 GUI for Lights PI Show.

Requires: python3-gi python3-gi-cairo gir1.2-gtk-3.0
  sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0

Run:
    python3 gui.py
    python3 gui.py --test   # force ASCII/virtual strip (no hardware needed)
"""
from __future__ import annotations

import math
import sys
import threading
import time
from pathlib import Path
from typing import Any

try:
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, Gdk, GLib, GdkPixbuf
    import cairo  # noqa: F401 — used via DrawingArea context
except ImportError:
    sys.exit(
        "GTK3 / PyGObject not found.\n"
        "Install with: sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0"
    )

# Import the backend logic — same file the CLI uses.
try:
    import into
except ImportError:
    sys.exit("Could not import into.py — make sure gui.py is in the same directory.")

# ── icon ─────────────────────────────────────────────────────────────────────

def _load_app_icon() -> GdkPixbuf.Pixbuf | None:
    """Load media/icon.svg (or icon.png) as a GdkPixbuf for the window/taskbar."""
    here = Path(__file__).parent
    for name in ("icon.png", "icon.svg"):
        path = here / "media" / name
        if path.exists():
            try:
                return GdkPixbuf.Pixbuf.new_from_file_at_size(str(path), 128, 128)
            except Exception:
                pass
    return None


# ── constants ────────────────────────────────────────────────────────────────

PREVIEW_COLS = 20          # LEDs per row in the preview grid
PREVIEW_CELL = 18          # px per LED circle (diameter)
PREVIEW_PAD  = 3           # px gap between circles
PREVIEW_FPS  = 25          # target refresh rate for the preview

PATTERN_TOOLTIPS: dict[str, str] = {
    "-1": "Emergency SOS — alternating Red/Blue/White panic flash in Morse SOS pattern.",
    "1":  "Chase — a single bright pixel races around the strip.",
    "2":  "Random — every pixel gets a random color each frame.",
    "3":  "Bounce — a single pixel bounces back and forth.",
    "4":  "Random (alt) — same as Random with the same palette options.",
    "5":  "Comet — a glowing head with a fading amber trail that loops the strip.",
    "6":  "Theater Chase — evenly-spaced lit slots slide along the strip.",
    "7":  "Rainbow Sweep — full HSV rainbow flows across all pixels continuously.",
    "8":  "Pulse — all pixels breathe in and out with a sine-wave brightness curve.",
    "9":  "Sparkle — random pixels flash like white sparkling glitter.",
    "10": "Fire Flame — flickering orange/red heat effect simulating a real flame.",
    "11": "Meteor Shower — a bright comet head with a long fading tail.",
    "12": "Twinkle Stars — individual pixels fade in and out independently.",
}

# Patterns where the color picker is irrelevant (rainbow or SOS)
NO_COLOR_PATTERNS = {"-1", "7"}

# Patterns that use the palette ComboBox (Random family)
PALETTE_PATTERNS = {"2", "4"}

# Patterns that use the named color dropdown (Chase / Bounce)
NAMED_COLOR_PATTERNS = {"1": into.CHASE_COLORS, "3": into.BOUNCE_COLORS}


# ── helper ───────────────────────────────────────────────────────────────────

def packed_to_rgba(packed: int) -> tuple[float, float, float]:
    """Convert a packed 0xRRGGBB int to (r, g, b) floats in [0.0, 1.0]."""
    r = ((packed >> 16) & 0xFF) / 255.0
    g = ((packed >> 8) & 0xFF) / 255.0
    b = (packed & 0xFF) / 255.0
    return r, g, b


def gdk_rgba_to_packed(rgba: Gdk.RGBA) -> int:
    """Convert a Gdk.RGBA to a packed 0xRRGGBB int."""
    r = int(rgba.red * 255) & 0xFF
    g = int(rgba.green * 255) & 0xFF
    b = int(rgba.blue * 255) & 0xFF
    return into.Color(r, g, b)


# ── LED preview drawing area ─────────────────────────────────────────────────

class LEDPreview(Gtk.DrawingArea):
    """Cairo-rendered grid of LED circles mirroring the VirtualStrip pixel buffer."""

    def __init__(self, virtual_strip: into.VirtualStrip) -> None:
        super().__init__()
        self._strip = virtual_strip
        cols = PREVIEW_COLS
        rows = math.ceil(into.LED_COUNT / cols)
        width  = cols * (PREVIEW_CELL + PREVIEW_PAD) + PREVIEW_PAD
        height = rows * (PREVIEW_CELL + PREVIEW_PAD) + PREVIEW_PAD
        self.set_size_request(width, height)
        self.connect("draw", self._on_draw)

    def _on_draw(self, _widget: Gtk.Widget, ctx: Any) -> bool:
        pixels = self._strip.pixels
        cols = PREVIEW_COLS
        ctx.set_source_rgb(0.1, 0.1, 0.1)
        ctx.paint()
        for idx, packed in enumerate(pixels):
            col = idx % cols
            row = idx // cols
            x = PREVIEW_PAD + col * (PREVIEW_CELL + PREVIEW_PAD) + PREVIEW_CELL / 2
            y = PREVIEW_PAD + row * (PREVIEW_CELL + PREVIEW_PAD) + PREVIEW_CELL / 2
            r, g, b = packed_to_rgba(packed)
            if packed == 0:
                ctx.set_source_rgb(0.18, 0.18, 0.18)
            else:
                ctx.set_source_rgb(r, g, b)
            ctx.arc(x, y, PREVIEW_CELL / 2 - 1, 0, 2 * math.pi)
            ctx.fill()
        return False


# ── main application window ──────────────────────────────────────────────────

class LightsApp(Gtk.Application):

    def __init__(self, force_test: bool = False) -> None:
        super().__init__(application_id="com.lights_pi_show.gui")
        self._force_test = force_test
        self._state: into.AppState | None = None
        self._options: into.RunOptions | None = None
        self._virtual_strip: into.VirtualStrip | None = None
        self._anim_thread: threading.Thread | None = None
        self._running = threading.Event()
        self._pattern_buttons: dict[str, Gtk.ToggleButton] = {}
        self._color_section: Gtk.Box | None = None
        self._palette_combo: Gtk.ComboBoxText | None = None
        self._named_color_combo: Gtk.ComboBoxText | None = None
        self._color_chooser: Gtk.ColorChooserWidget | None = None
        self._color_chooser_frame: Gtk.Frame | None = None
        self._named_combo_frame: Gtk.Frame | None = None
        self._speed_scale: Gtk.Scale | None = None
        self._brightness_scale: Gtk.Scale | None = None
        self._speed_label: Gtk.Label | None = None
        self._brightness_label: Gtk.Label | None = None
        self._status_label: Gtk.Label | None = None
        self._run_btn: Gtk.Button | None = None
        self._test_check: Gtk.CheckButton | None = None
        self._stack: Gtk.Stack | None = None
        self._preview: LEDPreview | None = None

    # ── Gtk.Application lifecycle ────────────────────────────────────────────

    def do_activate(self) -> None:
        win = Gtk.ApplicationWindow(application=self)
        win.set_title("Lights PI Show")
        win.set_default_size(860, 640)
        win.connect("delete-event", self._on_window_close)

        # Set window/taskbar/dock icon
        icon = _load_app_icon()
        if icon:
            win.set_icon(icon)
            Gtk.Window.set_default_icon(icon)

        self._build_ui(win)
        win.show_all()
        self._apply_css()

    # ── CSS ──────────────────────────────────────────────────────────────────

    def _apply_css(self) -> None:
        css = b"""
        .pattern-btn { font-size: 11px; padding: 4px 6px; }
        .pattern-btn:checked { background: #3584e4; color: white; }
        .welcome-title { font-size: 28px; font-weight: bold; }
        .welcome-sub { font-size: 14px; color: #888; }
        .section-header { font-size: 12px; font-weight: bold; color: #aaa;
                          margin-top: 8px; }
        .status-bar { font-size: 11px; color: #aaa; padding: 4px; }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    # ── UI build ─────────────────────────────────────────────────────────────

    def _build_ui(self, win: Gtk.ApplicationWindow) -> None:
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        win.add(vbox)

        # Header bar
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.set_title("Lights PI Show")
        header.set_subtitle("WS281X LED Controller")
        win.set_titlebar(header)

        help_btn = Gtk.Button(label="?")
        help_btn.set_tooltip_text("Return to the welcome screen")
        help_btn.connect("clicked", lambda _: self._stack.set_visible_child_name("welcome"))
        header.pack_end(help_btn)

        # Stack: welcome / main
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._stack.set_transition_duration(300)
        vbox.pack_start(self._stack, True, True, 0)

        self._stack.add_named(self._build_welcome_page(), "welcome")
        self._stack.add_named(self._build_main_page(), "main")
        self._stack.set_visible_child_name("welcome")

        # Status bar
        self._status_label = Gtk.Label(label="Ready")
        self._status_label.get_style_context().add_class("status-bar")
        self._status_label.set_xalign(0)
        self._status_label.set_margin_start(8)
        vbox.pack_end(self._status_label, False, False, 0)

    # ── welcome page ─────────────────────────────────────────────────────────

    def _build_welcome_page(self) -> Gtk.Widget:
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_valign(Gtk.Align.CENTER)
        outer.set_halign(Gtk.Align.CENTER)
        outer.set_margin_top(40)
        outer.set_margin_bottom(40)
        outer.set_margin_start(60)
        outer.set_margin_end(60)

        title = Gtk.Label(label="🌈  Lights PI Show")
        title.get_style_context().add_class("welcome-title")
        outer.pack_start(title, False, False, 8)

        sub = Gtk.Label(label="WS281X LED Pattern Controller for Raspberry Pi")
        sub.get_style_context().add_class("welcome-sub")
        outer.pack_start(sub, False, False, 4)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(16)
        sep.set_margin_bottom(16)
        outer.pack_start(sep, False, False, 0)

        features = [
            "🎨  13 built-in patterns — Chase, Bounce, Random, Comet, Fire, Meteor, Twinkle and more",
            "🖌️   Custom color picker — 256-color HSV wheel for any pattern",
            "🌈  8 random palettes — Any RGB, Warm, Cool, Pastel, Neon, Ocean, Fire, Forest",
            "⚡  Live LED preview — see the animation before it hits the strip",
            "🎛️   Speed + Brightness sliders — fine control in real time",
            "🚨  Emergency SOS mode — panic flash override",
            "💾  Headless JSON config — save and reload settings",
        ]
        for feat in features:
            lbl = Gtk.Label(label=feat)
            lbl.set_xalign(0)
            lbl.set_margin_start(16)
            lbl.set_margin_bottom(4)
            outer.pack_start(lbl, False, False, 0)

        sep2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep2.set_margin_top(16)
        sep2.set_margin_bottom(20)
        outer.pack_start(sep2, False, False, 0)

        btn = Gtk.Button(label="  Get Started  ")
        btn.set_halign(Gtk.Align.CENTER)
        btn.get_style_context().add_class("suggested-action")
        btn.set_tooltip_text("Open the LED controller")
        btn.connect("clicked", self._on_get_started)
        outer.pack_start(btn, False, False, 0)

        return outer

    def _on_get_started(self, _btn: Gtk.Button) -> None:
        self._stack.set_visible_child_name("main")

    # ── main page ────────────────────────────────────────────────────────────

    def _build_main_page(self) -> Gtk.Widget:
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(420)

        paned.pack1(self._build_left_panel(), resize=True, shrink=False)
        paned.pack2(self._build_right_panel(), resize=True, shrink=False)
        return paned

    # ── left panel (controls) ─────────────────────────────────────────────────

    def _build_left_panel(self) -> Gtk.Widget:
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_width(380)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_margin_top(10)
        vbox.set_margin_bottom(10)
        vbox.set_margin_start(10)
        vbox.set_margin_end(10)
        scroll.add(vbox)

        # ── Patterns ──
        ph = Gtk.Label(label="PATTERN")
        ph.get_style_context().add_class("section-header")
        ph.set_xalign(0)
        vbox.pack_start(ph, False, False, 0)

        flow = Gtk.FlowBox()
        flow.set_max_children_per_line(4)
        flow.set_min_children_per_line(2)
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_row_spacing(4)
        flow.set_column_spacing(4)
        vbox.pack_start(flow, False, False, 0)

        # SOS first, then numeric order
        ordered_keys = ["-1"] + [str(i) for i in range(1, 13)]
        for key in ordered_keys:
            name = into.PATTERN_NAMES.get(key, key)
            btn = Gtk.ToggleButton(label=f"{key}: {name}")
            btn.get_style_context().add_class("pattern-btn")
            btn.set_tooltip_text(PATTERN_TOOLTIPS.get(key, name))
            btn.connect("toggled", self._on_pattern_toggled, key)
            self._pattern_buttons[key] = btn
            flow.add(btn)

        # ── Speed ──
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(6)
        vbox.pack_start(sep, False, False, 0)

        speed_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        sh_lbl = Gtk.Label(label="SPEED")
        sh_lbl.get_style_context().add_class("section-header")
        sh_lbl.set_xalign(0)
        self._speed_label = Gtk.Label(label="Level 5")
        self._speed_label.set_xalign(1)
        speed_hdr.pack_start(sh_lbl, True, True, 0)
        speed_hdr.pack_end(self._speed_label, False, False, 0)
        vbox.pack_start(speed_hdr, False, False, 0)

        self._speed_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 9, 1)
        self._speed_scale.set_value(5)
        self._speed_scale.set_draw_value(False)
        self._speed_scale.set_tooltip_text(
            "Animation speed: 0 = constant (no delay), 1 = slowest, 9 = fastest.\n"
            "Runtime keys: + / = to speed up, - to slow down."
        )
        self._speed_scale.connect("value-changed", self._on_speed_changed)
        vbox.pack_start(self._speed_scale, False, False, 0)

        # ── Brightness ──
        bright_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        bh_lbl = Gtk.Label(label="BRIGHTNESS")
        bh_lbl.get_style_context().add_class("section-header")
        bh_lbl.set_xalign(0)
        self._brightness_label = Gtk.Label(label="255 (100%)")
        self._brightness_label.set_xalign(1)
        bright_hdr.pack_start(bh_lbl, True, True, 0)
        bright_hdr.pack_end(self._brightness_label, False, False, 0)
        vbox.pack_start(bright_hdr, False, False, 0)

        self._brightness_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 255, 1)
        self._brightness_scale.set_value(255)
        self._brightness_scale.set_draw_value(False)
        self._brightness_scale.set_tooltip_text(
            "LED brightness: 0 = off, 255 = maximum.\n"
            "Runtime keys: ↑ brighten, ↓ dim."
        )
        self._brightness_scale.connect("value-changed", self._on_brightness_changed)
        vbox.pack_start(self._brightness_scale, False, False, 0)

        # ── Color section ──
        sep2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep2.set_margin_top(6)
        vbox.pack_start(sep2, False, False, 0)

        self._color_section = self._build_color_section()
        vbox.pack_start(self._color_section, False, False, 0)

        # ── Run controls ──
        sep3 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep3.set_margin_top(6)
        vbox.pack_start(sep3, False, False, 0)

        run_hdr = Gtk.Label(label="RUN")
        run_hdr.get_style_context().add_class("section-header")
        run_hdr.set_xalign(0)
        vbox.pack_start(run_hdr, False, False, 0)

        self._test_check = Gtk.CheckButton(label="Test / simulation mode (no hardware)")
        self._test_check.set_active(self._force_test)
        self._test_check.set_tooltip_text(
            "When checked, runs a virtual strip instead of real LEDs.\n"
            "Safe to use on any computer — no Raspberry Pi needed."
        )
        vbox.pack_start(self._test_check, False, False, 0)

        run_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._run_btn = Gtk.Button(label="▶  Start")
        self._run_btn.get_style_context().add_class("suggested-action")
        self._run_btn.set_tooltip_text("Start the LED animation (or press Stop to halt it).")
        self._run_btn.connect("clicked", self._on_run_stop)
        run_row.pack_start(self._run_btn, True, True, 0)
        vbox.pack_start(run_row, False, False, 4)

        # Select pattern 1 by default
        self._select_pattern_button("1")

        return scroll

    def _build_color_section(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        color_hdr = Gtk.Label(label="COLOR")
        color_hdr.get_style_context().add_class("section-header")
        color_hdr.set_xalign(0)
        box.pack_start(color_hdr, False, False, 0)

        # Palette combo (for random patterns)
        self._named_combo_frame = Gtk.Frame(label=None)
        named_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        named_vbox.set_margin_top(4)
        named_vbox.set_margin_start(4)
        named_vbox.set_margin_end(4)
        named_vbox.set_margin_bottom(4)
        self._named_combo_frame.add(named_vbox)

        # Named color dropdown for chase/bounce
        chase_lbl = Gtk.Label(label="Named color preset:")
        chase_lbl.set_xalign(0)
        named_vbox.pack_start(chase_lbl, False, False, 0)
        self._named_color_combo = Gtk.ComboBoxText()
        self._named_color_combo.set_tooltip_text(
            "Choose a preset color for this pattern.\n"
            "Select 'Custom' to use the color wheel below."
        )
        self._named_color_combo.connect("changed", self._on_named_color_changed)
        named_vbox.pack_start(self._named_color_combo, False, False, 0)

        # Palette dropdown for random patterns
        palette_lbl = Gtk.Label(label="Random palette:")
        palette_lbl.set_xalign(0)
        named_vbox.pack_start(palette_lbl, False, False, 0)
        self._palette_combo = Gtk.ComboBoxText()
        self._palette_combo.set_tooltip_text(
            "Select the color palette used for random pixel assignments.\n"
            "Each palette has a distinct mood."
        )
        for key, (name, _) in into.RANDOM_PALETTES.items():
            self._palette_combo.append(key, f"{key}: {name}")
        self._palette_combo.set_active_id("1")
        self._palette_combo.connect("changed", self._on_palette_changed)
        named_vbox.pack_start(self._palette_combo, False, False, 0)

        box.pack_start(self._named_combo_frame, False, False, 0)

        # HSV color wheel
        self._color_chooser_frame = Gtk.Frame(label="Custom color (HSV wheel)")
        self._color_chooser = Gtk.ColorChooserWidget()
        self._color_chooser.set_use_alpha(False)
        self._color_chooser.set_tooltip_text(
            "Pick any custom color using the HSV wheel.\n"
            "This color is used by patterns that support a custom hue\n"
            "(e.g. Comet, Theater Chase, Pulse, Sparkle, Fire, Meteor, Twinkle,\n"
            "and Chase/Bounce when 'Custom' is selected above)."
        )
        self._color_chooser.connect("notify::rgba", self._on_color_chosen)
        self._color_chooser_frame.add(self._color_chooser)
        box.pack_start(self._color_chooser_frame, False, False, 0)

        return box

    # ── right panel (preview) ─────────────────────────────────────────────────

    def _build_right_panel(self) -> Gtk.Widget:
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_margin_top(10)
        vbox.set_margin_bottom(10)
        vbox.set_margin_start(6)
        vbox.set_margin_end(10)

        ph = Gtk.Label(label="LED PREVIEW")
        ph.get_style_context().add_class("section-header")
        ph.set_xalign(0)
        vbox.pack_start(ph, False, False, 0)

        # Virtual strip (always active for preview)
        self._virtual_strip = into.VirtualStrip(into.LED_COUNT)
        self._preview = LEDPreview(self._virtual_strip)
        self._preview.set_tooltip_text(
            "Live preview of the LED strip (virtual simulation).\n"
            "Refreshes at ~25 fps when the animation is running."
        )

        preview_scroll = Gtk.ScrolledWindow()
        preview_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        preview_scroll.add(self._preview)
        vbox.pack_start(preview_scroll, True, True, 0)

        return vbox

    # ── state construction ────────────────────────────────────────────────────

    def _build_state(self) -> into.AppState:
        speed_val = str(int(self._speed_scale.get_value()))
        bright_val = int(self._brightness_scale.get_value())

        # Determine active pattern
        active_pattern = "1"
        for key, btn in self._pattern_buttons.items():
            if btn.get_active():
                active_pattern = key
                break

        # Custom color from wheel
        rgba = self._color_chooser.get_rgba()
        custom_color = gdk_rgba_to_packed(rgba)

        # Chase / bounce named color
        chase_color = "1"
        bounce_color = "1"
        random_palette = self._palette_combo.get_active_id() or "1"

        named_id = self._named_color_combo.get_active_id()
        if active_pattern == "1":
            chase_color = named_id or "1"
        elif active_pattern == "3":
            bounce_color = named_id or "1"

        state = into.AppState(
            pattern=active_pattern,
            speed=speed_val,
            chase_color=chase_color,
            random_palette=random_palette,
            bounce_color=bounce_color,
            brightness=into.clamp_brightness(bright_val),
            max_brightness=into.clamp_brightness(bright_val),
            custom_color=custom_color,
        )
        into.normalize_pattern_for_mode(state)
        return state

    # ── animation control ─────────────────────────────────────────────────────

    def _on_run_stop(self, _btn: Gtk.Button) -> None:
        if self._running.is_set():
            self._stop_animation()
        else:
            self._start_animation()

    def _start_animation(self) -> None:
        state = self._build_state()
        options = into.RunOptions()
        test_mode = self._test_check.get_active() or self._force_test

        # Set the global strip used by pattern functions
        if test_mode:
            into.strip = self._virtual_strip
        else:
            try:
                into.init_strip()
                into.get_strip().begin()
            except RuntimeError as exc:
                self._set_status(f"Hardware error: {exc}")
                self._test_check.set_active(True)
                into.strip = self._virtual_strip

        self._virtual_strip.pixels = [into.Color(0, 0, 0)] * into.LED_COUNT
        into.apply_brightness_from_state(state)

        self._state = state
        self._options = options
        self._running.set()

        self._run_btn.set_label("⏹  Stop")
        self._run_btn.get_style_context().remove_class("suggested-action")
        self._run_btn.get_style_context().add_class("destructive-action")

        self._anim_thread = threading.Thread(target=self._anim_loop, args=(state,), daemon=True)
        self._anim_thread.start()

        # Schedule preview refresh
        GLib.timeout_add(1000 // PREVIEW_FPS, self._refresh_preview)

        self._set_status(
            f"Running: {into.PATTERN_NAMES.get(state.pattern, state.pattern)} | "
            f"Speed {into.SPEED_LABELS[state.speed]} | "
            f"Brightness {state.brightness}"
        )

    def _stop_animation(self) -> None:
        self._running.clear()
        if self._anim_thread:
            self._anim_thread.join(timeout=1.0)
            self._anim_thread = None
        into.clear_strip(show_now=False)
        self._run_btn.set_label("▶  Start")
        self._run_btn.get_style_context().remove_class("destructive-action")
        self._run_btn.get_style_context().add_class("suggested-action")
        self._set_status("Stopped.")

    def _anim_loop(self, state: into.AppState) -> None:
        """Background thread — drives pattern steps against the virtual strip."""
        while self._running.is_set():
            # Sync live control changes from sliders / buttons to state
            self._sync_state_from_ui(state)
            into.run_pattern_step(state)
            # Also step against the real hardware strip if active
            if not isinstance(into.strip, into.VirtualStrip) and into.strip is not None:
                try:
                    into.run_pattern_step(state)
                except Exception:
                    pass
            delay = into.get_delay(state)
            if delay > 0:
                time.sleep(delay)

    def _sync_state_from_ui(self, state: into.AppState) -> None:
        """Pull latest slider / button values into state safely from bg thread."""
        # Only safe reads — Gtk widgets must be read from a GLib.idle callback
        # We use a simple shared cache updated in the main thread signal handlers.
        pass  # handled via direct state mutation in signal handlers below

    def _refresh_preview(self) -> bool:
        if self._preview:
            self._preview.queue_draw()
        return self._running.is_set()  # returning False stops the timeout

    # ── signal handlers ───────────────────────────────────────────────────────

    def _on_pattern_toggled(self, btn: Gtk.ToggleButton, pattern_key: str) -> None:
        if not btn.get_active():
            return
        # Untoggle all others
        for key, other_btn in self._pattern_buttons.items():
            if key != pattern_key and other_btn.get_active():
                other_btn.handler_block_by_func(self._on_pattern_toggled)
                other_btn.set_active(False)
                other_btn.handler_unblock_by_func(self._on_pattern_toggled)

        self._update_color_section_visibility(pattern_key)

        # Update running state if animation is active
        if self._running.is_set() and self._state:
            self._state.pattern = pattern_key

    def _on_speed_changed(self, scale: Gtk.Scale) -> None:
        val = int(scale.get_value())
        speed_key = str(val)
        label = into.SPEED_LABELS.get(speed_key, f"Level {val}")
        if self._speed_label:
            self._speed_label.set_text(label)
        if self._running.is_set() and self._state:
            self._state.speed = speed_key

    def _on_brightness_changed(self, scale: Gtk.Scale) -> None:
        val = int(scale.get_value())
        pct = int(val / 255 * 100)
        if self._brightness_label:
            self._brightness_label.set_text(f"{val} ({pct}%)")
        if self._running.is_set() and self._state:
            self._state.brightness = into.clamp_brightness(val)
            into.set_strip_brightness(self._state.brightness)

    def _on_palette_changed(self, combo: Gtk.ComboBoxText) -> None:
        palette_id = combo.get_active_id()
        if palette_id and self._running.is_set() and self._state:
            self._state.random_palette = palette_id

    def _on_named_color_changed(self, combo: Gtk.ComboBoxText) -> None:
        color_id = combo.get_active_id()
        if not color_id or not self._state:
            return
        active_pattern = self._state.pattern if self._running.is_set() else self._get_active_pattern()
        if active_pattern == "1":
            if self._running.is_set():
                self._state.chase_color = color_id
        elif active_pattern == "3":
            if self._running.is_set():
                self._state.bounce_color = color_id
        # Show/hide color wheel depending on "Custom" selection
        show_wheel = (color_id == "5")
        if self._color_chooser_frame:
            if show_wheel:
                self._color_chooser_frame.show()
            else:
                self._color_chooser_frame.hide()

    def _on_color_chosen(self, chooser: Gtk.ColorChooserWidget, _param: Any) -> None:
        rgba = chooser.get_rgba()
        packed = gdk_rgba_to_packed(rgba)
        if self._running.is_set() and self._state:
            self._state.custom_color = packed

    # ── color section visibility management ──────────────────────────────────

    def _get_active_pattern(self) -> str:
        for key, btn in self._pattern_buttons.items():
            if btn.get_active():
                return key
        return "1"

    def _update_color_section_visibility(self, pattern_key: str) -> None:
        if not self._color_section:
            return

        is_no_color = pattern_key in NO_COLOR_PATTERNS
        is_palette  = pattern_key in PALETTE_PATTERNS
        is_named    = pattern_key in NAMED_COLOR_PATTERNS

        if is_no_color:
            self._color_section.hide()
            return

        self._color_section.show()

        # Show/hide the named-combo frame
        if is_named or is_palette:
            self._named_combo_frame.show()
        else:
            self._named_combo_frame.hide()

        # Populate named combo for chase/bounce
        if is_named:
            color_map = NAMED_COLOR_PATTERNS[pattern_key]
            self._named_color_combo.remove_all()
            for k, (name, _) in color_map.items():
                self._named_color_combo.append(k, f"{k}: {name}")
            # Get current selection from state if running
            if self._running.is_set() and self._state:
                current = self._state.chase_color if pattern_key == "1" else self._state.bounce_color
                self._named_color_combo.set_active_id(current)
            else:
                self._named_color_combo.set_active(0)
            self._named_color_combo.show()

            # Hide palette combo label/widget
            for child in self._named_combo_frame.get_child():
                pass  # handled by show()/hide() on palette_combo directly
            self._palette_combo.hide()

            # Show wheel only if Custom is selected
            named_id = self._named_color_combo.get_active_id()
            if named_id == "5":
                self._color_chooser_frame.show()
            else:
                self._color_chooser_frame.hide()

        elif is_palette:
            self._palette_combo.show()
            self._named_color_combo.hide()
            self._color_chooser_frame.hide()

        else:
            # Direct custom color patterns (Comet, Theater, Pulse, Sparkle, Fire, Meteor, Twinkle)
            self._palette_combo.hide()
            self._named_color_combo.hide()
            self._color_chooser_frame.show()

    def _select_pattern_button(self, key: str) -> None:
        btn = self._pattern_buttons.get(key)
        if btn:
            btn.set_active(True)
        self._update_color_section_visibility(key)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _set_status(self, msg: str) -> None:
        def _do() -> bool:
            if self._status_label:
                self._status_label.set_text(msg)
            return False
        GLib.idle_add(_do)

    def _on_window_close(self, _win: Gtk.Window, _event: Any) -> bool:
        self._running.clear()
        into.clear_strip(show_now=False)
        return False  # allow close


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Lights PI Show — GTK3 GUI")
    parser.add_argument("--test", action="store_true", help="Force simulation mode (no hardware)")
    args = parser.parse_args()

    app = LightsApp(force_test=args.test)
    sys.exit(app.run(None))


if __name__ == "__main__":
    main()
