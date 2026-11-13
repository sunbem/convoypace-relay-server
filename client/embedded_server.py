"""
client/embedded_server.py - Manages an in-process relay server for zero-terminal hosting.
Allows a convoy host to run the WebSocket relay server directly inside ConvoyPace.
"""

import sys
import socket
import asyncio
import threading
from pathlib import Path
from typing import Optional
from aiohttp import web

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server.relay_server import RelayServerApp


def get_local_ip() -> str:
    """Retrieve the primary local LAN IP of this machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class EmbeddedServerManager:
    """Runs a RelayServerApp instance in a background thread."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self.server_app = RelayServerApp()
        self._runner: Optional[web.AppRunner] = None
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self.is_running = False
        self.last_error = ""

    def start(self) -> bool:
        """Start the embedded relay server in background."""
        if self.is_running:
            return True

        self.last_error = ""
        started_event = threading.Event()
        error_holder = []

        def _target():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            try:
                self._runner = web.AppRunner(self.server_app.app)
                self._loop.run_until_complete(self._runner.setup())
                site = web.TCPSite(self._runner, self.host, self.port)
                self._loop.run_until_complete(site.start())
                self.is_running = True
                started_event.set()
                self._loop.run_forever()
            except Exception as e:
                self.last_error = str(e)
                error_holder.append(e)
                started_event.set()

        self._thread = threading.Thread(target=_target, daemon=True, name="ConvoyPace-EmbeddedServer")
        self._thread.start()

        started_event.wait(timeout=3.0)
        if error_holder:
            self.is_running = False
            return False

        return self.is_running

    def stop(self):
        """Stop the embedded relay server cleanly."""
        if not self.is_running:
            return
        self.is_running = False
        if self._loop and self._loop.is_running():
            async def _shutdown():
                try:
                    if self._runner:
                        await self._runner.cleanup()
                except Exception:
                    pass
                finally:
                    self._loop.stop()

            try:
                future = asyncio.run_coroutine_threadsafe(_shutdown(), self._loop)
                future.result(timeout=2.0)
            except Exception:
                pass

        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._runner = None
        self._loop = None

    def get_lan_url(self) -> str:
        """Return the shareable LAN URL for convoy friends."""
        lan_ip = get_local_ip()
        return f"http://{lan_ip}:{self.port}"

    def get_local_url(self) -> str:
        """Return the localhost URL for the host app."""
        return f"http://localhost:{self.port}"
