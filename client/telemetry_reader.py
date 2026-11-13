"""
client/telemetry_reader.py - Windows shared memory reader for ETS2 SCS Telemetry.
Safely connects to Local\\SCSTelemetry or falls back to simulation mode.
"""

import sys
import os
import mmap
import ctypes
from typing import Optional, Tuple
from pathlib import Path

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.telemetry_model import (
    TelemetryData,
    SCS_MMF_NAME,
    SCS_MMF_SIZE,
    parse_telemetry_buffer
)
from client.telemetry_simulator import TelemetrySimulator


FILE_MAP_READ = 0x0004


def is_scs_mmf_active() -> bool:
    """Check if Local\\SCSTelemetry shared memory object actually exists on Windows."""
    if os.name != "nt":
        return False
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenFileMappingW(FILE_MAP_READ, False, SCS_MMF_NAME)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    except Exception:
        return False


class TelemetryReader:
    """Reads live telemetry from Local\\SCSTelemetry or delegates to internal simulator."""

    def __init__(self, simulation_mode: bool = False, sim_distance_km: float = 146.0):
        self.simulation_mode = simulation_mode
        self.simulator = TelemetrySimulator(initial_distance_km=sim_distance_km)
        self.mm: Optional[mmap.mmap] = None
        self.is_connected = False
        self.last_error = ""

    def connect(self) -> bool:
        """Attempt to attach to Windows shared memory."""
        if self.simulation_mode:
            self.is_connected = True
            return True

        if os.name != "nt":
            self.last_error = "Shared memory reader only supported natively on Windows"
            self.is_connected = False
            return False

        if not is_scs_mmf_active():
            self.last_error = "ETS2 not running or scs-telemetry.dll not loaded"
            self.is_connected = False
            return False

        try:
            self.close()
            self.mm = mmap.mmap(
                -1,
                SCS_MMF_SIZE,
                tagname=SCS_MMF_NAME,
                access=mmap.ACCESS_READ
            )
            self.is_connected = True
            self.last_error = ""
            return True
        except Exception as e:
            self.last_error = str(e)
            self.is_connected = False
            self.mm = None
            return False

    def read(self) -> Tuple[Optional[TelemetryData], str]:
        """
        Read the latest telemetry frame.
        Returns: (TelemetryData or None, status_message)
        """
        if self.simulation_mode:
            return self.simulator.update(), "Simulation Active"

        if not self.is_connected or self.mm is None:
            if not self.connect():
                return None, self.last_error or "Not connected"

        try:
            self.mm.seek(0)
            raw = self.mm.read(SCS_MMF_SIZE)
            data = parse_telemetry_buffer(raw)

            if data is None or not data.sdk_active:
                # Game might have exited or unloaded plugin
                if not is_scs_mmf_active():
                    self.close()
                    return None, "ETS2 disconnected"
                return data, "SDK Inactive (Menu / Paused)"

            return data, "Live Connected"
        except Exception as e:
            self.close()
            return None, f"Read error: {e}"

    def set_simulation_mode(self, enabled: bool):
        """Toggle simulation mode on or off."""
        if self.simulation_mode != enabled:
            self.simulation_mode = enabled
            if enabled:
                self.close()
                self.is_connected = True
            else:
                self.is_connected = False
                self.connect()

    def close(self):
        """Safely release the memory-mapped file handle."""
        if self.mm:
            try:
                self.mm.close()
            except Exception:
                pass
            self.mm = None
        self.is_connected = False


if __name__ == "__main__":
    import time
    print("Testing TelemetryReader in Simulation Mode...")
    reader = TelemetryReader(simulation_mode=True, sim_distance_km=146.0)
    for i in range(3):
        data, status = reader.read()
        if data:
            print(f"[{status}] Speed: {data.format_speed('km')} | Distance: {data.format_distance('km')} | Route: {data.source_city} -> {data.destination_city}")
        time.sleep(0.5)

