"""
client/overlay_window.py - Sleek, frameless, transparent, always-on-top in-game HUD overlay.
Supports click-through mode, drag-to-move, and real-time leaderboard rendering.
"""

import sys
import tkinter as tk
from tkinter import font as tkfont
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from client.win32_utils import set_click_through, set_always_on_top
from client.config_manager import ConfigManager


class OverlayWindow:
    """In-game HUD overlay window for Euro Truck Simulator 2."""

    def __init__(
        self,
        config: ConfigManager,
        on_lock_toggled: Optional[Callable[[bool], None]] = None,
        on_visibility_toggled: Optional[Callable[[bool], None]] = None
    ):
        self.config = config
        self.on_lock_toggled = on_lock_toggled
        self.on_visibility_toggled = on_visibility_toggled

        self.root = tk.Toplevel() if tk._default_root else tk.Tk()
        self.root.title("ConvoyPace HUD")

        # Visual configuration
        self.bg_color = "#0f1117"
        self.border_color_locked = "#21262d"
        self.border_color_unlocked = "#58a6ff"
        self.text_color = "#f0f6fc"
        self.accent_color = "#58a6ff"
        self.gold_color = "#f1e05a"
        self.orange_color = "#ffa657"
        self.green_color = "#3fb950"
        self.muted_color = "#8b949e"

        # Window properties
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.88)
        self.root.config(bg=self.bg_color)

        # Dragging state
        self._drag_start_x = 0
        self._drag_start_y = 0
        self.is_locked = self.config.get("overlay_locked", True)
        self.is_visible = self.config.get("overlay_visible", True)

        # Data cache
        self.current_unit = self.config.get("unit", "km")
        self.local_driver_name = self.config.get("driver_name", "Driver")
        self.leaderboard_data: Optional[Dict[str, Any]] = None

        # Build UI layout
        self._build_ui()

        # Apply saved position
        x = self.config.get("overlay_x", 40)
        y = self.config.get("overlay_y", 40)
        self.root.geometry(f"+{x}+{y}")

        # Bind dragging on the container
        self.container.bind("<ButtonPress-1>", self._on_drag_start)
        self.container.bind("<B1-Motion>", self._on_drag_motion)
        self.container.bind("<ButtonRelease-1>", self._on_drag_end)

        # Apply initial lock state after window mapping
        self.root.after(150, self._apply_initial_state)

    def _build_ui(self):
        # Outer container with border
        border_col = self.border_color_locked if self.is_locked else self.border_color_unlocked
        self.container = tk.Frame(
            self.root,
            bg=self.bg_color,
            highlightbackground=border_col,
            highlightthickness=1,
            padx=12,
            pady=10
        )
        self.container.pack(fill=tk.BOTH, expand=True)

        # Header Row: Convoy Code & Route
        self.header_frame = tk.Frame(self.container, bg=self.bg_color)
        self.header_frame.pack(fill=tk.X, pady=(0, 6))

        self.lbl_title = tk.Label(
            self.header_frame,
            text="🚚 CONVOY: --",
            font=("Segoe UI", 10, "bold"),
            fg=self.accent_color,
            bg=self.bg_color
        )
        self.lbl_title.pack(side=tk.LEFT)

        self.lbl_route = tk.Label(
            self.header_frame,
            text="[Route: Connecting...]",
            font=("Segoe UI", 9, "bold"),
            fg=self.gold_color,
            bg=self.bg_color
        )
        self.lbl_route.pack(side=tk.RIGHT)

        # Divider
        self.divider = tk.Frame(self.container, height=1, bg=self.border_color_locked)
        self.divider.pack(fill=tk.X, pady=(0, 8))

        # Dynamic rows container
        self.rows_frame = tk.Frame(self.container, bg=self.bg_color)
        self.rows_frame.pack(fill=tk.BOTH, expand=True)

        # Initial placeholder label
        self.lbl_empty = tk.Label(
            self.rows_frame,
            text="Waiting for convoy drivers...",
            font=("Segoe UI", 9),
            fg=self.muted_color,
            bg=self.bg_color,
            pady=10
        )
        self.lbl_empty.pack()

        # Footer divider
        self.footer_divider = tk.Frame(self.container, height=1, bg=self.border_color_locked)
        self.footer_divider.pack(fill=tk.X, pady=(8, 6))

        # Footer Row: Hotkeys & Lock status
        self.footer_frame = tk.Frame(self.container, bg=self.bg_color)
        self.footer_frame.pack(fill=tk.X)

        self.lbl_hotkeys = tk.Label(
            self.footer_frame,
            text="[Ctrl+F9 / Ins: Hide] [Ctrl+F10 / Home: Unlock]",
            font=("Segoe UI", 8),
            fg=self.muted_color,
            bg=self.bg_color
        )
        self.lbl_hotkeys.pack(side=tk.LEFT)

        self.lbl_lock_status = tk.Label(
            self.footer_frame,
            text="🔒 Locked",
            font=("Segoe UI", 8, "bold"),
            fg=self.green_color if self.is_locked else self.orange_color,
            bg=self.bg_color
        )
        self.lbl_lock_status.pack(side=tk.RIGHT)

    def _ensure_realized(self) -> bool:
        """Ensure the Tk window has been mapped before applying Win32 state."""
        try:
            self.root.update_idletasks()
            return self.root.winfo_viewable()
        except Exception:
            return False

    def _apply_initial_state(self):
        if not self._ensure_realized():
            # Window not yet mapped; retry shortly instead of applying to a stale HWND.
            self.root.after(100, self._apply_initial_state)
            return
        self.set_locked(self.is_locked)
        if not self.is_visible:
            self.root.withdraw()
        else:
            self.root.deiconify()
        # Self-heal: re-assert topmost + click-through shortly after mapping
        # (games like fullscreen-borderless can steal Z-order / reset layered state).
        self.root.after(2000, self._self_heal_lock)

    def _self_heal_lock(self):
        """One-shot self-heal: re-apply lock state (click-through + topmost) after mapping."""
        self.set_locked(self.is_locked)

    def set_locked(self, locked: bool):
        """Toggle lock state (locked = click-through, unlocked = draggable)."""
        self.is_locked = locked
        self.config.set("overlay_locked", locked)

        if locked:
            self.container.config(highlightbackground=self.border_color_locked)
            self.lbl_hotkeys.config(text="[Ctrl+F9 / Ins: Hide] [Ctrl+F10 / Home: Unlock]")
            self.lbl_lock_status.config(text="🔒 Locked", fg=self.green_color)
            set_click_through(self.root, True)
        else:
            self.container.config(highlightbackground=self.border_color_unlocked)
            self.lbl_hotkeys.config(text="[Ctrl+F9 / Ins: Hide] [Ctrl+F10 / Home: Lock]")
            self.lbl_lock_status.config(text="🔓 Drag Mode", fg=self.orange_color)
            set_click_through(self.root, False)

        set_always_on_top(self.root, True)
        if self.on_lock_toggled:
            self.on_lock_toggled(locked)

    def toggle_lock(self):
        self.set_locked(not self.is_locked)

    def toggle_visibility(self):
        self.is_visible = not self.is_visible
        self.config.set("overlay_visible", self.is_visible)
        if self.is_visible:
            self.root.deiconify()
            self.set_locked(self.is_locked)
        else:
            self.root.withdraw()
        if self.on_visibility_toggled:
            self.on_visibility_toggled(self.is_visible)

    def set_unit(self, unit: str):
        self.current_unit = unit.lower()
        if self.leaderboard_data:
            self.update_leaderboard(self.leaderboard_data)

    def set_driver_name(self, name: str):
        self.local_driver_name = name
        if self.leaderboard_data:
            self.update_leaderboard(self.leaderboard_data)

    def set_network_connected(self, connected: bool):
        """Update overlay state when disconnected from relay server."""
        if not connected:
            self.lbl_route.config(text="[Server Disconnected]")
            if not self.leaderboard_data or not self.leaderboard_data.get("drivers"):
                for widget in self.rows_frame.winfo_children():
                    widget.destroy()
                lbl = tk.Label(
                    self.rows_frame,
                    text="Relay server not connected.\nCheck 'Host Convoy' or verify Server URL.",
                    font=("Segoe UI", 9),
                    fg=self.orange_color,
                    bg=self.bg_color,
                    pady=10
                )
                lbl.pack()

    def update_leaderboard(self, data: Dict[str, Any]):
        """Render fresh leaderboard data received from the relay server."""
        self.leaderboard_data = data
        room_code = data.get("room_code", "--")
        self.lbl_title.config(text=f"🚚 CONVOY: {room_code}")

        # Update route
        route = data.get("route", {})
        src = route.get("source", "")
        dst = route.get("destination", "")
        if dst:
            route_str = f"[{src} ➔ {dst}]" if src else f"[➔ {dst}]"
        else:
            route_str = "[Free Roam]"
        self.lbl_route.config(text=route_str)

        # Clear existing rows
        for widget in self.rows_frame.winfo_children():
            widget.destroy()

        drivers: List[Dict[str, Any]] = data.get("drivers", [])
        if not drivers:
            lbl = tk.Label(
                self.rows_frame,
                text="Waiting for convoy drivers...",
                font=("Segoe UI", 9),
                fg=self.muted_color,
                bg=self.bg_color,
                pady=10
            )
            lbl.pack()
            return

        is_mi = (self.current_unit == "mi")

        for d in drivers:
            row_frame = tk.Frame(self.rows_frame, bg=self.bg_color)
            row_frame.pack(fill=tk.X, pady=2)

            rank = d.get("rank", 1)
            name = d.get("driver_name", "Driver")
            status = d.get("status", "DRIVING")
            speed = d.get("speed_mph", 0) if is_mi else d.get("speed_kmh", 0)
            dist = d.get("distance_mi", 0) if is_mi else d.get("distance_km", 0)
            delta = d.get("delta_mi", 0) if is_mi else d.get("delta_km", 0)
            eta = d.get("time_formatted", "--:--")
            unit_suffix = "mi" if is_mi else "km"
            speed_suffix = "mph" if is_mi else "km/h"

            is_local = (name.lower() == self.local_driver_name.lower())
            display_name = f"You ({name})" if is_local else name

            # Colors
            row_fg = "#ffffff" if is_local else self.text_color
            rank_fg = self.gold_color if rank == 1 else self.muted_color

            # 1. Rank & Name Label
            lbl_name = tk.Label(
                row_frame,
                text=f"#{rank:<2} {display_name:<12}",
                font=("Consolas" if not is_local else "Segoe UI", 9, "bold" if is_local else "normal"),
                fg=self.accent_color if is_local else row_fg,
                bg=self.bg_color,
                anchor="w",
                width=16
            )
            lbl_name.pack(side=tk.LEFT)

            # 2. Distance & Status
            if status == "FINISHED":
                fin_rank = d.get("finished_rank")
                badge = f"🏁 FINISHED (#{fin_rank})" if fin_rank else "🏁 FINISHED"
                lbl_dist = tk.Label(
                    row_frame,
                    text=badge,
                    font=("Segoe UI", 9, "bold"),
                    fg=self.green_color,
                    bg=self.bg_color
                )
                lbl_dist.pack(side=tk.LEFT, padx=(10, 0))
            else:
                dist_str = f"{round(dist):>4} {unit_suffix}"
                delta_str = f" (+{round(delta)} {unit_suffix})" if delta > 0 else f" ({eta})"

                lbl_dist = tk.Label(
                    row_frame,
                    text=f"{dist_str}{delta_str}",
                    font=("Consolas", 9),
                    fg=self.orange_color if delta > 0 else self.gold_color,
                    bg=self.bg_color,
                    anchor="w"
                )
                lbl_dist.pack(side=tk.LEFT, padx=(6, 0))

                # 3. Speed
                lbl_speed = tk.Label(
                    row_frame,
                    text=f"{round(speed):>3} {speed_suffix}",
                    font=("Consolas", 9),
                    fg=self.muted_color,
                    bg=self.bg_color,
                    anchor="e"
                )
                lbl_speed.pack(side=tk.RIGHT)

    # Window Dragging Event Handlers
    def _on_drag_start(self, event):
        if not self.is_locked:
            self._drag_start_x = event.x
            self._drag_start_y = event.y

    def _on_drag_motion(self, event):
        if not self.is_locked:
            x = self.root.winfo_x() + (event.x - self._drag_start_x)
            y = self.root.winfo_y() + (event.y - self._drag_start_y)
            self.root.geometry(f"+{x}+{y}")

    def _on_drag_end(self, event):
        if not self.is_locked:
            self.config.set("overlay_x", self.root.winfo_x(), auto_save=False)
            self.config.set("overlay_y", self.root.winfo_y(), auto_save=True)


if __name__ == "__main__":
    cfg = ConfigManager()
    cfg.set("overlay_locked", False)
    overlay = OverlayWindow(cfg)
    # Mock data
    mock_payload = {
        "room_code": "TRUCK-42",
        "route": {"source": "Berlin", "destination": "Paris"},
        "drivers": [
            {"rank": 1, "driver_name": "Alex", "distance_km": 142.0, "delta_km": 0.0, "speed_kmh": 85.0, "time_formatted": "1h 48m", "status": "DRIVING"},
            {"rank": 2, "driver_name": cfg.get("driver_name"), "distance_km": 146.0, "delta_km": 4.0, "speed_kmh": 82.0, "time_formatted": "1h 51m", "status": "DRIVING"},
            {"rank": 3, "driver_name": "Mike", "distance_km": 159.0, "delta_km": 17.0, "speed_kmh": 79.0, "time_formatted": "2h 01m", "status": "DRIVING"},
            {"rank": 4, "driver_name": "Leo", "distance_km": 0.0, "delta_km": 0.0, "speed_kmh": 0.0, "time_formatted": "--:--", "status": "FINISHED", "finished_rank": 1}
        ]
    }
    overlay.update_leaderboard(mock_payload)
    print("Overlay running. Press F10 to toggle lock.")
    overlay.root.mainloop()

