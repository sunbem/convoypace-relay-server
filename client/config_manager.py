"""
client/config_manager.py - Persistent JSON configuration management for ConvoyPace.
Stores user settings (driver name, room code, server URL, overlay position, etc.).
"""

import os
import sys
import json
import getpass
from pathlib import Path
from typing import Dict, Any, Optional


def get_default_config_path() -> Path:
    """Determine the location for config.json (next to exe or in project root)."""
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        return exe_dir / "config.json"
    return Path(__file__).resolve().parent.parent / "config.json"


DEFAULT_CONFIG: Dict[str, Any] = {
    "driver_name": getpass.getuser() or "Driver",
    "server_url": "https://convoypace-relay-server.onrender.com",
    "last_room_code": "TRUCK-42",
    "unit": "km",  # "km" or "mi"
    "overlay_x": 40,
    "overlay_y": 40,
    "overlay_locked": True,
    "overlay_visible": True,
    "simulation_mode": False,
    "ets2_custom_path": ""
}


class ConfigManager:
    """Loads, manages, and saves persistent settings to config.json."""

    def __init__(self, config_path: Optional[Path] = None):
        self.path = config_path or get_default_config_path()
        self.data: Dict[str, Any] = dict(DEFAULT_CONFIG)
        self.load()
        # Allow environment override for cloud server URL (e.g. Render).
        # Useful when deploying the client to connect to a cloud relay.
        env_url = os.environ.get("CONVOYPACE_SERVER_URL")
        if env_url:
            self.data["server_url"] = env_url

    def load(self):
        """Load settings from disk."""
        if self.path.is_file() and self.path.stat().st_size > 0:
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        self.data.update(loaded)
            except Exception as e:
                print(f"Warning: Failed to load config from {self.path}: {e}")

    def save(self):
        """Save settings to disk atomically."""
        try:
            temp_path = self.path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
            if self.path.exists():
                self.path.unlink()
            temp_path.rename(self.path)
        except Exception as e:
            print(f"Warning: Failed to save config to {self.path}: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any, auto_save: bool = True):
        self.data[key] = value
        if auto_save:
            self.save()


if __name__ == "__main__":
    cfg = ConfigManager()
    print("Config path:", cfg.path)
    print("Loaded data:", cfg.data)
