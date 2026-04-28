#!/usr/bin/env python3
"""
Advanced Features for LightsPiShow - Performance, Automation, and Professional Features
"""

import sys
import time
import threading
import json
import subprocess
import psutil
import socket
import http.server
import socketserver
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
from datetime import datetime, timedelta
import queue

# Import main components
try:
    from into import AppState, RunOptions, PATTERN_NAMES, LED_COUNT
    from cli_utils import Colors, success_print, error_print, warning_print, info_print
except ImportError:
    warning_print("Main components not available for advanced features")

@dataclass
class PerformanceMetrics:
    fps: float = 0.0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    uptime: float = 0.0
    frames_rendered: int = 0
    errors_count: int = 0
    last_update: float = 0.0

@dataclass
class SessionStats:
    start_time: float = 0.0
    total_runtime: float = 0.0
    patterns_used: Dict[str, float] = None
    favorite_pattern: str = "1"
    average_brightness: float = 128.0
    total_commands: int = 0
    
    def __post_init__(self):
        if self.patterns_used is None:
            self.patterns_used = {}

class PerformanceMonitor:
    """Monitor system performance and LED strip metrics"""
    
    def __init__(self):
        self.metrics = PerformanceMetrics()
        self.session_stats = SessionStats()
        self.start_time = time.time()
        self.frame_count = 0
        self.last_frame_time = time.time()
        self.error_log = []
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        
    def start_monitoring(self):
        """Start performance monitoring"""
        self.monitoring = True
        self.session_stats.start_time = time.time()
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        info_print("Performance monitoring started")
        
    def stop_monitoring(self):
        """Stop performance monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
        self.session_stats.total_runtime = time.time() - self.session_stats.start_time
        info_print("Performance monitoring stopped")
        
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.monitoring:
            try:
                # Update system metrics
                self.metrics.cpu_usage = psutil.cpu_percent()
                self.metrics.memory_usage = psutil.virtual_memory().percent
                self.metrics.uptime = time.time() - self.start_time
                
                # Calculate FPS
                current_time = time.time()
                if self.frame_count > 0:
                    time_diff = current_time - self.last_frame_time
                    if time_diff > 0:
                        self.metrics.fps = 1.0 / time_diff
                        
                self.metrics.last_update = current_time
                self.last_frame_time = current_time
                
                time.sleep(0.1)  # Update every 100ms
                
            except Exception as e:
                self.log_error(f"Monitor error: {e}")
                
    def record_frame(self):
        """Record a rendered frame"""
        self.frame_count += 1
        self.metrics.frames_rendered = self.frame_count
        
    def log_error(self, error: str):
        """Log an error"""
        timestamp = datetime.now().isoformat()
        self.error_log.append({"timestamp": timestamp, "error": error})
        self.metrics.errors_count = len(self.error_log)
        error_print(f"Error logged: {error}")
        
    def get_metrics(self) -> PerformanceMetrics:
        """Get current performance metrics"""
        return self.metrics
        
    def get_session_stats(self) -> SessionStats:
        """Get session statistics"""
        return self.session_stats
        
    def export_metrics(self, filepath: str):
        """Export metrics to JSON file"""
        data = {
            "performance": asdict(self.metrics),
            "session": asdict(self.session_stats),
            "errors": self.error_log[-10:],  # Last 10 errors
            "export_time": datetime.now().isoformat()
        }
        
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            success_print(f"Metrics exported to: {filepath}")
        except Exception as e:
            error_print(f"Failed to export metrics: {e}")

class CommandQueue:
    """Queue system for sequential command execution"""
    
    def __init__(self):
        self.queue = queue.Queue()
        self.running = False
        self.worker_thread: Optional[threading.Thread] = None
        self.current_command: Optional[Dict] = None
        self.command_history: List[Dict] = []
        
    def add_command(self, command_type: str, params: Dict[str, Any], delay: float = 0.0):
        """Add a command to the queue"""
        command = {
            "type": command_type,
            "params": params,
            "delay": delay,
            "timestamp": time.time(),
            "id": len(self.command_history)
        }
        self.queue.put(command)
        self.command_history.append(command)
        info_print(f"Command queued: {command_type}")
        
    def start_processing(self):
        """Start processing the command queue"""
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
            self.worker_thread.start()
            info_print("Command queue processing started")
            
    def stop_processing(self):
        """Stop processing the command queue"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=1.0)
        info_print("Command queue processing stopped")
        
    def _process_queue(self):
        """Process commands from the queue"""
        while self.running:
            try:
                command = self.queue.get(timeout=0.1)
                self.current_command = command
                
                # Apply delay if specified
                if command["delay"] > 0:
                    time.sleep(command["delay"])
                    
                # Execute command
                self._execute_command(command)
                
                self.queue.task_done()
                self.current_command = None
                
            except queue.Empty:
                continue
            except Exception as e:
                error_print(f"Command execution error: {e}")
                
    def _execute_command(self, command: Dict):
        """Execute a single command"""
        command_type = command["type"]
        params = command["params"]
        
        if command_type == "set_pattern":
            info_print(f"Setting pattern to: {params.get('pattern', 'unknown')}")
        elif command_type == "set_brightness":
            info_print(f"Setting brightness to: {params.get('brightness', 0)}")
        elif command_type == "set_speed":
            info_print(f"Setting speed to: {params.get('speed', 'unknown')}")
        elif command_type == "set_color":
            info_print(f"Setting color to: {params.get('color', 'unknown')}")
        elif command_type == "wait":
            time.sleep(params.get("duration", 1.0))
        else:
            warning_print(f"Unknown command type: {command_type}")
            
    def get_queue_status(self) -> Dict:
        """Get current queue status"""
        return {
            "queue_size": self.queue.qsize(),
            "running": self.running,
            "current_command": self.current_command,
            "total_commands": len(self.command_history)
        }

class MacroSystem:
    """Record and playback command sequences"""
    
    def __init__(self):
        self.recording = False
        self.recorded_commands: List[Dict] = []
        self.macros: Dict[str, List[Dict]] = {}
        self.start_time = 0.0
        
    def start_recording(self, macro_name: str):
        """Start recording a macro"""
        if self.recording:
            warning_print("Already recording a macro")
            return
            
        self.recording = True
        self.recorded_commands = []
        self.start_time = time.time()
        info_print(f"Started recording macro: {macro_name}")
        
    def stop_recording(self, macro_name: str):
        """Stop recording and save macro"""
        if not self.recording:
            warning_print("Not currently recording")
            return
            
        self.recording = False
        
        # Calculate relative timing
        for cmd in self.recorded_commands:
            cmd["relative_time"] = cmd["timestamp"] - self.start_time
            
        self.macros[macro_name] = self.recorded_commands.copy()
        success_print(f"Macro '{macro_name}' saved with {len(self.recorded_commands)} commands")
        
    def record_command(self, command_type: str, params: Dict[str, Any]):
        """Record a command during macro recording"""
        if self.recording:
            command = {
                "type": command_type,
                "params": params,
                "timestamp": time.time()
            }
            self.recorded_commands.append(command)
            
    def play_macro(self, macro_name: str, command_queue: CommandQueue):
        """Play back a recorded macro"""
        if macro_name not in self.macros:
            error_print(f"Macro '{macro_name}' not found")
            return
            
        commands = self.macros[macro_name]
        info_print(f"Playing macro '{macro_name}' with {len(commands)} commands")
        
        for cmd in commands:
            delay = cmd.get("relative_time", 0.0)
            command_queue.add_command(cmd["type"], cmd["params"], delay)
            
    def list_macros(self) -> List[str]:
        """List all available macros"""
        return list(self.macros.keys())
        
    def delete_macro(self, macro_name: str):
        """Delete a macro"""
        if macro_name in self.macros:
            del self.macros[macro_name]
            success_print(f"Macro '{macro_name}' deleted")
        else:
            error_print(f"Macro '{macro_name}' not found")
            
    def save_macros(self, filepath: str):
        """Save macros to file"""
        try:
            with open(filepath, 'w') as f:
                json.dump(self.macros, f, indent=2)
            success_print(f"Macros saved to: {filepath}")
        except Exception as e:
            error_print(f"Failed to save macros: {e}")
            
    def load_macros(self, filepath: str):
        """Load macros from file"""
        try:
            with open(filepath, 'r') as f:
                self.macros = json.load(f)
            success_print(f"Macros loaded from: {filepath}")
        except Exception as e:
            error_print(f"Failed to load macros: {e}")

class PluginManager:
    """Simple plugin system for custom patterns"""
    
    def __init__(self):
        self.plugins: Dict[str, Any] = {}
        self.plugin_dir = Path("plugins")
        self.plugin_dir.mkdir(exist_ok=True)
        
    def load_plugin(self, plugin_name: str, plugin_path: str):
        """Load a plugin from file"""
        try:
            # Simple plugin loading - in real implementation, use importlib
            plugin_data = {
                "name": plugin_name,
                "path": plugin_path,
                "loaded_at": time.time()
            }
            self.plugins[plugin_name] = plugin_data
            success_print(f"Plugin '{plugin_name}' loaded")
        except Exception as e:
            error_print(f"Failed to load plugin '{plugin_name}': {e}")
            
    def unload_plugin(self, plugin_name: str):
        """Unload a plugin"""
        if plugin_name in self.plugins:
            del self.plugins[plugin_name]
            success_print(f"Plugin '{plugin_name}' unloaded")
        else:
            error_print(f"Plugin '{plugin_name}' not found")
            
    def list_plugins(self) -> List[str]:
        """List all loaded plugins"""
        return list(self.plugins.keys())
        
    def get_plugin_info(self, plugin_name: str) -> Optional[Dict]:
        """Get plugin information"""
        return self.plugins.get(plugin_name)

class APIServer:
    """Simple REST API for remote control"""
    
    def __init__(self, port: int = 8080):
        self.port = port
        self.server = None
        self.server_thread: Optional[threading.Thread] = None
        self.running = False
        
    def start_server(self):
        """Start the API server"""
        if self.running:
            warning_print("API server already running")
            return
            
        try:
            handler = self._create_handler()
            self.server = socketserver.TCPServer(("", self.port), handler)
            self.running = True
            self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.server_thread.start()
            success_print(f"API server started on port {self.port}")
        except Exception as e:
            error_print(f"Failed to start API server: {e}")
            
    def stop_server(self):
        """Stop the API server"""
        if self.running and self.server:
            self.running = False
            self.server.shutdown()
            self.server.server_close()
            if self.server_thread:
                self.server_thread.join(timeout=1.0)
            success_print("API server stopped")
            
    def _create_handler(self):
        """Create HTTP request handler"""
        class LightsAPIHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory="", **kwargs)
                
            def do_GET(self):
                if self.path == "/api/status":
                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    response = {
                        "status": "running",
                        "patterns": list(PATTERN_NAMES.keys()),
                        "led_count": LED_COUNT
                    }
                    self.wfile.write(json.dumps(response).encode())
                else:
                    self.send_response(404)
                    self.end_headers()
                    
            def do_POST(self):
                if self.path == "/api/command":
                    content_length = int(self.headers['Content-Length'])
                    post_data = self.rfile.read(content_length)
                    try:
                        command = json.loads(post_data.decode())
                        # Process command here
                        self.send_response(200)
                        self.send_header("Content-type", "application/json")
                        self.end_headers()
                        response = {"status": "success", "command": command}
                        self.wfile.write(json.dumps(response).encode())
                    except Exception as e:
                        self.send_response(400)
                        self.end_headers()
                else:
                    self.send_response(404)
                    self.end_headers()
                    
        return LightsAPIHandler

class BatchOperations:
    """Batch operations for multiple LEDs/zones"""
    
    def __init__(self, led_count: int = LED_COUNT):
        self.led_count = led_count
        self.zones: Dict[str, range] = {}
        
    def create_zone(self, zone_name: str, start: int, end: int):
        """Create a zone of LEDs"""
        if start < 0 or end > self.led_count or start >= end:
            error_print(f"Invalid zone range: {start}-{end}")
            return
            
        self.zones[zone_name] = range(start, end)
        success_print(f"Zone '{zone_name}' created: {start}-{end}")
        
    def apply_to_zone(self, zone_name: str, operation: str, params: Dict[str, Any]):
        """Apply operation to a specific zone"""
        if zone_name not in self.zones:
            error_print(f"Zone '{zone_name}' not found")
            return
            
        zone_range = self.zones[zone_name]
        info_print(f"Applying '{operation}' to zone '{zone_name}' ({len(zone_range)} LEDs)")
        
        # In real implementation, this would apply the operation to the specified LEDs
        # For now, just log the operation
        
    def apply_to_all(self, operation: str, params: Dict[str, Any]):
        """Apply operation to all LEDs"""
        info_print(f"Applying '{operation}' to all {self.led_count} LEDs")
        
    def list_zones(self) -> List[str]:
        """List all zones"""
        return list(self.zones.keys())
        
    def delete_zone(self, zone_name: str):
        """Delete a zone"""
        if zone_name in self.zones:
            del self.zones[zone_name]
            success_print(f"Zone '{zone_name}' deleted")
        else:
            error_print(f"Zone '{zone_name}' not found")

# Global instances
performance_monitor = PerformanceMonitor()
command_queue = CommandQueue()
macro_system = MacroSystem()
plugin_manager = PluginManager()
api_server = APIServer()
batch_operations = BatchOperations()

def initialize_advanced_features():
    """Initialize all advanced features"""
    performance_monitor.start_monitoring()
    command_queue.start_processing()
    info_print("Advanced features initialized")

def shutdown_advanced_features():
    """Shutdown all advanced features"""
    performance_monitor.stop_monitoring()
    command_queue.stop_processing()
    api_server.stop_server()
    info_print("Advanced features shutdown")

# Example usage and testing
if __name__ == "__main__":
    print("Testing advanced features...")
    
    # Test performance monitoring
    performance_monitor.start_monitoring()
    time.sleep(1)
    metrics = performance_monitor.get_metrics()
    print(f"Metrics: FPS={metrics.fps:.1f}, CPU={metrics.cpu_usage:.1f}%")
    performance_monitor.stop_monitoring()
    
    # Test command queue
    command_queue.add_command("set_pattern", {"pattern": "1"})
    command_queue.add_command("set_brightness", {"brightness": 200})
    command_queue.start_processing()
    time.sleep(0.5)
    command_queue.stop_processing()
    
    # Test macro system
    macro_system.start_recording("test_macro")
    macro_system.record_command("set_pattern", {"pattern": "1"})
    macro_system.record_command("set_brightness", {"brightness": 255})
    macro_system.stop_recording("test_macro")
    
    print("Advanced features test completed")
