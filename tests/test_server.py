"""
tests/test_server.py - Integration tests for the ConvoyPace relay server and WebSocket protocol.
"""

import unittest
import asyncio
import json
import sys
from pathlib import Path
from aiohttp import web, ClientSession

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server.relay_server import RelayServerApp, ConvoyRoom, DriverSession
from client.embedded_server import EmbeddedServerManager


class TestServerLogic(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.server_app = RelayServerApp()
        self.runner = web.AppRunner(self.server_app.app)
        await self.runner.setup()
        self.port = 8899
        self.site = web.TCPSite(self.runner, "127.0.0.1", self.port)
        await self.site.start()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.ws_url = f"ws://127.0.0.1:{self.port}/ws"

    async def asyncTearDown(self):
        await self.runner.cleanup()

    async def test_health_and_create_room_api(self):
        async with ClientSession() as session:
            # Test /health
            async with session.get(f"{self.base_url}/health") as resp:
                self.assertEqual(resp.status, 200)
                data = await resp.json()
                self.assertEqual(data["status"], "ok")

            # Test POST /api/rooms
            async with session.post(f"{self.base_url}/api/rooms") as resp:
                self.assertEqual(resp.status, 200)
                data = await resp.json()
                self.assertIn("room_code", data)
                self.assertTrue(len(data["room_code"]) >= 5)

    async def test_websocket_multi_driver_leaderboard(self):
        async with ClientSession() as session:
            # Driver 1: Alex (Remaining: 142 km)
            ws1 = await session.ws_connect(self.ws_url)
            await ws1.send_str(json.dumps({
                "type": "join",
                "room_code": "TEST-1",
                "driver_name": "Alex"
            }))
            join_resp1 = json.loads(await ws1.receive_str())
            self.assertEqual(join_resp1["type"], "joined")
            # Initial leaderboard broadcast upon join
            await ws1.receive_str()

            # Driver 2: Sam (Remaining: 146 km)
            ws2 = await session.ws_connect(self.ws_url)
            await ws2.send_str(json.dumps({
                "type": "join",
                "room_code": "TEST-1",
                "driver_name": "Sam"
            }))
            join_resp2 = json.loads(await ws2.receive_str())
            self.assertEqual(join_resp2["type"], "joined")
            # Receive join broadcast
            await ws2.receive_str()
            # ws1 also receives the updated broadcast
            await ws1.receive_str()

            # Send telemetry for Alex (142 km, speed 85 km/h)
            await ws1.send_str(json.dumps({
                "type": "telemetry",
                "data": {
                    "route_distance_m": 142000.0,
                    "distance_km": 142.0,
                    "speed_kmh": 85.0,
                    "time_formatted": "1h 48m",
                    "destination_city": "Paris",
                    "source_city": "Berlin",
                    "cargo_name": "Electronics",
                    "on_job": True,
                    "is_finished": False
                }
            }))

            # Small delay to ensure ws1 update processed
            await asyncio.sleep(0.05)

            # Send telemetry for Sam (146 km, speed 82 km/h)
            await ws2.send_str(json.dumps({
                "type": "telemetry",
                "data": {
                    "route_distance_m": 146000.0,
                    "distance_km": 146.0,
                    "speed_kmh": 82.0,
                    "time_formatted": "1h 51m",
                    "destination_city": "Paris",
                    "source_city": "Berlin",
                    "cargo_name": "Electronics",
                    "on_job": True,
                    "is_finished": False
                }
            }))

            # Drain messages until we get update where both drivers have reported distance > 0
            msg = None
            for _ in range(10):
                raw = await ws2.receive_str()
                data = json.loads(raw)
                if data.get("type") == "leaderboard_update":
                    drivers = data.get("drivers", [])
                    if len(drivers) == 2 and all(d["distance_km"] > 0 for d in drivers):
                        msg = data
                        break

            self.assertIsNotNone(msg)
            drivers = msg["drivers"]
            self.assertEqual(len(drivers), 2)

            # Leaderboard sort verification:
            # #1 Alex at 142 km (delta 0)
            # #2 Sam at 146 km (delta +4 km)
            self.assertEqual(drivers[0]["driver_name"], "Alex")
            self.assertEqual(drivers[0]["rank"], 1)
            self.assertEqual(drivers[0]["distance_km"], 142.0)
            self.assertEqual(drivers[0]["delta_km"], 0.0)

            self.assertEqual(drivers[1]["driver_name"], "Sam")
            self.assertEqual(drivers[1]["rank"], 2)
            self.assertEqual(drivers[1]["distance_km"], 146.0)
            self.assertAlmostEqual(drivers[1]["delta_km"], 4.0, places=1)

            # Route verification
            self.assertEqual(msg["route"]["destination"], "Paris")
            self.assertEqual(msg["route"]["source"], "Berlin")

            # Test Finish state for Alex
            await ws1.send_str(json.dumps({
                "type": "telemetry",
                "data": {
                    "route_distance_m": 0.0,
                    "distance_km": 0.0,
                    "speed_kmh": 0.0,
                    "on_job": True,
                    "is_finished": True
                }
            }))

            # Check that Alex is marked FINISHED (#1)
            raw = await ws2.receive_str()
            fin_update = json.loads(raw)
            alex_entry = [d for d in fin_update["drivers"] if d["driver_name"] == "Alex"][0]
            self.assertEqual(alex_entry["status"], "FINISHED")
            self.assertEqual(alex_entry["finished_rank"], 1)

            await ws1.close()
            await ws2.close()


    async def test_embedded_server_lifecycle(self):
        embedded = EmbeddedServerManager(port=8995)
        try:
            self.assertTrue(embedded.start())
            self.assertTrue(embedded.is_running)
            async with ClientSession() as session:
                async with session.get(f"http://127.0.0.1:8995/health") as resp:
                    self.assertEqual(resp.status, 200)
                    data = await resp.json()
                    self.assertEqual(data["status"], "ok")
        finally:
            embedded.stop()
            self.assertFalse(embedded.is_running)


if __name__ == "__main__":
    unittest.main()
