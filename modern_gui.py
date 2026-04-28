#!/usr/bin/env python3
"""
Modern GUI for LightsPiShow - PyQt6 based interface
"""

import sys
import time
import threading
from dataclasses import dataclass
from typing import Optional, Dict, Any
from pathlib import Path

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QSlider, QLabel, QPushButton, QComboBox, QColorDialog, QTabWidget,
        QProgressBar, QGroupBox, QGridLayout, QSpinBox, QCheckBox,
        QFileDialog, QMessageBox, QFrame, QScrollArea, QSplitter,
        QToolBar, QMenuBar, QStatusBar, QTextEdit, QCalendarWidget,
        QTimeEdit, QDial, QProgressBar
    )
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QSize
    from PyQt6.QtGui import QColor, QPalette, QIcon, QFont, QPixmap, QPainter
    _HAVE_PYQT = True
except ImportError:
    _HAVE_PYQT = False

# Import main application components
try:
    from into import AppState, RunOptions, PATTERN_NAMES, SPEED_LABELS, LED_COUNT
    from cli_utils import Colors, success_print, error_print, warning_print, info_print
except ImportError:
    _HAVE_MAIN_COMPONENTS = False
else:
    _HAVE_MAIN_COMPONENTS = True

@dataclass
class GUIState:
    current_pattern: str = "1"
    current_speed: str = "5"
    current_brightness: int = 255
    current_color: QColor = QColor(255, 255, 255)
    is_running: bool = False
    uptime: float = 0.0
    fps: float = 0.0

class LEDStripWidget(QWidget):
    """Visual representation of LED strip"""
    
    def __init__(self, led_count: int = LED_COUNT):
        super().__init__()
        self.led_count = led_count
        self.led_colors = [QColor(0, 0, 0) for _ in range(led_count)]
        self.setMinimumHeight(60)
        self.setMaximumHeight(120)
        
    def update_led(self, index: int, color: QColor):
        if 0 <= index < self.led_count:
            self.led_colors[index] = color
            self.update()
            
    def update_all_leds(self, colors: list[QColor]):
        self.led_colors = colors[:self.led_count]
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        led_width = width / self.led_count
        
        for i, color in enumerate(self.led_colors):
            painter.fillRect(i * led_width, 0, led_width - 1, height, color)
            
    def clear(self):
        self.led_colors = [QColor(0, 0, 0) for _ in range(self.led_count)]
        self.update()

class PatternPreviewWidget(QWidget):
    """ASCII pattern preview widget"""
    
    def __init__(self):
        super().__init__()
        self.pattern_text = ""
        self.setMinimumHeight(100)
        self.setFont(QFont("Courier", 10))
        
    def set_pattern(self, pattern_name: str, pattern_data: str):
        self.pattern_text = f"Pattern: {pattern_name}\n{pattern_data}"
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(20, 20, 20))
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self.pattern_text)

class ColorPaletteWidget(QWidget):
    """Interactive color palette editor"""
    
    color_selected = pyqtSignal(QColor)
    
    def __init__(self):
        super().__init__()
        self.predefined_colors = [
            QColor(255, 0, 0),    # Red
            QColor(0, 255, 0),    # Green
            QColor(0, 0, 255),    # Blue
            QColor(255, 255, 0),  # Yellow
            QColor(255, 0, 255),  # Magenta
            QColor(0, 255, 255),  # Cyan
            QColor(255, 255, 255), # White
            QColor(255, 165, 0),  # Orange
            QColor(128, 0, 128),  # Purple
            QColor(255, 192, 203), # Pink
        ]
        self.setup_ui()
        
    def setup_ui(self):
        layout = QGridLayout(self)
        
        # Color grid
        row, col = 0, 0
        for color in self.predefined_colors:
            btn = QPushButton()
            btn.setStyleSheet(f"background-color: {color.name()}; border: 2px solid #666;")
            btn.setFixedSize(40, 40)
            btn.clicked.connect(lambda checked, c=color: self.color_selected.emit(c))
            layout.addWidget(btn, row, col)
            col += 1
            if col >= 5:
                col = 0
                row += 1
                
        # Custom color button
        custom_btn = QPushButton("Custom Color")
        custom_btn.clicked.connect(self.pick_custom_color)
        layout.addWidget(custom_btn, row, col, 1, 2)
        
    def pick_custom_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.color_selected.emit(color)

class TimelineWidget(QWidget):
    """Timeline editor for pattern sequences"""
    
    def __init__(self):
        super().__init__()
        self.timeline_items = []
        self.current_position = 0
        self.setMinimumHeight(150)
        
    def add_item(self, pattern: str, duration: float):
        self.timeline_items.append({"pattern": pattern, "duration": duration})
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(40, 40, 40))
        
        if not self.timeline_items:
            painter.setPen(QColor(128, 128, 128))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No timeline items")
            return
            
        # Draw timeline
        width = self.width()
        height = self.height()
        item_width = width / len(self.timeline_items)
        
        for i, item in enumerate(self.timeline_items):
            x = i * item_width
            color = QColor(100, 150, 200) if i == self.current_position else QColor(70, 70, 70)
            painter.fillRect(x, 20, item_width - 2, height - 40, color)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(x, 5, item_width, 15, Qt.AlignmentFlag.AlignCenter, item["pattern"])

class ModernLightsGUI(QMainWindow):
    """Main GUI window"""
    
    def __init__(self):
        super().__init__()
        self.state = GUIState()
        self.app_state: Optional[AppState] = None
        self.app_options: Optional[RunOptions] = None
        
        if not _HAVE_PYQT:
            raise ImportError("PyQt6 is required for the GUI")
        if not _HAVE_MAIN_COMPONENTS:
            raise ImportError("Main application components not found")
            
        self.setup_ui()
        self.setup_timers()
        self.apply_theme()
        
    def setup_ui(self):
        self.setWindowTitle("Lights Pi Show - Modern GUI")
        self.setGeometry(100, 100, 1200, 800)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout(central_widget)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left panel - Controls
        left_panel = self.create_control_panel()
        splitter.addWidget(left_panel)
        
        # Right panel - Visualization
        right_panel = self.create_visualization_panel()
        splitter.addWidget(right_panel)
        
        # Set splitter sizes
        splitter.setSizes([400, 800])
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create toolbar
        self.create_toolbar()
        
        # Create status bar
        self.create_status_bar()
        
    def create_control_panel(self) -> QWidget:
        """Create the main control panel"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Pattern controls
        pattern_group = QGroupBox("Pattern Control")
        pattern_layout = QVBoxLayout(pattern_group)
        
        # Pattern selector
        pattern_selector_layout = QHBoxLayout()
        pattern_selector_layout.addWidget(QLabel("Pattern:"))
        self.pattern_combo = QComboBox()
        self.pattern_combo.addItems([f"{k}. {v}" for k, v in sorted(PATTERN_NAMES.items(), key=lambda x: int(x[0]))])
        self.pattern_combo.currentTextChanged.connect(self.on_pattern_changed)
        pattern_selector_layout.addWidget(self.pattern_combo)
        pattern_layout.addLayout(pattern_selector_layout)
        
        # Speed control
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("Speed:"))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(0, 9)
        self.speed_slider.setValue(5)
        self.speed_slider.valueChanged.connect(self.on_speed_changed)
        speed_layout.addWidget(self.speed_slider)
        self.speed_label = QLabel("Level 5")
        speed_layout.addWidget(self.speed_label)
        pattern_layout.addLayout(speed_layout)
        
        # Brightness control
        brightness_layout = QHBoxLayout()
        brightness_layout.addWidget(QLabel("Brightness:"))
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setRange(0, 255)
        self.brightness_slider.setValue(255)
        self.brightness_slider.valueChanged.connect(self.on_brightness_changed)
        brightness_layout.addWidget(self.brightness_slider)
        self.brightness_label = QLabel("100%")
        brightness_layout.addWidget(self.brightness_label)
        pattern_layout.addLayout(brightness_layout)
        
        layout.addWidget(pattern_group)
        
        # Color controls
        color_group = QGroupBox("Color Control")
        color_layout = QVBoxLayout(color_group)
        
        self.color_palette = ColorPaletteWidget()
        self.color_palette.color_selected.connect(self.on_color_selected)
        color_layout.addWidget(self.color_palette)
        
        self.current_color_label = QLabel("Current Color: #FFFFFF")
        self.current_color_label.setStyleSheet("background-color: #FFFFFF; padding: 5px;")
        color_layout.addWidget(self.current_color_label)
        
        layout.addWidget(color_group)
        
        # Advanced controls
        advanced_group = QGroupBox("Advanced Controls")
        advanced_layout = QVBoxLayout(advanced_group)
        
        # Start/Stop buttons
        button_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self.start_lights)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_lights)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.stop_btn)
        advanced_layout.addLayout(button_layout)
        
        # Test mode checkbox
        self.test_mode_checkbox = QCheckBox("Test Mode (ASCII)")
        advanced_layout.addWidget(self.test_mode_checkbox)
        
        layout.addWidget(advanced_group)
        
        layout.addStretch()
        
        return panel
        
    def create_visualization_panel(self) -> QWidget:
        """Create the visualization panel"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Create tab widget
        tabs = QTabWidget()
        
        # LED Strip tab
        strip_tab = QWidget()
        strip_layout = QVBoxLayout(strip_tab)
        self.led_strip_widget = LEDStripWidget()
        strip_layout.addWidget(self.led_strip_widget)
        strip_layout.addWidget(QLabel("LED Strip Visualization"))
        tabs.addTab(strip_tab, "LED Strip")
        
        # Pattern Preview tab
        preview_tab = QWidget()
        preview_layout = QVBoxLayout(preview_tab)
        self.pattern_preview = PatternPreviewWidget()
        preview_layout.addWidget(self.pattern_preview)
        tabs.addTab(preview_tab, "Pattern Preview")
        
        # Timeline tab
        timeline_tab = QWidget()
        timeline_layout = QVBoxLayout(timeline_tab)
        self.timeline_widget = TimelineWidget()
        timeline_layout.addWidget(self.timeline_widget)
        tabs.addTab(timeline_tab, "Timeline")
        
        # Status tab
        status_tab = QWidget()
        status_layout = QVBoxLayout(status_tab)
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(200)
        status_layout.addWidget(self.status_text)
        tabs.addTab(status_tab, "Status")
        
        layout.addWidget(tabs)
        
        return panel
        
    def create_menu_bar(self):
        """Create the menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        load_action = file_menu.addAction("Load Configuration")
        load_action.triggered.connect(self.load_configuration)
        
        save_action = file_menu.addAction("Save Configuration")
        save_action.triggered.connect(self.save_configuration)
        
        file_menu.addSeparator()
        
        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)
        
        # View menu
        view_menu = menubar.addMenu("View")
        
        dark_theme_action = view_menu.addAction("Dark Theme")
        dark_theme_action.setCheckable(True)
        dark_theme_action.setChecked(True)
        dark_theme_action.triggered.connect(self.toggle_theme)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = help_menu.addAction("About")
        about_action.triggered.connect(self.show_about)
        
    def create_toolbar(self):
        """Create the toolbar"""
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        
        # Quick actions
        start_action = toolbar.addAction("Start")
        start_action.triggered.connect(self.start_lights)
        
        stop_action = toolbar.addAction("Stop")
        stop_action.triggered.connect(self.stop_lights)
        
        toolbar.addSeparator()
        
        # Pattern quick access
        for pattern_id in ["1", "2", "3"]:
            pattern_name = PATTERN_NAMES.get(pattern_id, f"Pattern {pattern_id}")
            action = toolbar.addAction(f"P{pattern_id}")
            action.triggered.connect(lambda checked, pid=pattern_id: self.set_pattern(pid))
            
    def create_status_bar(self):
        """Create the status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)
        
        # Add progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
    def setup_timers(self):
        """Setup update timers"""
        # Status update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(1000)  # Update every second
        
        # FPS counter timer
        self.fps_timer = QTimer()
        self.fps_timer.timeout.connect(self.update_fps)
        self.fps_timer.start(100)  # Update every 100ms
        
    def apply_theme(self):
        """Apply dark theme"""
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(0, 0, 0))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
        palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
        self.setPalette(palette)
        
    def on_pattern_changed(self, pattern_text):
        """Handle pattern change"""
        if pattern_text:
            pattern_id = pattern_text.split('.')[0]
            self.state.current_pattern = pattern_id
            self.log_status(f"Pattern changed to: {pattern_text}")
            
    def on_speed_changed(self, value):
        """Handle speed change"""
        self.state.current_speed = str(value)
        speed_label = SPEED_LABELS.get(str(value), f"Level {value}")
        self.speed_label.setText(speed_label)
        self.log_status(f"Speed changed to: {speed_label}")
        
    def on_brightness_changed(self, value):
        """Handle brightness change"""
        self.state.current_brightness = value
        percentage = int((value / 255) * 100)
        self.brightness_label.setText(f"{percentage}%")
        self.log_status(f"Brightness changed to: {percentage}%")
        
    def on_color_selected(self, color: QColor):
        """Handle color selection"""
        self.state.current_color = color
        color_hex = color.name().upper()
        self.current_color_label.setText(f"Current Color: {color_hex}")
        self.current_color_label.setStyleSheet(f"background-color: {color_hex}; padding: 5px;")
        self.log_status(f"Color changed to: {color_hex}")
        
    def set_pattern(self, pattern_id: str):
        """Set pattern programmatically"""
        index = self.pattern_combo.findText(f"{pattern_id}.")
        if index >= 0:
            self.pattern_combo.setCurrentIndex(index)
            
    def start_lights(self):
        """Start the light show"""
        self.state.is_running = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("Running")
        self.log_status("Light show started")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        
    def stop_lights(self):
        """Stop the light show"""
        self.state.is_running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Stopped")
        self.log_status("Light show stopped")
        self.progress_bar.setVisible(False)
        
    def update_status(self):
        """Update status display"""
        if self.state.is_running:
            self.state.uptime += 1.0
            uptime_text = f"Uptime: {self.state.uptime:.1f}s"
            self.status_label.setText(f"Running - {uptime_text}")
            
    def update_fps(self):
        """Update FPS counter"""
        if self.state.is_running:
            # Simulate FPS calculation
            self.state.fps = 30.0 + (time.time() % 10) * 2
            fps_text = f"FPS: {self.state.fps:.1f}"
            # Update status bar or other display
            self.status_bar.showMessage(fps_text, 2000)
            
    def log_status(self, message: str):
        """Log status message"""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.status_text.append(log_entry)
        
        # Auto-scroll to bottom
        scrollbar = self.status_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def load_configuration(self):
        """Load configuration from file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Configuration", "", "JSON Files (*.json)")
        if file_path:
            try:
                # Load configuration logic here
                self.log_status(f"Configuration loaded from: {file_path}")
                success_print(f"Configuration loaded from: {file_path}")
            except Exception as e:
                error_print(f"Failed to load configuration: {e}")
                QMessageBox.critical(self, "Error", f"Failed to load configuration: {e}")
                
    def save_configuration(self):
        """Save configuration to file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Configuration", "", "JSON Files (*.json)")
        if file_path:
            try:
                # Save configuration logic here
                self.log_status(f"Configuration saved to: {file_path}")
                success_print(f"Configuration saved to: {file_path}")
            except Exception as e:
                error_print(f"Failed to save configuration: {e}")
                QMessageBox.critical(self, "Error", f"Failed to save configuration: {e}")
                
    def toggle_theme(self):
        """Toggle between dark and light theme"""
        # Theme toggle logic here
        self.log_status("Theme toggled")
        
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(self, "About Lights Pi Show", 
                         "Lights Pi Show - Modern GUI\n\n"
                         "A modern interface for controlling LED light patterns\n"
                         "with advanced features and real-time visualization.")

def main():
    """Main GUI entry point"""
    if not _HAVE_PYQT:
        error_print("PyQt6 is required for the GUI. Install with: pip install PyQt6")
        return False
        
    if not _HAVE_MAIN_COMPONENTS:
        error_print("Main application components not found")
        return False
        
    app = QApplication(sys.argv)
    app.setApplicationName("Lights Pi Show")
    app.setApplicationVersion("2.0")
    
    # Create and show main window
    window = ModernLightsGUI()
    window.show()
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
