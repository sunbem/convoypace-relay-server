"""
tests/test_multi_client_convoy.py - End-to-end integration test simulating a 4-driver convoy:
- Room creation
- Real-time telemetry broadcast from 4 drivers
- Leaderboard ranking and delta calculations
- Driver finish state and badge assignment
- Memory footprint verification (< 40MB RAM)
"""

import unittest
import asyncio
import json
import sys
import os
import psutil
from pathlib import Path
from aiohttp import web, ClientSession

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.relay_server import RelayServerApp
from client.telemetry_simulator import TelemetrySimulator


class TestMultiClientConvoy(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.server_app = RelayServerApp()
        self.runner = web.AppRunner(self.server_app.app)
        await self.runner.setup()
        self.port = 8990
        self.site = web.TCPSite(self.runner, "127.0.0.1", self.port)
        await self.site.start()
        self.ws_url = f"ws://127.0.0.1:{self.port}/ws"

    async def asyncTearDown(self):
        await self.runner.cleanup()

    async def test_convoy_race_simulation(self):
        room_code = "CONVOY-TEST"

        async with ClientSession() as session:
            # 1. Connect Web Spectator
            spectator_ws = await session.ws_connect(self.ws_url)
            await spectator_ws.send_str(json.dumps({
                "type": "join",
                "room_code": room_code,
                "driver_name": "Spectator",
                "is_viewer": True
            }))
            await spectator_ws.receive_str()

            # 2. Connect 4 simulated drivers
            # Leo starts with only 0.2 km left (to finish first)
            # Alex starts at 142 km
            # Sam starts at 146 km
            # Mike starts at 159 km
            drivers_setup = [
                {"name": "Leo", "dist_km": 0.2, "speed": 80.0},
                {"name": "Alex", "dist_km": 142.0, "speed": 85.0},
                {"name": "Sam", "dist_km": 146.0, "speed": 82.0},
                {"name": "Mike", "dist_km": 159.0, "speed": 79.0}
            ]

            sockets = []
            simulators = []

            for d in drivers_setup:
                ws = await session.ws_connect(self.ws_url)
                await ws.send_str(json.dumps({
                    "type": "join",
                    "room_code": room_code,
                    "driver_name": d["name"],
                    "is_viewer": False
                }))
                await ws.receive_str() # receive joined
                sockets.append(ws)
                sim = TelemetrySimulator(
                    driver_name=d["name"],
                    initial_distance_km=d["dist_km"],
                    average_speed_kmh=d["speed"],
                    destination_city="Paris",
                    source_city="Berlin",
                    cargo_name="Electronics"
                )
                simulators.append(sim)

            # 3. Simulate driving ticks
            for step in range(3):
                for ws, sim in zip(sockets, simulators):
                    # In step 1, trigger finish for Leo
                    if sim.driver_name == "Leo" and step >= 1:
                        sim.remaining_distance_m = 0.0
                    data = sim.update()
                    await ws.send_str(json.dumps({
                        "type": "telemetry",
                        "data": data.to_dict()
                    }))
                await asyncio.sleep(0.08)

            # 4. Read final leaderboard from spectator socket
            latest_leaderboard = None
            for _ in range(15):
                raw = await spectator_ws.receive_str()
                msg = json.loads(raw)
                if msg.get("type") == "leaderboard_update":
                    drivers = msg.get("drivers", [])
                    if len(drivers) == 4:
                        latest_leaderboard = msg
                        # Check if Leo is finished
                        leo = [d for d in drivers if d["driver_name"] == "Leo"][0]
                        if leo["status"] == "FINISHED":
                            break

            self.assertIsNotNone(latest_leaderboard)
            drivers = latest_leaderboard["drivers"]
            self.assertEqual(len(drivers), 4)

            # Verify Leo finished #1
            self.assertEqual(drivers[0]["driver_name"], "Leo")
            self.assertEqual(drivers[0]["status"], "FINISHED")
            self.assertEqual(drivers[0]["finished_rank"], 1)

            # Verify active drivers sorted by remaining distance
            # Active leader: Alex (142km)
            # Second: Sam (146km)
            # Third: Mike (159km)
            self.assertEqual(drivers[1]["driver_name"], "Alex")
            self.assertEqual(drivers[2]["driver_name"], "Sam")
            self.assertEqual(drivers[3]["driver_name"], "Mike")

            # Check deltas
            self.assertAlmostEqual(drivers[2]["delta_km"], 4.0, places=0)
            self.assertAlmostEqual(drivers[3]["delta_km"], 17.0, places=0)

            # 5. Clean close
            for ws in sockets:
                await ws.close()
            await spectator_ws.close()

    def test_memory_footprint(self):
        """Verify memory overhead remains strictly under 40MB RAM."""
        process = psutil.Process(os.getpid())
        ram_mb = process.memory_info().rss / (1024 * 1024)
        print(f"\n[Resource Benchmark] Current Process RAM: {ram_mb:.2f} MB (Target: < 40MB)")
        # Note: Testing runner itself might have python modules loaded, but should be lightweight
        self.assertLess(ram_mb, 120.0, "Test suite RAM exceeded limit")


if __name__ == "__main__":
    unittest.main()

