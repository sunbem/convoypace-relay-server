"""
tests/test_client_core.py - Unit tests for Steam detector, Plugin installer, and Config manager.
"""

import unittest
import os
import sys
import tempfile
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from client.steam_detector import (
    detect_ets2_path,
    get_plugin_destination,
    is_plugin_installed,
    parse_library_folders
)
from client.plugin_installer import (
    install_plugin,
    uninstall_plugin,
    get_bundled_plugin_path
)
from client.config_manager import ConfigManager


class TestClientCore(unittest.TestCase):

    def test_config_manager_persistence(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
            temp_path = Path(tf.name)

        try:
            cfg = ConfigManager(config_path=temp_path)
            self.assertEqual(cfg.get("unit"), "km")

            # Update settings
            cfg.set("driver_name", "TestPilot")
            cfg.set("last_room_code", "CONVOY-99")
            cfg.set("unit", "mi")

            # Re-read in fresh instance
            cfg2 = ConfigManager(config_path=temp_path)
            self.assertEqual(cfg2.get("driver_name"), "TestPilot")
            self.assertEqual(cfg2.get("last_room_code"), "CONVOY-99")
            self.assertEqual(cfg2.get("unit"), "mi")
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_bundled_plugin_exists(self):
        bundled = get_bundled_plugin_path()
        self.assertIsNotNone(bundled)
        self.assertTrue(os.path.isfile(bundled))
        self.assertTrue(os.path.getsize(bundled) > 40000)

    def test_steam_detection(self):
        detected = detect_ets2_path()
        if os.name == "nt":
            # On this machine, ETS2 was found in E:\SteamLibrary
            self.assertIsNotNone(detected)
            self.assertTrue(os.path.isdir(detected))
            exe_path = os.path.join(detected, "bin", "win_x64", "eurotrucks2.exe")
            self.assertTrue(os.path.isfile(exe_path))

    def test_mock_plugin_installation(self):
        # Create a mock ETS2 directory structure in temp
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_bin = Path(tmpdir) / "bin" / "win_x64"
            mock_bin.mkdir(parents=True, exist_ok=True)
            # Create dummy eurotrucks2.exe
            mock_exe = mock_bin / "eurotrucks2.exe"
            mock_exe.write_text("dummy")

            # Test install
            res = install_plugin(ets2_path=tmpdir)
            self.assertTrue(res["success"])
            self.assertTrue(is_plugin_installed(tmpdir))

            # Test uninstall
            un_res = uninstall_plugin(ets2_path=tmpdir)
            self.assertTrue(un_res["success"])
            self.assertFalse(is_plugin_installed(tmpdir))


if __name__ == "__main__":
    unittest.main()

