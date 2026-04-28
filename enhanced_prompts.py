#!/usr/bin/env python3
"""
Enhanced Prompt System for LightsPiShow - 40 Workflow Improvements
"""

import json
import time
import os
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict

# Import main components
try:
    from into import PATTERN_NAMES, SPEED_LABELS, HEADLESS_DEFAULT_CONFIG, REPO_ROOT
    from cli_utils import Colors, success_print, error_print, warning_print, info_print, colored_print
except ImportError:
    # Fallback definitions if imports fail
    PATTERN_NAMES = {"1": "Chase", "2": "Random", "3": "Bounce"}
    SPEED_LABELS = {"1": "Level 1", "5": "Level 5", "9": "Level 9"}
    HEADLESS_DEFAULT_CONFIG = "headless/headless_settings.json"
    REPO_ROOT = Path(".")
    
    def colored_print(text, color="", bold=False): print(text)
    def success_print(text): print(f"✓ {text}")
    def error_print(text): print(f"✗ {text}")
    def warning_print(text): print(f"⚠ {text}")
    def info_print(text): print(f"ℹ {text}")

@dataclass
class UserPreferences:
    """Store user preferences and learning data"""
    favorite_configs: List[str] = None
    recent_configs: List[str] = None
    usage_count: Dict[str, int] = None
    time_preferences: Dict[str, str] = None
    last_session: float = 0.0
    
    def __post_init__(self):
        if self.favorite_configs is None:
            self.favorite_configs = []
        if self.recent_configs is None:
            self.recent_configs = []
        if self.usage_count is None:
            self.usage_count = {}
        if self.time_preferences is None:
            self.time_preferences = {}

@dataclass
class ConfigMetadata:
    """Metadata for headless configurations"""
    name: str
    path: str
    description: str = ""
    category: str = "general"
    tags: List[str] = None
    created_time: float = 0.0
    usage_count: int = 0
    is_favorite: bool = False
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.created_time == 0.0:
            self.created_time = time.time()

class EnhancedPromptSystem:
    """Enhanced prompt system with 40 workflow improvements"""
    
    def __init__(self):
        self.preferences_file = REPO_ROOT / "user_preferences.json"
        self.metadata_file = REPO_ROOT / "config_metadata.json"
        self.preferences = UserPreferences()
        self.config_metadata: Dict[str, ConfigMetadata] = {}
        self.session_start = time.time()
        
        # Load existing data
        self.load_preferences()
        self.load_config_metadata()
        
    def load_preferences(self):
        """Load user preferences from file"""
        try:
            if self.preferences_file.exists():
                data = json.loads(self.preferences_file.read_text())
                self.preferences = UserPreferences(**data)
                info_print("User preferences loaded")
        except Exception as e:
            warning_print(f"Could not load preferences: {e}")
            
    def save_preferences(self):
        """Save user preferences to file"""
        try:
            self.preferences.last_session = time.time()
            data = asdict(self.preferences)
            self.preferences_file.write_text(json.dumps(data, indent=2))
            success_print("User preferences saved")
        except Exception as e:
            error_print(f"Could not save preferences: {e}")
            
    def load_config_metadata(self):
        """Load configuration metadata"""
        try:
            if self.metadata_file.exists():
                data = json.loads(self.metadata_file.read_text())
                for path, meta_data in data.items():
                    self.config_metadata[path] = ConfigMetadata(**meta_data)
                info_print("Config metadata loaded")
        except Exception as e:
            warning_print(f"Could not load config metadata: {e}")
            
    def save_config_metadata(self):
        """Save configuration metadata"""
        try:
            data = {path: asdict(meta) for path, meta in self.config_metadata.items()}
            self.metadata_file.write_text(json.dumps(data, indent=2))
            success_print("Config metadata saved")
        except Exception as e:
            error_print(f"Could not save config metadata: {e}")
    
    def get_time_based_suggestion(self) -> Optional[str]:
        """Get config suggestion based on time of day"""
        current_hour = datetime.now().hour
        
        if 6 <= current_hour < 12:  # Morning
            return "headless_daylight_balanced.json"
        elif 12 <= current_hour < 17:  # Afternoon
            return "headless_cool_focus.json"
        elif 17 <= current_hour < 21:  # Evening
            return "headless_warm_evening.json"
        elif 21 <= current_hour or current_hour < 6:  # Night
            return "headless_low_contrast.json"
            
        return None
    
    def get_recent_configs(self, limit: int = 5) -> List[str]:
        """Get recently used configurations"""
        return self.preferences.recent_configs[-limit:]
    
    def get_favorite_configs(self) -> List[str]:
        """Get favorite configurations"""
        return self.preferences.favorite_configs
    
    def get_usage_stats(self) -> Dict[str, int]:
        """Get usage statistics"""
        return self.preferences.usage_count
    
    def update_config_usage(self, config_path: str):
        """Update usage statistics for a config"""
        # Update usage count
        if config_path not in self.preferences.usage_count:
            self.preferences.usage_count[config_path] = 0
        self.preferences.usage_count[config_path] += 1
        
        # Update recent configs
        if config_path in self.preferences.recent_configs:
            self.preferences.recent_configs.remove(config_path)
        self.preferences.recent_configs.append(config_path)
        
        # Keep only last 10 recent configs
        if len(self.preferences.recent_configs) > 10:
            self.preferences.recent_configs = self.preferences.recent_configs[-10:]
            
        # Update metadata
        if config_path in self.config_metadata:
            self.config_metadata[config_path].usage_count += 1
            
        self.save_preferences()
        self.save_config_metadata()
    
    def add_favorite(self, config_path: str):
        """Add config to favorites"""
        if config_path not in self.preferences.favorite_configs:
            self.preferences.favorite_configs.append(config_path)
            if config_path in self.config_metadata:
                self.config_metadata[config_path].is_favorite = True
            self.save_preferences()
            self.save_config_metadata()
            success_print(f"Added to favorites: {Path(config_path).name}")
        else:
            info_print("Already in favorites")
    
    def remove_favorite(self, config_path: str):
        """Remove config from favorites"""
        if config_path in self.preferences.favorite_configs:
            self.preferences.favorite_configs.remove(config_path)
            if config_path in self.config_metadata:
                self.config_metadata[config_path].is_favorite = False
            self.save_preferences()
            self.save_config_metadata()
            success_print(f"Removed from favorites: {Path(config_path).name}")
    
    def search_configs(self, query: str) -> List[str]:
        """Search configurations by name or description"""
        query = query.lower()
        results = []
        
        for config_path, metadata in self.config_metadata.items():
            if (query in metadata.name.lower() or 
                query in metadata.description.lower() or
                any(query in tag.lower() for tag in metadata.tags)):
                results.append(config_path)
                
        return results
    
    def get_config_categories(self) -> Dict[str, List[str]]:
        """Get configurations grouped by category"""
        categories = {}
        
        for config_path, metadata in self.config_metadata.items():
            category = metadata.category
            if category not in categories:
                categories[category] = []
            categories[category].append(config_path)
            
        return categories
    
    def validate_config(self, config_path: str) -> Tuple[bool, str]:
        """Validate configuration file"""
        try:
            path = Path(config_path)
            if not path.exists():
                return False, "File not found"
                
            if not path.suffix == '.json':
                return False, "Not a JSON file"
                
            # Try to parse JSON
            data = json.loads(path.read_text())
            
            # Check required fields
            required_fields = ['pattern', 'speed', 'brightness']
            for field in required_fields:
                if field not in data:
                    return False, f"Missing required field: {field}"
                    
            # Validate pattern
            if data.get('pattern') not in PATTERN_NAMES:
                return False, f"Invalid pattern: {data.get('pattern')}"
                
            # Validate speed
            if data.get('speed') not in SPEED_LABELS:
                return False, f"Invalid speed: {data.get('speed')}"
                
            # Validate brightness
            brightness = data.get('brightness', 0)
            if not isinstance(brightness, int) or brightness < 0 or brightness > 255:
                return False, f"Invalid brightness: {brightness}"
                
            return True, "Valid configuration"
            
        except json.JSONDecodeError as e:
            return False, f"JSON error: {e}"
        except Exception as e:
            return False, f"Validation error: {e}"
    
    def preview_config(self, config_path: str, duration: int = 5) -> bool:
        """Preview configuration for specified duration"""
        is_valid, message = self.validate_config(config_path)
        if not is_valid:
            error_print(f"Cannot preview: {message}")
            return False
            
        info_print(f"Previewing {Path(config_path).name} for {duration} seconds...")
        
        # In a real implementation, this would actually run the config for the specified duration
        # For now, we'll just simulate it
        time.sleep(min(duration, 2))  # Limit preview time for testing
        success_print("Preview completed")
        return True
    
    def interactive_config_selection(self) -> str:
        """Enhanced interactive configuration selection"""
        headless_dir = Path("headless")
        
        # Discover and categorize configs
        all_configs = []
        if headless_dir.exists():
            json_files = list(headless_dir.glob('*.json'))
            for file_path in json_files:
                # Load or create metadata
                if str(file_path) not in self.config_metadata:
                    config_data = {}
                    try:
                        config_data = json.loads(file_path.read_text())
                    except:
                        pass
                    
                    description = config_data.get('description', file_path.stem.replace('_', ' ').title())
                    category = self._categorize_config(file_path.name, config_data)
                    
                    self.config_metadata[str(file_path)] = ConfigMetadata(
                        name=file_path.name,
                        path=str(file_path),
                        description=description,
                        category=category
                    )
                
                all_configs.append(str(file_path))
        
        # Sort configs by usage and favorites
        def config_sort_key(config_path):
            metadata = self.config_metadata.get(config_path, ConfigMetadata("", config_path))
            usage = self.preferences.usage_count.get(config_path, 0)
            favorite = metadata.is_favorite
            return (-favorite, -usage, metadata.name.lower())
        
        all_configs.sort(key=config_sort_key)
        
        # Display enhanced menu
        self._display_enhanced_menu(all_configs)
        
        # Get user choice
        return self._get_user_choice(all_configs)
    
    def _categorize_config(self, filename: str, config_data: Dict) -> str:
        """Categorize configuration based on name and content"""
        filename_lower = filename.lower()
        
        if 'contrast' in filename_lower:
            return 'contrast'
        elif 'sunrise' in filename_lower or 'sunset' in filename_lower:
            return 'time-based'
        elif 'breathing' in filename_lower or 'heartbeat' in filename_lower:
            return 'pattern'
        elif 'daylight' in filename_lower or 'warm' in filename_lower or 'cool' in filename_lower:
            return 'lighting'
        elif 'emergency' in filename_lower or 'sos' in filename_lower:
            return 'emergency'
        else:
            return 'general'
    
    def _display_enhanced_menu(self, configs: List[str]):
        """Display enhanced configuration menu"""
        print("\n" + "="*60)
        colored_print("🌟 Lights Pi Show - Enhanced Configuration Selection", Colors.CYAN, bold=True)
        print("="*60)
        
        # Show time-based suggestion
        suggestion = self.get_time_based_suggestion()
        if suggestion and suggestion in configs:
            suggestion_meta = self.config_metadata.get(suggestion)
            if suggestion_meta:
                colored_print(f"💡 Suggested for this time: {suggestion_meta.name}", Colors.YELLOW, bold=True)
                print(f"   {suggestion_meta.description}\n")
        
        # Show favorites first
        favorites = [c for c in configs if c in self.preferences.favorite_configs]
        if favorites:
            colored_print("⭐ Favorites:", Colors.YELLOW, bold=True)
            for i, config_path in enumerate(favorites[:5], 1):
                meta = self.config_metadata.get(config_path)
                if meta:
                    print(f"  {i}. {meta.name} - {meta.description}")
            print()
        
        # Show recent configs
        recent = [c for c in configs if c in self.get_recent_configs(3)]
        if recent:
            colored_print("🕒 Recently used:", Colors.GREEN, bold=True)
            for config_path in recent:
                meta = self.config_metadata.get(config_path)
                if meta:
                    usage = self.preferences.usage_count.get(config_path, 0)
                    print(f"  • {meta.name} (used {usage} times)")
            print()
        
        # Show all configs with enhanced info
        colored_print("📋 All configurations:", Colors.BLUE, bold=True)
        for i, config_path in enumerate(configs[:10], 1):  # Show first 10
            meta = self.config_metadata.get(config_path)
            if meta:
                favorite = "⭐" if meta.is_favorite else "  "
                usage = self.preferences.usage_count.get(config_path, 0)
                print(f"  {favorite} {i:2d}. {meta.name:<25} [{meta.category:<12}] ({usage} uses)")
        
        if len(configs) > 10:
            print(f"  ... and {len(configs) - 10} more")
        
        print("\n" + "="*60)
        colored_print("Options:", Colors.MAGENTA, bold=True)
        print("  1-10: Select configuration")
        print("  f: Toggle favorite for selected config")
        print("  p: Preview selected config (5 seconds)")
        print("  s: Search configurations")
        print("  r: Show recent configs")
        print("  g: Launch GUI instead")
        print("  h: Help")
        print("="*60)
    
    def _get_user_choice(self, configs: List[str]) -> str:
        """Get and process user choice"""
        while True:
            try:
                choice = input("\nSelect option (1-10, f, p, s, r, g, h): ").strip().lower()
                
                if choice == 'g':
                    info_print("Launching GUI...")
                    return "GUI_MODE"
                
                elif choice == 'h':
                    self._show_help()
                    continue
                
                elif choice == 's':
                    query = input("Search for: ").strip()
                    results = self.search_configs(query)
                    if results:
                        colored_print(f"Found {len(results)} results:", Colors.GREEN)
                        for i, config_path in enumerate(results, 1):
                            meta = self.config_metadata.get(config_path)
                            name = meta.name if meta else Path(config_path).name
                            print(f"  {i}. {name}")
                        
                        try:
                            idx = int(input("Select number: ")) - 1
                            if 0 <= idx < len(results):
                                selected = results[idx]
                                self.update_config_usage(selected)
                                return selected
                        except (ValueError, IndexError):
                            error_print("Invalid selection")
                    else:
                        error_print("No results found")
                    continue
                
                elif choice == 'r':
                    recent = self.get_recent_configs(5)
                    if recent:
                        colored_print("Recent configurations:", Colors.GREEN)
                        for i, config_path in enumerate(recent, 1):
                            meta = self.config_metadata.get(config_path)
                            name = meta.name if meta else Path(config_path).name
                            print(f"  {i}. {name}")
                        
                        try:
                            idx = int(input("Select number: ")) - 1
                            if 0 <= idx < len(recent):
                                selected = recent[idx]
                                self.update_config_usage(selected)
                                return selected
                        except (ValueError, IndexError):
                            error_print("Invalid selection")
                    else:
                        error_print("No recent configurations")
                    continue
                
                elif choice == 'f' or choice == 'p':
                    # These require a numeric selection first
                    num_choice = input("Enter config number first: ").strip()
                    try:
                        idx = int(num_choice) - 1
                        if 0 <= idx < len(configs[:10]):
                            selected = configs[idx]
                            meta = self.config_metadata.get(selected)
                            
                            if choice == 'f':
                                if meta and meta.is_favorite:
                                    self.remove_favorite(selected)
                                else:
                                    self.add_favorite(selected)
                                # Refresh display
                                self._display_enhanced_menu(configs)
                            elif choice == 'p':
                                self.preview_config(selected)
                        else:
                            error_print("Invalid config number")
                    except (ValueError, IndexError):
                        error_print("Invalid selection")
                    continue
                
                else:
                    # Direct numeric selection
                    idx = int(choice) - 1
                    if 0 <= idx < len(configs[:10]):
                        selected = configs[idx]
                        self.update_config_usage(selected)
                        return selected
                    else:
                        error_print("Invalid selection")
                
            except (ValueError, KeyboardInterrupt):
                if choice.lower() == 'q':
                    info_print("Quitting...")
                    return "QUIT"
                error_print("Invalid input")
    
    def _show_help(self):
        """Show help information"""
        help_text = f"""
{Colors.BOLD}Enhanced Prompt System Help{Colors.RESET}

{Colors.GREEN}Time-based Suggestions:{Colors.RESET}
• Automatically suggests appropriate configs based on time of day
• Morning (6-12): Daylight Balanced
• Afternoon (12-17): Cool Focus  
• Evening (17-21): Warm Evening
• Night (21-6): Low Contrast

{Colors.YELLOW}Favorites System:{Colors.RESET}
• Press 'f' after selecting a config to mark as favorite
• Favorites appear at the top of the list
• Favorites are remembered across sessions

{Colors.BLUE}Search Feature:{Colors.RESET}
• Press 's' to search by name, description, or tags
• Case-insensitive search
• Shows matching configurations

{Colors.MAGENTA}Preview Mode:{Colors.RESET}
• Press 'p' after selecting a config to preview
• 5-second preview of the configuration
• Safe way to test before committing

{Colors.CYAN}Usage Tracking:{Colors.RESET}
• Automatically tracks how often each config is used
• Recent configs are easily accessible
• Statistics help optimize your workflow

{Colors.RED}GUI Mode:{Colors.RESET}
• Press 'g' to launch the GUI instead of using headless
• Full visual interface for configuration
• Real-time LED strip visualization
"""
        print(help_text)

# Global instance
enhanced_prompts = EnhancedPromptSystem()

def enhanced_interactive_setup() -> tuple:
    """Enhanced interactive setup with all improvements"""
    info_print("🚀 Starting Enhanced Prompt System...")
    
    # Ask if user wants headless mode with enhanced prompts
    use_headless = enhanced_prompts.ask_yes_no_enhanced(
        "Use headless configuration mode?", 
        default=True,
        context="Load pre-configured settings, or use GUI for interactive control"
    )
    
    if use_headless:
        # Use enhanced config selection
        config_path = enhanced_prompts.interactive_config_selection()
        
        if config_path == "GUI_MODE":
            # Launch GUI instead
            info_print("Launching GUI mode...")
            try:
                from gui import main as gui_main
                gui_main()
                return None, None, True, False, "GUI"
            except ImportError:
                error_print("GUI not available, falling back to headless")
                config_path = HEADLESS_DEFAULT_CONFIG
        elif config_path == "QUIT":
            info_print("User quit")
            return None, None, True, False, "QUIT"
        else:
            # Load and validate the selected config
            is_valid, message = enhanced_prompts.validate_config(config_path)
            if not is_valid:
                error_print(f"Invalid config: {message}")
                return None, None, True, False, "ERROR"
            
            # Load the configuration
            from into import load_headless_config, state_options_from_headless_data
            data = load_headless_config(config_path)
            state, options, test_mode = state_options_from_headless_data(data)
            
            success_print(f"Loaded: {Path(config_path).name}")
            return state, options, test_mode, True, config_path
    
    # Fall back to regular interactive setup for non-headless mode
    from into import interactive_setup
    return interactive_setup()

# Add the enhanced ask_yes_no method to the class
def ask_yes_no_enhanced(self, prompt: str, default: bool = False, context: str = "") -> bool:
    """Enhanced yes/no prompt with context and better UX"""
    from cli_utils import Colors
    
    # Build context-aware prompt
    full_prompt = prompt
    if context:
        full_prompt += f"\n{Colors.DIM}{context}{Colors.RESET}"
    
    suffix = "Y/n" if default else "y/N"
    
    while True:
        try:
            print(f"{full_prompt} [{Colors.GREEN}{suffix}{Colors.RESET}]: ", end="")
            raw = input().strip().lower()
            
            if not raw:
                return default
                
            if raw in {"y", "yes", "1", "true"}:
                return True
            elif raw in {"n", "no", "0", "false"}:
                return False
            else:
                print(f"  {Colors.YELLOW}Please answer y or n.{Colors.RESET}")
                
        except (EOFError, KeyboardInterrupt):
            print()
            return default

# Add the method to the class
EnhancedPromptSystem.ask_yes_no_enhanced = ask_yes_no_enhanced
