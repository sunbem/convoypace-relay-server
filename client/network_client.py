"""
client/network_client.py - Threaded WebSocket client for real-time convoy telemetry sync.
Maintains connection, auto-reconnects, and relays leaderboard updates to the UI.
"""

import sys
import json
import time
import asyncio
import threading
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from urllib.parse import urlparse
import aiohttp

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def normalize_ws_url(url: str) -> str:
    """Convert http:// or https:// or plain host to proper WebSocket URL ending with /ws."""
    url = url.strip()
    if not url.startswith("http://") and not url.startswith("https://") and not url.startswith("ws://") and not url.startswith("wss://"):
        url = "http://" + url

    parsed = urlparse(url)
    scheme = "wss" if parsed.scheme in ["https", "wss"] else "ws"
    netloc = parsed.netloc or parsed.path
    return f"{scheme}://{netloc}/ws"


class NetworkClient:
    """Runs an asynchronous WebSocket loop in a background thread."""

    def __init__(
        self,
        server_url: str,
        room_code: str,
        driver_name: str,
        on_leaderboard_update: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_status_change: Optional[Callable[[str, bool], None]] = None
    ):
        self.server_url = normalize_ws_url(server_url)
        self.room_code = room_code.strip().upper()
        self.driver_name = driver_name.strip() or "Driver"
        self.on_leaderboard_update = on_leaderboard_update
        self.on_status_change = on_status_change

        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._running = False
        self._is_connected = False
        self._latest_telemetry: Optional[Dict[str, Any]] = None
        self._telemetry_lock = threading.Lock()
        self._session_id: Optional[str] = None

    def start(self):
        """Start the background network thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="ConvoyPace-NetClient")
        self._thread.start()

    def stop(self):
        """Stop the background network thread."""
        self._running = False
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def update_telemetry(self, data: Dict[str, Any]):
        """Thread-safe update of current telemetry payload to be sent to server."""
        with self._telemetry_lock:
            self._latest_telemetry = data

    def change_room(self, room_code: str):
        """Switch room code dynamically."""
        self.room_code = room_code.strip().upper()
        if self._loop and self._loop.is_running():
            # Trigger reconnect to new room
            pass

    def update_driver_name(self, driver_name: str):
        self.driver_name = driver_name.strip() or "Driver"

    def is_connected(self) -> bool:
        return self._is_connected

    def clear_telemetry(self):
        """Clear current telemetry and send leave message to server."""
        self._latest_telemetry = None
        # The leave message will be sent by the _send_loop when it sees None telemetry
        # and the connection is still active

    def _notify_status(self, text: str, connected: bool):
        self._is_connected = connected
        if self.on_status_change:
            try:
                self.on_status_change(text, connected)
            except Exception:
                pass

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._worker())
        except Exception as e:
            self._notify_status(f"Network error: {e}", False)
        finally:
            self._loop.close()

    async def _worker(self):
        while self._running:
            try:
                self._notify_status("Connecting to relay...", False)
                timeout = aiohttp.ClientTimeout(total=10)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.ws_connect(self.server_url) as ws:
                        self._notify_status("Connected", True)

                        # Send join message
                        await ws.send_str(json.dumps({
                            "type": "join",
                            "room_code": self.room_code,
                            "driver_name": self.driver_name,
                            "is_viewer": False
                        }))

                        # Launch reader and sender sub-tasks
                        send_task = asyncio.create_task(self._send_loop(ws))
                        recv_task = asyncio.create_task(self._recv_loop(ws))

                        done, pending = await asyncio.wait(
                            [send_task, recv_task],
                            return_when=asyncio.FIRST_COMPLETED
                        )

                        for task in pending:
                            task.cancel()

            except Exception as e:
                self._notify_status(f"Disconnected ({e})", False)

            if self._running:
                await asyncio.sleep(2.0)  # Reconnect delay

    async def _send_loop(self, ws: aiohttp.ClientWebSocketResponse):
        """Periodically broadcast latest telemetry and heartbeat pings."""
        last_ping = time.time()
        leave_sent = False
        while self._running and not ws.closed:
            with self._telemetry_lock:
                telemetry_copy = self._latest_telemetry

            if telemetry_copy is not None:
                try:
                    await ws.send_str(json.dumps({
                        "type": "telemetry",
                        "data": telemetry_copy
                    }))
                    leave_sent = False  # Reset leave flag when telemetry resumes
                except Exception:
                    break
            elif not leave_sent:
                # Telemetry cleared (game quit) - send leave message
                try:
                    await ws.send_str(json.dumps({"type": "leave"}))
                    leave_sent = True
                except Exception:
                    break

            now = time.time()
            if now - last_ping > 15.0:
                try:
                    await ws.send_str(json.dumps({"type": "ping"}))
                    last_ping = now
                except Exception:
                    break

            await asyncio.sleep(1.0)  # 1-second telemetry interval

    async def _recv_loop(self, ws: aiohttp.ClientWebSocketResponse):
        """Receive leaderboard updates and messages from server."""
        async for msg in ws:
            if not self._running:
                break
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    msg_type = data.get("type", "")

                    if msg_type == "joined":
                        self._session_id = data.get("session_id")
                        self._notify_status(f"In Convoy {self.room_code}", True)

                    elif msg_type == "leaderboard_update":
                        if self.on_leaderboard_update:
                            try:
                                self.on_leaderboard_update(data)
                            except Exception as e:
                                print(f"Error in leaderboard callback: {e}")

                except Exception as e:
                    print(f"Error parsing incoming message: {e}")

            elif msg.type in [aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR]:
                break


if __name__ == "__main__":
    def on_update(data):
        print(f"Leaderboard update received: {len(data.get('drivers', []))} drivers")

    client = NetworkClient(
        server_url="http://localhost:8080",
        room_code="TRUCK-42",
        driver_name="TestDriver",
        on_leaderboard_update=on_update
    )
    print("Starting client...")
    client.start()
    time.sleep(2)
    client.stop()
    print("Done.")

