"""
tests/test_telemetry.py - Unit tests for telemetry model, binary buffer pack/unpack, and simulator.
"""

import unittest
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.telemetry_model import (
    TelemetryData,
    pack_telemetry_buffer,
    parse_telemetry_buffer
)
from client.telemetry_simulator import TelemetrySimulator
from client.telemetry_reader import TelemetryReader


class TestTelemetryModel(unittest.TestCase):

    def test_units_conversion(self):
        data = TelemetryData(
            speed_ms=25.0,            # 25 m/s = 90 km/h
            route_distance_m=100000.0 # 100,000 m = 100 km
        )
        self.assertAlmostEqual(data.speed_kmh, 90.0, places=1)
        self.assertAlmostEqual(data.speed_mph, 55.9, places=1)
        self.assertAlmostEqual(data.distance_km, 100.0, places=1)
        self.assertAlmostEqual(data.distance_mi, 62.1, places=1)

    def test_formatting(self):
        data = TelemetryData(
            speed_ms=22.77,            # ~82 km/h
            route_distance_m=146000.0, # 146 km
            route_time_s=6480.0,       # 1h 48m (108 minutes)
            on_job=True
        )
        self.assertEqual(data.format_distance("km"), "146 km")
        self.assertEqual(data.format_distance("mi"), "91 mi")
        self.assertEqual(data.format_speed("km"), "82 km/h")
        self.assertEqual(data.format_speed("mi"), "51 mph")
        self.assertEqual(data.format_time(), "1h 48m")

    def test_finish_state(self):
        data = TelemetryData(
            on_job=True,
            route_distance_m=0.0,
            job_finished=True
        )
        self.assertTrue(data.is_finished)
        self.assertEqual(data.format_distance("km"), "🏁 FINISHED")

    def test_binary_pack_and_parse(self):
        original = TelemetryData(
            sdk_active=True,
            paused=False,
            speed_ms=23.6,
            route_distance_m=142350.0,
            route_time_s=5800.0,
            speed_limit_ms=25.0,
            cargo_damage=0.035,
            destination_city="Paris",
            destination_company="Tradeaux",
            source_city="Berlin",
            source_company="LKWLog",
            cargo_name="Electronics",
            on_job=True,
            job_finished=False
        )

        buffer = pack_telemetry_buffer(original)
        self.assertEqual(len(buffer), 32 * 1024)

        parsed = parse_telemetry_buffer(buffer)
        self.assertIsNotNone(parsed)
        self.assertTrue(parsed.sdk_active)
        self.assertFalse(parsed.paused)
        self.assertAlmostEqual(parsed.speed_ms, 23.6, places=2)
        self.assertAlmostEqual(parsed.route_distance_m, 142350.0, places=0)
        self.assertAlmostEqual(parsed.cargo_damage, 0.035, places=2)
        self.assertEqual(parsed.destination_city, "Paris")
        self.assertEqual(parsed.destination_company, "Tradeaux")
        self.assertEqual(parsed.source_city, "Berlin")
        self.assertEqual(parsed.source_company, "LKWLog")
        self.assertEqual(parsed.cargo_name, "Electronics")
        self.assertTrue(parsed.on_job)
        self.assertFalse(parsed.job_finished)

    def test_simulator_progression(self):
        sim = TelemetrySimulator(initial_distance_km=10.0, average_speed_kmh=80.0)
        snap1 = sim.update()
        self.assertAlmostEqual(snap1.distance_km, 10.0, delta=0.5)
        self.assertFalse(snap1.is_finished)

        # Force distance to 0
        sim.remaining_distance_m = 0.0
        snap_finished = sim.update()
        self.assertTrue(snap_finished.is_finished)
        self.assertEqual(snap_finished.format_distance(), "🏁 FINISHED")

    def test_reader_simulation_mode(self):
        reader = TelemetryReader(simulation_mode=True, sim_distance_km=50.0)
        self.assertTrue(reader.connect())
        data, status = reader.read()
        self.assertIsNotNone(data)
        self.assertEqual(status, "Simulation Active")
        self.assertAlmostEqual(data.distance_km, 50.0, delta=1.0)


if __name__ == "__main__":
    unittest.main()

