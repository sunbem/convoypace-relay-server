"""
client/overlay_window.py - Modern, minimal, frameless in-game HUD overlay for ConvoyPace.
Sleek dark card design with rank badges, two-line driver rows, status pills,
live connection indicator, click-through mode, and drag-to-move.
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

    WIDTH = 360

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
        self.card_bg = "#161b22"           # driver row card
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
            padx=14,
            pady=12
        )
        self.container.pack(fill=tk.BOTH, expand=True)

        # ---- Header Row: Room code + live status ----
        self.header_frame = tk.Frame(self.container, bg=self.bg_color)
        self.header_frame.pack(fill=tk.X, pady=(0, 2))

        self.lbl_title = tk.Label(
            self.header_frame,
            text="🚚 --",
            font=("Segoe UI", 11, "bold"),
            fg=self.accent_color,
            bg=self.bg_color
        )
        self.lbl_title.pack(side=tk.LEFT)

        self.lbl_status = tk.Label(
            self.header_frame,
            text="● CONNECTING",
            font=("Segoe UI", 8, "bold"),
            fg=self.muted_color,
            bg=self.bg_color
        )
        self.lbl_status.pack(side=tk.RIGHT)

        # ---- Route subtitle ----
        self.lbl_route = tk.Label(
            self.container,
            text="Connecting to relay…",
            font=("Segoe UI", 9),
            fg=self.muted_color,
            bg=self.bg_color,
            anchor="w"
        )
        self.lbl_route.pack(fill=tk.X, pady=(0, 8))

        # ---- Divider ----
        self.divider = tk.Frame(self.container, height=1, bg=self.border_locked)
        self.divider.pack(fill=tk.X, pady=(0, 8))

        # ---- Dynamic rows container ----
        self.rows_frame = tk.Frame(self.container, bg=self.bg_color)
        self.rows_frame.pack(fill=tk.BOTH, expand=True)

        # Initial placeholder
        self._render_empty("Waiting for convoy drivers…")

        # ---- Footer divider ----
        self.footer_divider = tk.Frame(self.container, height=1, bg=self.border_locked)
        self.footer_divider.pack(fill=tk.X, pady=(8, 6))

        # ---- Footer Row: lock status + hotkey hint ----
        self.footer_frame = tk.Frame(self.container, bg=self.bg_color)
        self.footer_frame.pack(fill=tk.X)

        self.lbl_lock_status = tk.Label(
            self.footer_frame,
            text="🔒 Locked",
            font=("Segoe UI", 8, "bold"),
            fg=self.green_color if self.is_locked else self.orange_color,
            bg=self.bg_color
        )
        self.lbl_lock_status.pack(side=tk.LEFT)

        self.lbl_hotkeys = tk.Label(
            self.footer_frame,
            text="F9 Hide · F10 Lock",
            font=("Segoe UI", 8),
            fg=self.muted_color,
            bg=self.bg_color
        )
        self.lbl_hotkeys.pack(side=tk.RIGHT)

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
            font=("Segoe UI", 9),
            fg=self.muted_color,
            bg=self.bg_color,
            pady=12
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

        if locked:
            self.container.config(highlightbackground=self.border_locked)
            self.lbl_hotkeys.config(text="F9 Hide · F10 Lock")
            self.lbl_lock_status.config(text="🔒 Locked", fg=self.green_color)
            set_click_through(self.root, True)
        else:
            self.container.config(highlightbackground=self.border_unlocked)
            self.lbl_hotkeys.config(text="F9 Hide · F10 Unlock")
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
        if connected:
            self.lbl_status.config(text="● LIVE", fg=self.green_color)
        else:
            self.lbl_status.config(text="● OFFLINE", fg=self.red_color)
            if not self.leaderboard_data or not self.leaderboard_data.get("drivers"):
                self._render_empty("Relay server not connected.\nCheck Server URL in settings.")

    # ------------------------------------------------------------------ #
    #  Leaderboard rendering
    # ------------------------------------------------------------------ #

    def update_leaderboard(self, data: Dict[str, Any]):
        """Render fresh leaderboard data received from the relay server."""
        self.leaderboard_data = data
        room_code = data.get("room_code", "--")
        self.lbl_title.config(text=f"🚚 {room_code}")

        # Update route subtitle
        route = data.get("route", {})
        src = route.get("source", "")
        dst = route.get("destination", "")
        cargo = route.get("cargo", "")
        if dst:
            route_str = f"{src} → {dst}" if src else f"→ {dst}"
            if cargo:
                route_str += f"  ·  📦 {cargo}"
        else:
            route_str = "Free Roam"
        self.lbl_route.config(text=route_str)

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
        """Render a single driver row: rank badge | name+meta | distance+delta."""
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

        # Row card background
        row_bg = self.card_bg_local if is_local else self.card_bg
        row_frame = tk.Frame(self.rows_frame, bg=row_bg, padx=10, pady=7)
        row_frame.pack(fill=tk.X, pady=2)

        # ---- Rank badge ----
        if rank == 1:
            rank_bg, rank_fg = self.gold_color, "#0d1117"
        elif rank == 2:
            rank_bg, rank_fg = self.silver_color, "#0d1117"
        elif rank == 3:
            rank_bg, rank_fg = self.bronze_color, "#0d1117"
        else:
            rank_bg, rank_fg = self.border_locked, self.muted_color

        badge = tk.Frame(row_frame, bg=rank_bg, width=26, height=26)
        badge.pack(side=tk.LEFT, padx=(0, 10))
        badge.pack_propagate(False)
        tk.Label(
            badge, text=str(rank),
            font=("Segoe UI", 10, "bold"),
            fg=rank_fg, bg=rank_bg
        ).pack(expand=True)

        # ---- Name + meta ----
        info = tk.Frame(row_frame, bg=row_bg)
        info.pack(side=tk.LEFT, fill=tk.X, expand=True)

        name_fg = self.accent_color if is_local else self.text_color
        tk.Label(
            info, text=display_name,
            font=("Segoe UI", 10, "bold"),
            fg=name_fg, bg=row_bg, anchor="w"
        ).pack(anchor="w")

        # Meta line: speed + ETA, or status text
        if status == "FINISHED":
            meta_text = "🏁 Finished"
            meta_fg = self.green_color
        elif status == "PAUSED":
            meta_text = f"⏸ Paused · {eta}"
            meta_fg = self.orange_color
        elif dist <= 0:
            meta_text = "Syncing…"
            meta_fg = self.muted_color
        else:
            meta_text = f"{round(speed)} {speed_suffix} · ETA {eta}"
            meta_fg = self.muted_color

        tk.Label(
            info, text=meta_text,
            font=("Segoe UI", 8),
            fg=meta_fg, bg=row_bg, anchor="w"
        ).pack(anchor="w")

        # ---- Distance + delta ----
        dist_frame = tk.Frame(row_frame, bg=row_bg)
        dist_frame.pack(side=tk.RIGHT)

        if status == "FINISHED":
            fin_rank = d.get("finished_rank")
            dist_text = f"#{fin_rank}" if fin_rank else "🏁"
            dist_fg = self.green_color
            delta_text = "Done"
            delta_fg = self.green_color
        elif dist <= 0:
            dist_text = "—"
            dist_fg = self.muted_color
            delta_text = ""
            delta_fg = self.muted_color
        else:
            dist_text = f"{round(dist)} {unit_suffix}"
            dist_fg = self.text_color
            if delta > 0:
                delta_text = f"+{round(delta)} {unit_suffix}"
                delta_fg = self.orange_color
            elif rank == 1:
                delta_text = "Leader"
                delta_fg = self.gold_color
            else:
                delta_text = ""
                delta_fg = self.muted_color

        tk.Label(
            dist_frame, text=dist_text,
            font=("Segoe UI", 11, "bold"),
            fg=dist_fg, bg=row_bg, anchor="e"
        ).pack(anchor="e")
        if delta_text:
            tk.Label(
                dist_frame, text=delta_text,
                font=("Segoe UI", 8),
                fg=delta_fg, bg=row_bg, anchor="e"
            ).pack(anchor="e")

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
