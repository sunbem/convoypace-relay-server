"""
server/relay_server.py - Ultra-lightweight real-time relay server for ConvoyPace.
Handles in-memory rooms, WebSockets sync, leaderboard sorting, and Web HUD.
"""

import sys
import os
import json
import time
import random
import string
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
from aiohttp import web, WSMsgType

# Add root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def generate_room_code() -> str:
    """Generate a clean, readable 5-character convoy room code like TRUCK-42."""
    prefix = random.choice(["TRUCK", "CONVOY", "HAUL", "PACE", "ROUTE"])
    suffix = random.randint(10, 99)
    return f"{prefix}-{suffix}"


class DriverSession:
    """Represents a driver or web viewer connected via WebSocket."""

    def __init__(self, ws: web.WebSocketResponse, driver_name: str, is_viewer: bool = False):
        self.id = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        self.ws = ws
        self.driver_name = driver_name
        self.is_viewer = is_viewer
        self.last_seen = time.time()
        self.telemetry: Dict[str, Any] = {}
        self.finish_time: Optional[float] = None
        self.finish_rank: Optional[int] = None

    def update_telemetry(self, data: Dict[str, Any]):
        self.last_seen = time.time()
        self.telemetry = data

        # Check if driver has finished
        is_finished = data.get("is_finished", False) or (
            data.get("on_job", False) and data.get("route_distance_m", 100) <= 0
        )
        if is_finished and self.finish_time is None:
            self.finish_time = time.time()


class ConvoyRoom:
    """In-memory room managing convoy drivers and real-time leaderboard."""

    def __init__(self, code: str):
        self.code = code
        self.created_at = time.time()
        self.last_activity = time.time()
        self.sessions: Dict[str, DriverSession] = {}
        self.finish_counter = 0

    def add_session(self, session: DriverSession):
        self.sessions[session.id] = session
        self.last_activity = time.time()

    def remove_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]
            self.last_activity = time.time()

    def is_empty(self) -> bool:
        return len(self.sessions) == 0

    def is_expired(self, max_idle_seconds: float = 7200) -> bool:
        """Rooms auto-expire after 2 hours (7200s) of inactivity."""
        return (time.time() - self.last_activity) > max_idle_seconds

    def compute_leaderboard(self) -> Dict[str, Any]:
        """Sort all active drivers and compute distance deltas and ranks."""
        drivers = [s for s in self.sessions.values() if not s.is_viewer]

        # Extract consensus route information
        source_city = ""
        destination_city = ""
        cargo_name = ""
        for s in drivers:
            if s.telemetry.get("destination_city"):
                destination_city = s.telemetry["destination_city"]
                source_city = s.telemetry.get("source_city", "")
                cargo_name = s.telemetry.get("cargo_name", "")
                break

        # Separate finished vs active drivers
        finished_drivers: List[DriverSession] = []
        active_drivers: List[DriverSession] = []

        for s in drivers:
            if s.finish_time is not None or s.telemetry.get("is_finished", False):
                if s.finish_rank is None:
                    self.finish_counter += 1
                    s.finish_rank = self.finish_counter
                finished_drivers.append(s)
            else:
                active_drivers.append(s)

        # Finished drivers sorted by finish_rank (or finish_time)
        finished_drivers.sort(key=lambda s: s.finish_rank or 999)

        # Active drivers sorted by remaining distance ascending (lowest distance = leader)
        active_drivers.sort(key=lambda s: s.telemetry.get("route_distance_m", 99999999.0))

        # Combine all drivers in order
        all_sorted = finished_drivers + active_drivers

        # Find leader distance for active drivers
        leader_distance_m = None
        if active_drivers:
            leader_distance_m = active_drivers[0].telemetry.get("route_distance_m", 0.0)

        results = []
        for idx, s in enumerate(all_sorted, start=1):
            t = s.telemetry
            dist_m = t.get("route_distance_m", 0.0)
            dist_km = t.get("distance_km", dist_m / 1000.0)
            dist_mi = t.get("distance_mi", dist_km * 0.621371)
            speed_kmh = t.get("speed_kmh", 0.0)
            speed_mph = t.get("speed_mph", 0.0)

            delta_km = 0.0
            delta_mi = 0.0
            if leader_distance_m is not None and s in active_drivers:
                delta_m = max(0.0, dist_m - leader_distance_m)
                delta_km = delta_m / 1000.0
                delta_mi = delta_km * 0.621371

            status = "DRIVING"
            if s in finished_drivers:
                status = "FINISHED"
            elif t.get("paused", False):
                status = "PAUSED"
            elif not t.get("on_job", False):
                status = "FREE_ROAM"

            results.append({
                "session_id": s.id,
                "rank": idx,
                "driver_name": s.driver_name,
                "distance_km": round(dist_km, 1),
                "distance_mi": round(dist_mi, 1),
                "delta_km": round(delta_km, 1),
                "delta_mi": round(delta_mi, 1),
                "speed_kmh": round(speed_kmh, 1),
                "speed_mph": round(speed_mph, 1),
                "time_formatted": t.get("time_formatted", "--:--"),
                "cargo_damage": round(t.get("cargo_damage", 0.0) * 100, 1),
                "status": status,
                "finished_rank": s.finish_rank,
                "destination_city": t.get("destination_city", destination_city),
                "last_seen": round(s.last_seen, 1)
            })

        return {
            "type": "leaderboard_update",
            "room_code": self.code,
            "route": {
                "source": source_city,
                "destination": destination_city,
                "cargo": cargo_name
            },
            "drivers": results,
            "timestamp": time.time()
        }

    async def broadcast(self):
        """Broadcast updated leaderboard to all connected sockets in this room."""
        payload = self.compute_leaderboard()
        text = json.dumps(payload)

        stale_ids = []
        for s_id, session in list(self.sessions.items()):
            try:
                if not session.ws.closed:
                    await session.ws.send_str(text)
                else:
                    stale_ids.append(s_id)
            except Exception:
                stale_ids.append(s_id)

        for s_id in stale_ids:
            self.remove_session(s_id)


class RelayServerApp:
    """Encapsulates the aiohttp web & WebSocket application."""

    def __init__(self):
        self.rooms: Dict[str, ConvoyRoom] = {}
        self.web_dir = Path(__file__).resolve().parent / "web"
        self.app = web.Application()
        self._setup_routes()

    def _setup_routes(self):
        self.app.router.add_get("/", self.handle_index)
        self.app.router.add_get("/health", self.handle_health)
        self.app.router.add_get("/api/health", self.handle_health)
        self.app.router.add_post("/api/rooms", self.handle_create_room)
        self.app.router.add_get("/api/rooms/{code}", self.handle_get_room)
        self.app.router.add_get("/room/{code}", self.handle_web_view)
        self.app.router.add_get("/ws", self.handle_ws)

    def get_or_create_room(self, code: str) -> ConvoyRoom:
        code = code.strip().upper()
        if code not in self.rooms:
            self.rooms[code] = ConvoyRoom(code)
        return self.rooms[code]

    def cleanup_expired_rooms(self):
        expired = [c for c, r in self.rooms.items() if r.is_expired()]
        for c in expired:
            del self.rooms[c]

    async def handle_index(self, request: web.Request) -> web.Response:
        default_room = generate_room_code()
        return web.HTTPFound(f"/room/{default_room}")

    async def handle_health(self, request: web.Request) -> web.Response:
        self.cleanup_expired_rooms()
        total_drivers = sum(len(r.sessions) for r in self.rooms.values())
        return web.json_response({
            "status": "ok",
            "active_rooms": len(self.rooms),
            "connected_clients": total_drivers,
            "version": "1.0.0"
        })

    async def handle_create_room(self, request: web.Request) -> web.Response:
        code = generate_room_code()
        while code in self.rooms:
            code = generate_room_code()
        self.rooms[code] = ConvoyRoom(code)
        return web.json_response({
            "room_code": code,
            "url": f"/room/{code}"
        })

    async def handle_get_room(self, request: web.Request) -> web.Response:
        code = request.match_info["code"].upper()
        if code not in self.rooms:
            return web.json_response({"error": "Room not found"}, status=404)
        room = self.rooms[code]
        return web.json_response(room.compute_leaderboard())

    async def handle_web_view(self, request: web.Request) -> web.Response:
        index_file = self.web_dir / "index.html"
        if not index_file.exists():
            return web.Response(text="Web view index.html not found", status=404)
        return web.FileResponse(index_file)

    async def handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=20.0)
        await ws.prepare(request)

        current_room: Optional[ConvoyRoom] = None
        current_session: Optional[DriverSession] = None

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                    except Exception:
                        continue

                    msg_type = data.get("type", "")

                    if msg_type == "join":
                        room_code = data.get("room_code", "DEFAULT").strip().upper()
                        driver_name = data.get("driver_name", "Driver").strip() or "Driver"
                        is_viewer = bool(data.get("is_viewer", False))

                        # Leave previous room if any
                        if current_room and current_session:
                            current_room.remove_session(current_session.id)
                            await current_room.broadcast()

                        current_room = self.get_or_create_room(room_code)
                        
                        # Deduplicate: remove any existing session with the same driver name
                        # This handles reconnects and duplicate joins from the same driver
                        if not is_viewer:
                            existing_sessions_to_remove = [
                                s_id for s_id, s in current_room.sessions.items()
                                if not s.is_viewer and s.driver_name == driver_name
                            ]
                            for s_id in existing_sessions_to_remove:
                                current_room.remove_session(s_id)
                        
                        current_session = DriverSession(ws, driver_name=driver_name, is_viewer=is_viewer)
                        current_room.add_session(current_session)

                        await ws.send_str(json.dumps({
                            "type": "joined",
                            "room_code": room_code,
                            "session_id": current_session.id
                        }))
                        await current_room.broadcast()

                    elif msg_type == "telemetry":
                        if current_room and current_session:
                            telemetry_data = data.get("data", {})
                            current_session.update_telemetry(telemetry_data)
                            await current_room.broadcast()

                    elif msg_type == "ping":
                        await ws.send_str(json.dumps({"type": "pong"}))

                    elif msg_type == "leave":
                        if current_room and current_session:
                            current_room.remove_session(current_session.id)
                            await current_room.broadcast()
                            current_room = None
                            current_session = None

                elif msg.type == WSMsgType.ERROR:
                    break

        finally:
            if current_room and current_session:
                current_room.remove_session(current_session.id)
                await current_room.broadcast()

        return ws


def run_server(host: Optional[str] = None, port: Optional[int] = None):
    import os
    _host = host or os.environ.get("PORT_HOST", "0.0.0.0")
    _port = port if port is not None else int(os.environ.get("PORT", "8080"))
    server = RelayServerApp()
    print(f"🚀 ConvoyPace Relay Server running on http://{_host}:{_port}")
    print(f"   Web HUD view available at http://localhost:{_port}/room/TRUCK-42")
    web.run_app(server.app, host=_host, port=_port)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ConvoyPace Relay Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    args = parser.parse_args()
    run_server(host=args.host, port=args.port)

