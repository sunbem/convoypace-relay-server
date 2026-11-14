"""
client/overlay_window.py - Compact, modern, frameless in-game HUD overlay for ConvoyPace.
Minimal corner widget: slim header with live dot and single-line driver rows
(rank · name · speed · remaining distance). Click-through mode and drag-to-move.
"""

import sys
import tkinter as tk
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from client.win32_utils import set_click_through, set_always_on_top
from client.config_manager import ConfigManager


class OverlayWindow:
    """In-game HUD overlay window for Euro Truck Simulator 2."""

    WIDTH = 300

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

        # ---- Modern dark palette ----
        self.bg_color = "#0d1117"          # deep background
        self.card_bg = "#161b22"           # driver row background
        self.card_bg_local = "#1a2332"     # local driver row (accent tint)
        self.border_locked = "#21262d"
        self.border_unlocked = "#58a6ff"
        self.text_color = "#e6edf3"
        self.muted_color = "#7d8590"
        self.accent_color = "#58a6ff"
        self.gold_color = "#e3b341"
        self.silver_color = "#c9d1d9"
        self.bronze_color = "#d29922"
        self.green_color = "#3fb950"
        self.orange_color = "#f0883e"
        self.red_color = "#f85149"

        # Window properties
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.92)
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

        # Saved position
        self._pos_x = self.config.get("overlay_x", 40)
        self._pos_y = self.config.get("overlay_y", 40)

        # Build UI layout
        self._build_ui()

        # Apply saved position + fixed width
        self._fit_window()

        # Bind dragging on the toplevel (catches clicks on any child widget)
        self.root.bind("<ButtonPress-1>", self._on_drag_start)
        self.root.bind("<B1-Motion>", self._on_drag_motion)
        self.root.bind("<ButtonRelease-1>", self._on_drag_end)

        # Apply saved lock state after window mapping
        self.root.after(150, self._apply_initial_state)

    # ------------------------------------------------------------------ #
    #  UI Construction
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        # Outer container with subtle border
        border_col = self.border_locked if self.is_locked else self.border_unlocked
        self.container = tk.Frame(
            self.root,
            bg=self.bg_color,
            highlightbackground=border_col,
            highlightthickness=1,
            padx=10,
            pady=7
        )
        self.container.pack(fill=tk.BOTH, expand=True)

        # ---- Header Row: Room code + live status ----
        self.header_frame = tk.Frame(self.container, bg=self.bg_color)
        self.header_frame.pack(fill=tk.X, pady=(0, 4))

        self.lbl_title = tk.Label(
            self.header_frame,
            text="🚚 --",
            font=("Segoe UI", 9, "bold"),
            fg=self.accent_color,
            bg=self.bg_color
        )
        self.lbl_title.pack(side=tk.LEFT)

        self.lbl_status = tk.Label(
            self.header_frame,
            text="● …",
            font=("Segoe UI", 7, "bold"),
            fg=self.muted_color,
            bg=self.bg_color
        )
        self.lbl_status.pack(side=tk.RIGHT)

        # ---- Dynamic rows container ----
        self.rows_frame = tk.Frame(self.container, bg=self.bg_color)
        self.rows_frame.pack(fill=tk.BOTH, expand=True)

        # Initial placeholder
        self._render_empty("Waiting for convoy drivers…")

    def _fit_window(self):
        """Resize the window to a fixed width and content-driven height."""
        try:
            self.root.update_idletasks()
            h = self.root.winfo_reqheight()
            self.root.geometry(f"{self.WIDTH}x{h}+{self._pos_x}+{self._pos_y}")
        except Exception:
            pass

    def _render_empty(self, text: str):
        """Show a centered placeholder message in the rows area."""
        for widget in self.rows_frame.winfo_children():
            widget.destroy()
        lbl = tk.Label(
            self.rows_frame,
            text=text,
            font=("Segoe UI", 8),
            fg=self.muted_color,
            bg=self.bg_color,
            pady=6
        )
        lbl.pack()

    # ------------------------------------------------------------------ #
    #  Window state
    # ------------------------------------------------------------------ #

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

        # Locked = subtle border; unlocked = accent border as a drag-mode hint
        self.container.config(
            highlightbackground=self.border_locked if locked else self.border_unlocked
        )
        set_click_through(self.root, locked)
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
        if connected:
            self.lbl_status.config(text="● LIVE", fg=self.green_color)
            # Refresh leaderboard on reconnect to ensure current state
            if self.leaderboard_data and self.leaderboard_data.get("drivers"):
                self.update_leaderboard(self.leaderboard_data)
        else:
            self.lbl_status.config(text="● OFF", fg=self.red_color)
            if not self.leaderboard_data or not self.leaderboard_data.get("drivers"):
                self._render_empty("Not connected.\nCheck Server URL in settings.")

    # ------------------------------------------------------------------ #
    #  Leaderboard rendering
    # ------------------------------------------------------------------ #

    def update_leaderboard(self, data: Dict[str, Any]):
        """Render fresh leaderboard data received from the relay server."""
        self.leaderboard_data = data
        room_code = data.get("room_code", "--")
        self.lbl_title.config(text=f"🚚 {room_code}")

        # Clear existing rows
        for widget in self.rows_frame.winfo_children():
            widget.destroy()

        drivers: List[Dict[str, Any]] = data.get("drivers", [])
        if not drivers:
            self._render_empty("Waiting for convoy drivers…")
            self._fit_window()
            return

        is_mi = (self.current_unit == "mi")

        for d in drivers:
            self._render_driver_row(d, is_mi)

        self._fit_window()

    def _render_driver_row(self, d: Dict[str, Any], is_mi: bool):
        """Render a compact single-line driver row: rank | name | speed | distance."""
        rank = d.get("rank", 1)
        name = d.get("driver_name", "Driver")
        status = d.get("status", "DRIVING")
        speed = d.get("speed_mph", 0) if is_mi else d.get("speed_kmh", 0)
        dist = d.get("distance_mi", 0) if is_mi else d.get("distance_km", 0)
        fin_rank = d.get("finished_rank")
        unit_suffix = "mi" if is_mi else "km"
        speed_suffix = "mph" if is_mi else "km/h"

        is_local = (name.lower() == self.local_driver_name.lower())

        # Row background (accent tint for the local driver)
        row_bg = self.card_bg_local if is_local else self.card_bg
        row = tk.Frame(self.rows_frame, bg=row_bg)
        row.pack(fill=tk.X, pady=1)

        # ---- Rank (colored number) ----
        rank_fg = {1: self.gold_color, 2: self.silver_color, 3: self.bronze_color}.get(
            rank, self.muted_color
        )
        tk.Label(
            row, text=str(rank),
            font=("Segoe UI", 8, "bold"),
            fg=rank_fg, bg=row_bg, width=2
        ).pack(side=tk.LEFT)

        # ---- Name (truncated to keep the row single-line) ----
        display_name = f"You ({name})" if is_local else name
        if len(display_name) > 14:
            display_name = display_name[:13] + "…"
        tk.Label(
            row, text=display_name,
            font=("Segoe UI", 8, "bold" if is_local else "normal"),
            fg=self.accent_color if is_local else self.text_color,
            bg=row_bg
        ).pack(side=tk.LEFT, padx=(3, 0))

        # ---- Distance (right-most, bold) ----
        if status == "FINISHED":
            dist_text = f"🏁 #{fin_rank}" if fin_rank else "🏁"
            dist_fg = self.green_color
        elif dist <= 0:
            dist_text = "—"
            dist_fg = self.muted_color
        else:
            dist_text = f"{round(dist)} {unit_suffix}"
            dist_fg = self.text_color
        tk.Label(
            row, text=dist_text,
            font=("Segoe UI", 9, "bold"),
            fg=dist_fg, bg=row_bg
        ).pack(side=tk.RIGHT, padx=(0, 1))

        # ---- Speed (right, muted) ----
        if status == "FINISHED":
            speed_text = ""
        elif status == "PAUSED":
            speed_text = "⏸"
        elif dist <= 0:
            speed_text = "…"
        else:
            speed_text = f"{round(speed)} {speed_suffix}"
        if speed_text:
            tk.Label(
                row, text=speed_text,
                font=("Segoe UI", 7),
                fg=self.muted_color, bg=row_bg
            ).pack(side=tk.RIGHT, padx=(6, 5))

    # ------------------------------------------------------------------ #
    #  Dragging (screen-coordinate based, works from any child widget)
    # ------------------------------------------------------------------ #

    def _on_drag_start(self, event):
        if not self.is_locked:
            self._drag_start_x = event.x_root - self.root.winfo_x()
            self._drag_start_y = event.y_root - self.root.winfo_y()

    def _on_drag_motion(self, event):
        if not self.is_locked:
            x = event.x_root - self._drag_start_x
            y = event.y_root - self._drag_start_y
            self.root.geometry(f"+{x}+{y}")
            self._pos_x, self._pos_y = x, y

    def _on_drag_end(self, event):
        if not self.is_locked:
            self._pos_x = self.root.winfo_x()
            self._pos_y = self.root.winfo_y()
            self.config.set("overlay_x", self._pos_x, auto_save=False)
            self.config.set("overlay_y", self._pos_y, auto_save=True)


if __name__ == "__main__":
    cfg = ConfigManager()
    cfg.set("overlay_locked", False)
    overlay = OverlayWindow(cfg)
    # Mock data
    mock_payload = {
        "room_code": "TRUCK-42",
        "route": {"source": "Berlin", "destination": "Paris", "cargo": "Electronics"},
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
