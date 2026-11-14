"""
client/control_panel.py - Main Control Panel & Settings GUI for ConvoyPace.
Modern card-based dark UI with 1-click plugin setup, room creation, units toggle,
and live relay/telemetry status.
"""

import os
import sys
import webbrowser
import tkinter as tk
from tkinter import messagebox
from pathlib import Path
from typing import Callable, Optional

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from client.config_manager import ConfigManager
from client.steam_detector import detect_ets2_path, is_plugin_installed
from client.plugin_installer import install_plugin, uninstall_plugin
from server.relay_server import generate_room_code


class ControlPanel:
    """Settings, connection manager, and 1-click plugin installer UI."""

    def __init__(
        self,
        root: tk.Tk,
        config: ConfigManager,
        on_join_room: Optional[Callable[[str, str, str], None]] = None,
        on_unit_changed: Optional[Callable[[str], None]] = None,
        on_simulation_toggled: Optional[Callable[[bool], None]] = None,
        on_toggle_overlay_visibility: Optional[Callable[[], None]] = None,
        on_toggle_overlay_lock: Optional[Callable[[], None]] = None
    ):
        self.root = root
        self.config = config
        self.on_join_room = on_join_room
        self.on_unit_changed = on_unit_changed
        self.on_simulation_toggled = on_simulation_toggled
        self.on_toggle_overlay_visibility = on_toggle_overlay_visibility
        self.on_toggle_overlay_lock = on_toggle_overlay_lock

        self.root.title("ConvoyPace — ETS2 Convoy Tracker")
        self.root.geometry("480x620")
        self.root.minsize(460, 580)

        # ---- Palette (matches the in-game overlay) ----
        self.bg_color = "#0d1117"
        self.card_bg = "#161b22"
        self.border_color = "#21262d"
        self.text_color = "#e6edf3"
        self.accent_color = "#58a6ff"
        self.gold_color = "#e3b341"
        self.green_color = "#3fb950"
        self.orange_color = "#f0883e"
        self.red_color = "#f85149"
        self.muted_color = "#7d8590"
        self.entry_bg = "#0d1117"
        self.btn_secondary = "#21262d"
        self.btn_primary = "#1f6feb"
        self.btn_success = "#238636"

        self.root.configure(bg=self.bg_color)

        self._build_ui()
        self.refresh_plugin_status()

    # ------------------------------------------------------------------ #
    #  UI helpers
    # ------------------------------------------------------------------ #

    def _card(self, parent: tk.Widget, title: str) -> tk.Frame:
        """Create a rounded-feel card with an uppercase muted section title."""
        card = tk.Frame(
            parent,
            bg=self.card_bg,
            highlightbackground=self.border_color,
            highlightthickness=1,
            padx=14,
            pady=12
        )
        card.pack(fill=tk.X, pady=(0, 12))
        if title:
            tk.Label(
                card, text=title.upper(),
                font=("Segoe UI", 8, "bold"),
                fg=self.muted_color, bg=self.card_bg, anchor="w"
            ).pack(fill=tk.X, pady=(0, 8))
        return card

    def _field_label(self, parent: tk.Widget, text: str):
        return tk.Label(
            parent, text=text,
            font=("Segoe UI", 7, "bold"),
            fg=self.muted_color, bg=self.card_bg, anchor="w"
        )

    def _entry(self, parent: tk.Widget, textvariable, font_size: int = 9, bold: bool = False):
        return tk.Entry(
            parent,
            textvariable=textvariable,
            font=("Segoe UI", font_size, "bold" if bold else "normal"),
            bg=self.entry_bg,
            fg=self.text_color,
            insertbackground=self.text_color,
            relief=tk.FLAT,
            highlightbackground=self.border_color,
            highlightthickness=1,
            highlightcolor=self.accent_color
        )

    def _button(self, parent: tk.Widget, text: str, command, kind: str = "secondary",
                font_size: int = 9) -> tk.Button:
        bg, fg = {
            "primary": (self.btn_primary, "#ffffff"),
            "success": (self.btn_success, "#ffffff"),
            "secondary": (self.btn_secondary, "#c9d1d9"),
        }[kind]
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg, fg=fg,
            activebackground=bg, activeforeground=fg,
            font=("Segoe UI", font_size, "bold"),
            relief=tk.FLAT, bd=0,
            padx=12, pady=4,
            cursor="hand2"
        )

    def _build_ui(self):
        # Header banner
        header = tk.Frame(self.root, bg=self.card_bg, padx=16, pady=12)
        header.pack(fill=tk.X)

        tk.Label(
            header, text="🚚 ConvoyPace",
            font=("Segoe UI", 15, "bold"),
            fg=self.text_color, bg=self.card_bg
        ).pack(side=tk.LEFT)

        tk.Label(
            header, text="ETS2 Live Leaderboard & Overlay",
            font=("Segoe UI", 8),
            fg=self.muted_color, bg=self.card_bg
        ).pack(side=tk.LEFT, padx=(8, 0), pady=(4, 0))

        # Main content container
        content = tk.Frame(self.root, bg=self.bg_color, padx=14, pady=12)
        content.pack(fill=tk.BOTH, expand=True)

        # --- Section 1: Convoy Connection ---
        sec_room = self._card(content, "Convoy Connection")

        self._field_label(sec_room, "DRIVER NAME").pack(fill=tk.X)
        self.var_driver_name = tk.StringVar(value=self.config.get("driver_name", "Driver"))
        self._entry(sec_room, self.var_driver_name).pack(fill=tk.X, ipady=3, pady=(2, 8))

        self._field_label(sec_room, "ROOM CODE").pack(fill=tk.X)
        f_code = tk.Frame(sec_room, bg=self.card_bg)
        f_code.pack(fill=tk.X, pady=(2, 8))
        self.var_room_code = tk.StringVar(value=self.config.get("last_room_code", "TRUCK-42"))
        self._entry(f_code, self.var_room_code, font_size=10, bold=True).pack(
            side=tk.LEFT, fill=tk.X, expand=True, ipady=3
        )
        self._button(f_code, "✨ Create", self._on_create_convoy, "success").pack(side=tk.LEFT, padx=(6, 0))
        self._button(f_code, "🚀 Join", self._on_join_convoy, "primary").pack(side=tk.LEFT, padx=(4, 0))

        self._field_label(sec_room, "SERVER URL").pack(fill=tk.X)
        self.var_server_url = tk.StringVar(
            value=self.config.get("server_url", "https://convoypace-relay-server.onrender.com")
        )
        self._entry(sec_room, self.var_server_url, font_size=8).pack(fill=tk.X, ipady=3, pady=(2, 8))

        f_links = tk.Frame(sec_room, bg=self.card_bg)
        f_links.pack(fill=tk.X)
        self._button(f_links, "☁️ Use Cloud Server", self._on_use_cloud_server, "secondary").pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4)
        )
        self._button(f_links, "🌐 Open Web HUD", self._on_open_web_hud, "secondary").pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0)
        )

        # --- Section 2: 1-Click Plugin Setup ---
        sec_plugin = self._card(content, "ETS2 Telemetry Plugin (Zero-Config)")

        self.lbl_ets2_path = tk.Label(
            sec_plugin,
            text="Detecting ETS2 installation…",
            font=("Segoe UI", 8),
            fg=self.muted_color,
            bg=self.card_bg,
            anchor="w",
            wraplength=410,
            justify=tk.LEFT
        )
        self.lbl_ets2_path.pack(fill=tk.X, pady=(0, 6))

        f_plugin_action = tk.Frame(sec_plugin, bg=self.card_bg)
        f_plugin_action.pack(fill=tk.X)

        self.lbl_plugin_status = tk.Label(
            f_plugin_action,
            text="Checking…",
            font=("Segoe UI", 9, "bold"),
            fg=self.orange_color,
            bg=self.card_bg
        )
        self.lbl_plugin_status.pack(side=tk.LEFT)

        self.btn_install_plugin = self._button(
            f_plugin_action, "⚡ 1-Click Install", self._on_install_plugin, "success"
        )
        self.btn_install_plugin.pack(side=tk.RIGHT)

        # --- Section 3: Preferences & Overlay Controls ---
        sec_pref = self._card(content, "Preferences & Overlay")

        f_units = tk.Frame(sec_pref, bg=self.card_bg)
        f_units.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            f_units, text="UNITS",
            font=("Segoe UI", 7, "bold"),
            fg=self.muted_color, bg=self.card_bg
        ).pack(side=tk.LEFT, padx=(0, 10))

        self.var_unit = tk.StringVar(value=self.config.get("unit", "km"))
        radio_kwargs = dict(
            font=("Segoe UI", 9), bg=self.card_bg, fg=self.text_color,
            selectcolor=self.entry_bg, activebackground=self.card_bg,
            activeforeground=self.text_color, relief=tk.FLAT, highlightthickness=0
        )
        tk.Radiobutton(
            f_units, text="Kilometers (km/h)", variable=self.var_unit, value="km",
            command=self._on_unit_toggled, **radio_kwargs
        ).pack(side=tk.LEFT, padx=(0, 8))
        tk.Radiobutton(
            f_units, text="Miles (mph)", variable=self.var_unit, value="mi",
            command=self._on_unit_toggled, **radio_kwargs
        ).pack(side=tk.LEFT)

        self.var_sim = tk.BooleanVar(value=self.config.get("simulation_mode", False))
        tk.Checkbutton(
            sec_pref,
            text="🚗 Demo / Simulation Mode (Test without ETS2)",
            variable=self.var_sim,
            command=self._on_sim_toggled,
            font=("Segoe UI", 8),
            fg=self.gold_color,
            bg=self.card_bg,
            selectcolor=self.entry_bg,
            activebackground=self.card_bg,
            activeforeground=self.gold_color,
            relief=tk.FLAT,
            highlightthickness=0
        ).pack(anchor="w", pady=(0, 10))

        f_controls = tk.Frame(sec_pref, bg=self.card_bg)
        f_controls.pack(fill=tk.X)

        self.btn_toggle_vis = self._button(
            f_controls, "👁 Hide/Show Overlay", self._on_toggle_visibility, "secondary", font_size=8
        )
        self.btn_toggle_vis.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        self.btn_toggle_lock = self._button(
            f_controls, "🔒 Lock/Unlock Drag", self._on_toggle_lock, "secondary", font_size=8
        )
        self.btn_toggle_lock.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        # Bottom status bar
        status_bar = tk.Frame(self.root, bg=self.card_bg, padx=14, pady=6)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.lbl_net_status = tk.Label(
            status_bar,
            text="● Relay: Disconnected",
            font=("Segoe UI", 8),
            fg=self.orange_color,
            bg=self.card_bg
        )
        self.lbl_net_status.pack(side=tk.LEFT)

        self.lbl_telemetry_status = tk.Label(
            status_bar,
            text="● ETS2: Waiting",
            font=("Segoe UI", 8),
            fg=self.muted_color,
            bg=self.card_bg
        )
        self.lbl_telemetry_status.pack(side=tk.RIGHT)

    def refresh_plugin_status(self):
        """Scan ETS2 installation and update plugin status label and install button."""
        detected = detect_ets2_path()
        if detected:
            self.lbl_ets2_path.config(text=f"📁 ETS2: {detected}")
            if is_plugin_installed(detected):
                self.lbl_plugin_status.config(text="✅ Plugin Installed", fg=self.green_color)
                self.btn_install_plugin.config(text="Reinstall Plugin", bg=self.btn_secondary)
            else:
                self.lbl_plugin_status.config(text="⚠️ Plugin Not Installed", fg=self.orange_color)
                self.btn_install_plugin.config(text="⚡ 1-Click Install", bg=self.btn_success)
        else:
            self.lbl_ets2_path.config(text="❌ ETS2 installation not found automatically.")
            self.lbl_plugin_status.config(text="Game Not Found", fg=self.orange_color)

    def set_network_status(self, text: str, connected: bool):
        fg = self.green_color if connected else self.orange_color
        self.lbl_net_status.config(text=f"● Relay: {text}", fg=fg)

    def set_telemetry_status(self, text: str, connected: bool):
        fg = self.green_color if connected else self.muted_color
        self.lbl_telemetry_status.config(text=f"● ETS2: {text}", fg=fg)

    def _on_use_cloud_server(self):
        """Switch to the hosted (Render) relay server."""
        cloud_url = "https://convoypace-relay-server.onrender.com"
        self.var_server_url.set(cloud_url)
        self.config.set("server_url", cloud_url)
        if self.on_join_room:
            self.on_join_room(self.var_room_code.get().strip().upper(), self.var_driver_name.get().strip() or "Driver", cloud_url)

    def _on_create_convoy(self):
        new_code = generate_room_code()
        self.var_room_code.set(new_code)
        self._on_join_convoy()

        server_url = self.var_server_url.get().strip() or "https://convoypace-relay-server.onrender.com"
        share_url = f"{server_url.rstrip('/')}/room/{new_code}"
        self.root.clipboard_clear()
        self.root.clipboard_append(share_url)
        messagebox.showinfo("Convoy Created", f"Room Code: {new_code}\nWeb HUD Link: {share_url}\n\nCopied link to clipboard! Share it with your friends.")

    def _on_join_convoy(self):
        code = self.var_room_code.get().strip().upper()
        name = self.var_driver_name.get().strip() or "Driver"
        server_url = self.var_server_url.get().strip() or "https://convoypace-relay-server.onrender.com"
        self.config.set("last_room_code", code, auto_save=False)
        self.config.set("driver_name", name, auto_save=False)
        self.config.set("server_url", server_url, auto_save=True)
        if self.on_join_room:
            self.on_join_room(code, name, server_url)

    def _on_open_web_hud(self):
        server_url = self.config.get("server_url", "https://convoypace-relay-server.onrender.com")
        code = self.var_room_code.get().strip().upper()
        clean_url = server_url.rstrip("/")
        full_url = f"{clean_url}/room/{code}"
        webbrowser.open(full_url)

    def _on_install_plugin(self):
        res = install_plugin()
        if res["success"]:
            messagebox.showinfo("Installation Complete", res["message"])
        else:
            messagebox.showerror("Installation Error", res["message"])
        self.refresh_plugin_status()

    def _on_unit_toggled(self):
        u = self.var_unit.get()
        self.config.set("unit", u)
        if self.on_unit_changed:
            self.on_unit_changed(u)

    def _on_sim_toggled(self):
        sim = self.var_sim.get()
        self.config.set("simulation_mode", sim)
        if self.on_simulation_toggled:
            self.on_simulation_toggled(sim)

    def _on_toggle_visibility(self):
        if self.on_toggle_overlay_visibility:
            self.on_toggle_overlay_visibility()

    def _on_toggle_lock(self):
        if self.on_toggle_overlay_lock:
            self.on_toggle_overlay_lock()
