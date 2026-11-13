"""
client/telemetry_simulator.py - Realistic mock telemetry generator for ETS2.
Allows end-to-end testing of ConvoyPace without running Euro Truck Simulator 2.
"""

import time
import random
import sys
from pathlib import Path

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.telemetry_model import TelemetryData


class TelemetrySimulator:
    """Simulates active truck driving telemetry with realistic speed and distance decay."""

    def __init__(
        self,
        driver_name: str = "Sam",
        initial_distance_km: float = 146.0,
        average_speed_kmh: float = 82.0,
        destination_city: str = "Paris",
        destination_company: str = "Tradeaux",
        source_city: str = "Berlin",
        source_company: str = "LKWLog",
        cargo_name: str = "Electronics",
        initial_damage: float = 0.02
    ):
        self.driver_name = driver_name
        self.destination_city = destination_city
        self.destination_company = destination_company
        self.source_city = source_city
        self.source_company = source_company
        self.cargo_name = cargo_name

        self.remaining_distance_m = initial_distance_km * 1000.0
        self.initial_distance_m = self.remaining_distance_m
        self.target_speed_kmh = average_speed_kmh
        self.current_speed_kmh = average_speed_kmh
        self.cargo_damage = initial_damage

        self.paused = False
        self.job_finished = False
        self.last_update_time = time.time()

    def update(self) -> TelemetryData:
        """Advance simulation tick (call every ~1 second)."""
        now = time.time()
        dt = max(0.1, min(3.0, now - self.last_update_time))
        self.last_update_time = now

        if self.paused:
            return self.get_snapshot()

        if self.job_finished or self.remaining_distance_m <= 0:
            self.job_finished = True
            self.remaining_distance_m = 0.0
            self.current_speed_kmh = 0.0
            return self.get_snapshot()

        # Add realistic micro-variations to speed (e.g. +/- 4 km/h)
        speed_jitter = random.uniform(-1.5, 1.5)
        self.current_speed_kmh = max(40.0, min(95.0, self.current_speed_kmh + speed_jitter))

        # Decrease remaining distance based on speed
        speed_ms = (self.current_speed_kmh / 3.6)
        distance_covered = speed_ms * dt
        self.remaining_distance_m = max(0.0, self.remaining_distance_m - distance_covered)

        if self.remaining_distance_m <= 0.0:
            self.job_finished = True
            self.remaining_distance_m = 0.0
            self.current_speed_kmh = 0.0

        return self.get_snapshot()

    def get_snapshot(self) -> TelemetryData:
        """Return current snapshot as TelemetryData instance."""
        speed_ms = self.current_speed_kmh / 3.6
        route_time_s = (self.remaining_distance_m / max(10.0, speed_ms)) if not self.job_finished else 0.0

        return TelemetryData(
            sdk_active=True,
            paused=self.paused,
            speed_ms=speed_ms if not self.job_finished else 0.0,
            route_distance_m=self.remaining_distance_m,
            route_time_s=route_time_s,
            speed_limit_ms=90.0 / 3.6,
            cargo_damage=self.cargo_damage,
            destination_city=self.destination_city,
            destination_company=self.destination_company,
            source_city=self.source_city,
            source_company=self.source_company,
            cargo_name=self.cargo_name,
            on_job=True,
            job_finished=self.job_finished,
            timestamp=time.time()
        )

    def set_paused(self, paused: bool):
        self.paused = paused

    def reset(self, distance_km: float = 146.0):
        self.remaining_distance_m = distance_km * 1000.0
        self.job_finished = False
        self.paused = False
        self.last_update_time = time.time()

