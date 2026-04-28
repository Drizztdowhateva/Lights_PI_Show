#!/usr/bin/env python3
"""
CLI Utilities for LightsPiShow - Enhanced User Experience
"""

import sys
import time
import threading
from typing import Optional, Callable, Any
from dataclasses import dataclass
from pathlib import Path
import json

# ANSI Color codes
class Colors:
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    DIM = '\033[2m'

@dataclass
class StatusInfo:
    pattern: str
    speed: str
    brightness: int
    color: str
    uptime: float
    fps: float

class ProgressBar:
    def __init__(self, total: int, width: int = 50, description: str = "Progress"):
        self.total = total
        self.width = width
        self.description = description
        self.current = 0
        self.start_time = time.time()
        
    def update(self, increment: int = 1):
        self.current += increment
        self._display()
        
    def _display(self):
        if self.total == 0:
            return
            
        percentage = self.current / self.total
        filled_width = int(self.width * percentage)
        bar = '█' * filled_width + '░' * (self.width - filled_width)
        
        elapsed = time.time() - self.start_time
        if self.current > 0:
            eta = elapsed * (self.total - self.current) / self.current
            eta_str = f"ETA: {eta:.1f}s"
        else:
            eta_str = "ETA: --"
            
        print(f'\r{Colors.CYAN}{self.description}: {Colors.GREEN}[{bar}]{Colors.CYAN} '
              f'{percentage:.1%} {eta_str}{Colors.RESET}', end='', flush=True)
        
        if self.current >= self.total:
            print()  # New line when complete

class StatusDisplay:
    def __init__(self):
        self.status = StatusInfo("", "", 0, "", 0.0, 0.0)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
    def update(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self.status, key):
                setattr(self.status, key, value)
                
    def start_monitoring(self):
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._thread.start()
            
    def stop_monitoring(self):
        self._running = False
        if self._thread:
            self._thread.join()
            
    def _monitor_loop(self):
        while self._running:
            self._display_status()
            time.sleep(1)
            
    def _display_status(self):
        # Clear previous status line
        sys.stdout.write('\r' + ' ' * 100 + '\r')
        
        status_line = (
            f"{Colors.BOLD}Pattern:{Colors.RESET} {self.status.pattern} | "
            f"{Colors.BOLD}Speed:{Colors.RESET} {self.status.speed} | "
            f"{Colors.BOLD}Brightness:{Colors.RESET} {self.status.brightness}% | "
            f"{Colors.BOLD}Color:{Colors.RESET} {self.status.color} | "
            f"{Colors.BOLD}FPS:{Colors.RESET} {self.status.fps:.1f}"
        )
        
        print(f"{Colors.CYAN}{status_line}{Colors.RESET}", end='', flush=True)

class CommandHistory:
    def __init__(self, max_history: int = 100):
        self.history: list[str] = []
        self.max_history = max_history
        self.current_index = -1
        self.temp_input = ""
        
    def add(self, command: str):
        if command and (not self.history or self.history[-1] != command):
            self.history.append(command)
            if len(self.history) > self.max_history:
                self.history.pop(0)
        self.current_index = len(self.history)
        
    def get_previous(self) -> Optional[str]:
        if self.current_index > 0:
            self.current_index -= 1
            return self.history[self.current_index]
        return None
        
    def get_next(self) -> Optional[str]:
        if self.current_index < len(self.history) - 1:
            self.current_index += 1
            return self.history[self.current_index]
        return None

class ConfigProfile:
    def __init__(self, profile_dir: str = "profiles"):
        self.profile_dir = Path(profile_dir)
        self.profile_dir.mkdir(exist_ok=True)
        
    def save_profile(self, name: str, state: dict, options: dict):
        profile_path = self.profile_dir / f"{name}.json"
        profile_data = {
            "name": name,
            "state": state,
            "options": options,
            "created_at": time.time(),
            "version": "1.0"
        }
        
        with open(profile_path, 'w') as f:
            json.dump(profile_data, f, indent=2)
            
        print(f"{Colors.GREEN}Profile '{name}' saved successfully{Colors.RESET}")
        
    def load_profile(self, name: str) -> tuple[dict, dict]:
        profile_path = self.profile_dir / f"{name}.json"
        
        if not profile_path.exists():
            raise FileNotFoundError(f"Profile '{name}' not found")
            
        with open(profile_path, 'r') as f:
            profile_data = json.load(f)
            
        return profile_data.get("state", {}), profile_data.get("options", {})
        
    def list_profiles(self) -> list[str]:
        profiles = []
        for file in self.profile_dir.glob("*.json"):
            profiles.append(file.stem)
        return sorted(profiles)
        
    def delete_profile(self, name: str):
        profile_path = self.profile_dir / f"{name}.json"
        if profile_path.exists():
            profile_path.unlink()
            print(f"{Colors.YELLOW}Profile '{name}' deleted{Colors.RESET}")
        else:
            print(f"{Colors.RED}Profile '{name}' not found{Colors.RESET}")

def colored_print(text: str, color: str = Colors.WHITE, bold: bool = False):
    """Print text with color and optional bold formatting"""
    prefix = color
    if bold:
        prefix += Colors.BOLD
    print(f"{prefix}{text}{Colors.RESET}")

def success_print(text: str):
    colored_print(f"✓ {text}", Colors.GREEN, bold=True)

def error_print(text: str):
    colored_print(f"✗ {text}", Colors.RED, bold=True)

def warning_print(text: str):
    colored_print(f"⚠ {text}", Colors.YELLOW, bold=True)

def info_print(text: str):
    colored_print(f"ℹ {text}", Colors.BLUE, bold=True)

def show_enhanced_help():
    """Show enhanced help with examples and shortcuts"""
    help_text = f"""
{Colors.BOLD}{Colors.CYAN}=== Lights Pi Show - Enhanced Help ==={Colors.RESET}

{Colors.BOLD}Basic Commands:{Colors.RESET}
{Colors.GREEN}1-9{Colors.RESET}           - Switch to pattern
{Colors.GREEN}a/d{Colors.RESET}           - Cycle patterns left/right
{Colors.GREEN}w/s{Colors.RESET}           - Brightness up/down
{Colors.GREEN}+/-{Colors.RESET}           - Speed up/down
{Colors.GREEN}c{Colors.RESET}             - Cycle color options
{Colors.GREEN}k{Colors.RESET}             - Enter custom color
{Colors.GREEN}n{Colors.RESET}             - Show named colors

{Colors.BOLD}Advanced Commands:{Colors.RESET}
{Colors.YELLOW}p{Colors.RESET}             - Save current profile
{Colors.YELLOW}l{Colors.RESET}             - Load profile
{Colors.YELLOW}P{Colors.RESET}             - Profile management
{Colors.YELLOW}S{Colors.RESET}             - Status monitoring
{Colors.YELLOW}D{Colors.RESET}             - Debug mode
{Colors.YELLOW}h{Colors.RESET}             - Show this help
{Colors.YELLOW}q{Colors.RESET}             - Quit

{Colors.BOLD}Examples:{Colors.RESET}
{Colors.DIM}./Lights.sh --pattern 1 --speed 9 --brightness 80{Colors.RESET}
{Colors.DIM}./Lights.sh --headless --profile party{Colors.RESET}
{Colors.DIM}./Lights.sh --test --debug{Colors.RESET}

{Colors.BOLD}Quick Tips:{Colors.RESET}
• Press {Colors.YELLOW}Tab{Colors.RESET} for command completion
• Use {Colors.YELLOW}↑/↓{Colors.RESET} arrows for command history
• Press {Colors.YELLOW}Ctrl+C{Colors.RESET} to emergency stop
• Type {Colors.YELLOW}help{Colors.RESET} for contextual help
"""
    print(help_text)

# Global instances
status_display = StatusDisplay()
command_history = CommandHistory()
config_profiles = ConfigProfile()
