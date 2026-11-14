"""
client/main.py - Main entry point for ConvoyPace (ETS2 Convoy Live Distance Overlay & Tracker).
Coordinates telemetry reading, network synchronization, global hotkeys, and GUI.
"""

import os
import sys
import time
import tkinter as tk
from pathlib import Path
from typing import Optional

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from client.config_manager import ConfigManager
from client.telemetry_reader import TelemetryReader
from client.network_client import NetworkClient
from client.overlay_window import OverlayWindow
from client.control_panel import ControlPanel
from client.win32_utils import GlobalHotkeyListener


class ConvoyPaceApp:
    """Master application coordinator."""

    def __init__(self, config: Optional[ConfigManager] = None):
        # 1. Load persistent configuration
        self.config = config or ConfigManager()

        # 1b. Enable per-monitor DPI awareness so Tk geometry and Win32 HWND
        # coordinates stay in sync on scaled displays (e.g. 4K / 150%).
        try:
            from client.win32_utils import set_dpi_awareness
            set_dpi_awareness()
        except Exception:
            pass

        # 2. Initialize Telemetry Engine
        sim_mode = bool(self.config.get("simulation_mode", False))
        self.telemetry_reader = TelemetryReader(simulation_mode=sim_mode)

        # 3. Create Tkinter Root Window (Control Panel)
        self.root = tk.Tk()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # 4. Create In-Game Overlay Window
        self.overlay = OverlayWindow(
            config=self.config,
            on_lock_toggled=self._on_overlay_lock_changed,
            on_visibility_toggled=self._on_overlay_vis_changed
        )

        # 5. Initialize Network Client (cloud relay only)
        # The server_url is read from config.json or CONVOYPACE_SERVER_URL env var.
        # Local server hosting has been removed; the client always connects to the
        # cloud relay server (Render) when CONVOYPACE_SERVER_URL is set, or falls back
        # to the URL stored in config.json.
        server_url = self.config.get("server_url", "https://convoypace-relay-server.onrender.com")
        room_code = self.config.get("last_room_code", "TRUCK-42")
        driver_name = self.config.get("driver_name", "Driver")

        self.net_client = NetworkClient(
            server_url=server_url,
            room_code=room_code,
            driver_name=driver_name,
            on_leaderboard_update=self._on_leaderboard_received,
            on_status_change=self._on_network_status_changed
        )

        # 6. Initialize Control Panel GUI
        self.control_panel = ControlPanel(
            root=self.root,
            config=self.config,
            on_join_room=self._on_join_room,
            on_unit_changed=self._on_unit_changed,
            on_simulation_toggled=self._on_simulation_toggled,
            on_toggle_overlay_visibility=self.overlay.toggle_visibility,
            on_toggle_overlay_lock=self.overlay.toggle_lock
        )

        # 7. Initialize Global Hotkey Listener (Safe: Ctrl+F9/Ins/F11 for Visibility, Ctrl+F10/Home for Lock/Unlock)
        self.hotkeys = GlobalHotkeyListener(
            on_toggle_visibility=self._handle_visibility_hotkey,
            on_toggle_lock=self._handle_lock_hotkey
        )

        self._running = True

    def start(self):
        """Start all background loops and run the Tkinter mainloop."""
        # Connect telemetry reader
        self.telemetry_reader.connect()

        # Start network worker thread
        self.net_client.start()

        # Start global hotkeys
        self.hotkeys.start()

        # Start periodic telemetry polling loop (1000ms / 1 second)
        self.root.after(500, self._telemetry_tick)

        # Run Tkinter loop
        self.root.mainloop()

    def _telemetry_tick(self):
        """Executed every 1000ms on the main GUI thread."""
        if not self._running:
            return

        data, status = self.telemetry_reader.read()

        # Update Control Panel Status Bar
        is_conn = (status == "Live Connected" or status == "Simulation Active")
        self.control_panel.set_telemetry_status(status, is_conn)

        if data:
            # Send to network worker
            self.net_client.update_telemetry(data.to_dict())

        # Schedule next tick
        self.root.after(1000, self._telemetry_tick)

    def _on_leaderboard_received(self, data):
        """Thread-safe callback from network client with new leaderboard."""
        if self._running:
            self.root.after(0, lambda: self.overlay.update_leaderboard(data))

    def _on_network_status_changed(self, text: str, connected: bool):
        """Thread-safe callback from network client with connection status."""
        if self._running:
            self.root.after(0, lambda: self.control_panel.set_network_status(text, connected))
            self.root.after(0, lambda: self.overlay.set_network_connected(connected))

    def _on_join_room(self, room_code: str, driver_name: str, server_url: Optional[str] = None):
        """User clicked Create or Join room."""
        target_url = server_url or self.config.get("server_url", "https://convoypace-relay-server.onrender.com")
        clean_name = driver_name.strip() or "Driver"
        self.overlay.set_driver_name(clean_name)
        self.net_client.stop()
        self.net_client = NetworkClient(
            server_url=target_url,
            room_code=room_code,
            driver_name=clean_name,
            on_leaderboard_update=self._on_leaderboard_received,
            on_status_change=self._on_network_status_changed
        )
        self.net_client.start()
        # Immediately read and push initial telemetry so the driver appears in the room instantly
        self.root.after(100, self._telemetry_tick)

    def _on_unit_changed(self, unit: str):
        self.overlay.set_unit(unit)

    def _on_simulation_toggled(self, sim: bool):
        self.telemetry_reader.set_simulation_mode(sim)

    def _on_overlay_lock_changed(self, locked: bool):
        pass

    def _on_overlay_vis_changed(self, visible: bool):
        pass

    def _handle_visibility_hotkey(self):
        self.root.after(0, self.overlay.toggle_visibility)

    def _handle_lock_hotkey(self):
        self.root.after(0, self.overlay.toggle_lock)

    def _handle_f9_hotkey(self):
        self._handle_visibility_hotkey()

    def _handle_f10_hotkey(self):
        self._handle_lock_hotkey()

    def on_close(self):
        """Graceful shutdown when Control Panel is closed."""
        self._running = False
        try:
            self.hotkeys.stop()
        except Exception:
            pass
        try:
            self.net_client.stop()
        except Exception:
            pass
        try:
            self.telemetry_reader.close()
        except Exception:
            pass
        try:
            self.config.save()
        except Exception:
            pass
        self.root.destroy()


def main():
    print("🚚 Starting ConvoyPace...")
    app = ConvoyPaceApp()
    app.start()


if __name__ == "__main__":
    main()
