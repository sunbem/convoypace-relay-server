"""
tests/test_app_lifecycle.py - Automated test verifying the ConvoyPaceApp initialization,
state transitions, simulated telemetry ticks, and clean shutdown.
"""

import unittest
import sys
import tempfile
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from client.config_manager import ConfigManager
from client.telemetry_reader import TelemetryReader
from client.overlay_window import OverlayWindow
from client.main import ConvoyPaceApp


class TestAppLifecycle(unittest.TestCase):

    def test_app_init_and_tick(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
            cfg_path = Path(tf.name)

        try:
            # Prepare config with simulation mode enabled
            cfg = ConfigManager(config_path=cfg_path)
            cfg.set("simulation_mode", True)
            cfg.set("driver_name", "TestRacer")
            cfg.set("last_room_code", "MOCK-99")

            # Initialize app
            app = ConvoyPaceApp(config=cfg)
            self.assertIsNotNone(app.overlay)
            self.assertIsNotNone(app.control_panel)
            self.assertIsNotNone(app.telemetry_reader)
            self.assertIsNotNone(app.net_client)

            # Test telemetry tick manually
            app._telemetry_tick()
            self.assertEqual(app.control_panel.var_room_code.get(), "MOCK-99")

            # Test hotkey handlers
            app._handle_f9_hotkey()
            app._handle_f10_hotkey()

            # Test simulated leaderboard update injection
            mock_update = {
                "room_code": "MOCK-99",
                "route": {"source": "Berlin", "destination": "Paris"},
                "drivers": [
                    {"rank": 1, "driver_name": "TestRacer", "distance_km": 120.0, "delta_km": 0.0, "speed_kmh": 85.0, "status": "DRIVING"}
                ]
            }
            app.overlay.update_leaderboard(mock_update)
            self.assertEqual(len(app.overlay.rows_frame.winfo_children()), 1)

            # Clean shutdown
            app.on_close()

        finally:
            if cfg_path.exists():
                cfg_path.unlink()


if __name__ == "__main__":
    unittest.main()
