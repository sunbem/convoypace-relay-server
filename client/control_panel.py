"""
client/control_panel.py - Main Control Panel & Settings GUI for ConvoyPace.
Provides 1-click plugin setup, room creation, units toggle, and live status.
"""

import os
import sys
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from typing import Callable, Optional

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from client.config_manager import ConfigManager
from client.steam_detector import detect_ets2_path, is_plugin_installed
from client.plugin_installer import install_plugin, uninstall_plugin
from client.embedded_server import get_local_ip
from server.relay_server import generate_room_code


class ControlPanel:
    """Settings, connection manager, and 1-click plugin installer UI."""

    def __init__(
        self,
        root: tk.Tk,
        config: ConfigManager,
        on_join_room: Optional[Callable[[str, str, str], None]] = None,
        on_toggle_host_server: Optional[Callable[[bool], None]] = None,
        on_unit_changed: Optional[Callable[[str], None]] = None,
        on_simulation_toggled: Optional[Callable[[bool], None]] = None,
        on_toggle_overlay_visibility: Optional[Callable[[], None]] = None,
        on_toggle_overlay_lock: Optional[Callable[[], None]] = None
    ):
        self.root = root
        self.config = config
        self.on_join_room = on_join_room
        self.on_toggle_host_server = on_toggle_host_server
        self.on_unit_changed = on_unit_changed
        self.on_simulation_toggled = on_simulation_toggled
        self.on_toggle_overlay_visibility = on_toggle_overlay_visibility
        self.on_toggle_overlay_lock = on_toggle_overlay_lock

        self.root.title("ConvoyPace - ETS2 Convoy Tracker")
        self.root.geometry("490x640")
        self.root.minsize(470, 620)

        # Dark theme styling
        self.bg_color = "#161b22"
        self.card_bg = "#0d1117"
        self.border_color = "#30363d"
        self.text_color = "#f0f6fc"
        self.accent_color = "#58a6ff"
        self.gold_color = "#f1e05a"
        self.green_color = "#3fb950"
        self.orange_color = "#ffa657"
        self.muted_color = "#8b949e"

        self.root.configure(bg=self.bg_color)

        self._build_ui()
        self.refresh_plugin_status()

    def _build_ui(self):
        # Header Banner
        header = tk.Frame(self.root, bg=self.card_bg, padx=16, pady=12)
        header.pack(fill=tk.X)

        lbl_logo = tk.Label(
            header,
            text="🚚 ConvoyPace",
            font=("Segoe UI", 16, "bold"),
            fg=self.accent_color,
            bg=self.card_bg
        )
        lbl_logo.pack(side=tk.LEFT)

        lbl_sub = tk.Label(
            header,
            text="ETS2 Live Leaderboard & Overlay",
            font=("Segoe UI", 9),
            fg=self.muted_color,
            bg=self.card_bg
        )
        lbl_sub.pack(side=tk.LEFT, padx=(8, 0), pady=(4, 0))

        # Main scrollable/padded container
        content = tk.Frame(self.root, bg=self.bg_color, padx=16, pady=12)
        content.pack(fill=tk.BOTH, expand=True)

        # --- Section 1: Convoy Room & Driver ---
        sec_room = tk.LabelFrame(
            content,
            text="  Convoy Connection  ",
            font=("Segoe UI", 9, "bold"),
            bg=self.bg_color,
            fg=self.text_color,
            padx=12,
            pady=10
        )
        sec_room.pack(fill=tk.X, pady=(0, 10))

        # Driver Name
        f_name = tk.Frame(sec_room, bg=self.bg_color)
        f_name.pack(fill=tk.X, pady=(0, 6))
        tk.Label(f_name, text="Driver Name:", font=("Segoe UI", 9), fg=self.text_color, bg=self.bg_color, width=12, anchor="w").pack(side=tk.LEFT)
        self.var_driver_name = tk.StringVar(value=self.config.get("driver_name", "Driver"))
        ent_name = tk.Entry(f_name, textvariable=self.var_driver_name, font=("Segoe UI", 9), bg="#21262d", fg="#fff", insertbackground="#fff", relief=tk.FLAT)
        ent_name.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)

        # Server URL
        f_server = tk.Frame(sec_room, bg=self.bg_color)
        f_server.pack(fill=tk.X, pady=(0, 6))
        tk.Label(f_server, text="Server URL:", font=("Segoe UI", 9), fg=self.text_color, bg=self.bg_color, width=12, anchor="w").pack(side=tk.LEFT)
        self.var_server_url = tk.StringVar(value=self.config.get("server_url", "http://localhost:8080"))
        ent_server = tk.Entry(f_server, textvariable=self.var_server_url, font=("Segoe UI", 9), bg="#21262d", fg="#fff", insertbackground="#fff", relief=tk.FLAT)
        ent_server.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)

        # Host Convoy Toggle (Starts Built-in Server)
        self.var_host_mode = tk.BooleanVar(value=bool(self.config.get("host_mode", True)))
        chk_host = tk.Checkbutton(
            sec_room,
            text="⚡ Host Convoy on this PC (Run Built-in Server)",
            variable=self.var_host_mode,
            command=self._on_host_mode_toggled,
            font=("Segoe UI", 9, "bold"),
            fg=self.green_color,
            bg=self.bg_color,
            selectcolor=self.card_bg
        )
        chk_host.pack(anchor="w", pady=(0, 6))

        # Cloud server preset (Render) - disables local host mode and sets cloud URL
        f_cloud = tk.Frame(sec_room, bg=self.bg_color)
        f_cloud.pack(fill=tk.X, pady=(0, 6))
        btn_cloud = tk.Button(
            f_cloud,
            text="☁️ Use Cloud Server (Render)",
            command=self._on_use_cloud_server,
            bg="#30363d",
            fg="#c9d1d9",
            font=("Segoe UI", 8),
            relief=tk.FLAT,
            padx=8,
            cursor="hand2"
        )
        btn_cloud.pack(side=tk.LEFT)
        tk.Label(
            f_cloud,
            text="Connects to your Render relay (set CONVOYPACE_SERVER_URL env or edit URL below)",
            font=("Segoe UI", 7),
            fg=self.muted_color,
            bg=self.bg_color,
            wraplength=300,
            justify=tk.LEFT
        ).pack(side=tk.LEFT, padx=(8, 0))

        # Shareable Link Banner (shows LAN IP when hosting)
        self.f_share = tk.Frame(sec_room, bg="#1c2128", padx=8, pady=6, highlightbackground="#30363d", highlightthickness=1)
        self.f_share.pack(fill=tk.X, pady=(0, 8))

        self.lbl_share_link = tk.Label(
            self.f_share,
            text="",
            font=("Segoe UI", 8),
            fg=self.accent_color,
            bg="#1c2128",
            anchor="w"
        )
        self.lbl_share_link.pack(side=tk.LEFT, fill=tk.X, expand=True)

        btn_copy_link = tk.Button(
            self.f_share,
            text="📋 Copy Link",
            command=self._on_copy_share_link,
            font=("Segoe UI", 8),
            bg="#30363d",
            fg="#c9d1d9",
            relief=tk.FLAT,
            padx=6,
            cursor="hand2"
        )
        btn_copy_link.pack(side=tk.RIGHT)

        # Room Code + Buttons
        f_code = tk.Frame(sec_room, bg=self.bg_color)
        f_code.pack(fill=tk.X, pady=(0, 8))
        tk.Label(f_code, text="Room Code:", font=("Segoe UI", 9), fg=self.text_color, bg=self.bg_color, width=12, anchor="w").pack(side=tk.LEFT)
        self.var_room_code = tk.StringVar(value=self.config.get("last_room_code", "TRUCK-42"))
        ent_code = tk.Entry(f_code, textvariable=self.var_room_code, font=("Segoe UI", 10, "bold"), bg="#21262d", fg=self.accent_color, insertbackground="#fff", relief=tk.FLAT)
        ent_code.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)

        btn_create = tk.Button(
            f_code,
            text="✨ Create",
            command=self._on_create_convoy,
            bg="#238636",
            fg="#fff",
            font=("Segoe UI", 8, "bold"),
            relief=tk.FLAT,
            padx=8,
            cursor="hand2"
        )
        btn_create.pack(side=tk.LEFT, padx=(6, 0))

        btn_join = tk.Button(
            f_code,
            text="🚀 Join",
            command=self._on_join_convoy,
            bg="#1f6feb",
            fg="#fff",
            font=("Segoe UI", 8, "bold"),
            relief=tk.FLAT,
            padx=10,
            cursor="hand2"
        )
        btn_join.pack(side=tk.LEFT, padx=(4, 0))

        # Secondary Monitor Web HUD Link
        f_web = tk.Frame(sec_room, bg=self.bg_color)
        f_web.pack(fill=tk.X)
        btn_web = tk.Button(
            f_web,
            text="🌐 Open Secondary Monitor / Phone Web HUD",
            command=self._on_open_web_hud,
            bg="#30363d",
            fg="#c9d1d9",
            font=("Segoe UI", 8),
            relief=tk.FLAT,
            cursor="hand2"
        )
        btn_web.pack(fill=tk.X, ipady=2)

        self._update_share_banner()

        # --- Section 2: 1-Click Plugin Setup ---
        sec_plugin = tk.LabelFrame(
            content,
            text="  ETS2 Telemetry Plugin (Zero-Config)  ",
            font=("Segoe UI", 9, "bold"),
            bg=self.bg_color,
            fg=self.text_color,
            padx=12,
            pady=10
        )
        sec_plugin.pack(fill=tk.X, pady=(0, 10))

        self.lbl_ets2_path = tk.Label(
            sec_plugin,
            text="Detecting ETS2 installation...",
            font=("Segoe UI", 8),
            fg=self.muted_color,
            bg=self.bg_color,
            anchor="w",
            wraplength=420,
            justify=tk.LEFT
        )
        self.lbl_ets2_path.pack(fill=tk.X, pady=(0, 4))

        f_plugin_action = tk.Frame(sec_plugin, bg=self.bg_color)
        f_plugin_action.pack(fill=tk.X, pady=(4, 0))

        self.lbl_plugin_status = tk.Label(
            f_plugin_action,
            text="Checking...",
            font=("Segoe UI", 9, "bold"),
            fg=self.orange_color,
            bg=self.bg_color
        )
        self.lbl_plugin_status.pack(side=tk.LEFT)

        self.btn_install_plugin = tk.Button(
            f_plugin_action,
            text="⚡ 1-Click Install Plugin",
            command=self._on_install_plugin,
            bg="#238636",
            fg="#fff",
            font=("Segoe UI", 8, "bold"),
            relief=tk.FLAT,
            padx=10,
            cursor="hand2"
        )
        self.btn_install_plugin.pack(side=tk.RIGHT)

        # --- Section 3: Overlay & Preferences ---
        sec_pref = tk.LabelFrame(
            content,
            text="  Preferences & Overlay Controls  ",
            font=("Segoe UI", 9, "bold"),
            bg=self.bg_color,
            fg=self.text_color,
            padx=12,
            pady=10
        )
        sec_pref.pack(fill=tk.X, pady=(0, 10))

        # Units & Simulation row
        f_units = tk.Frame(sec_pref, bg=self.bg_color)
        f_units.pack(fill=tk.X, pady=(0, 6))

        tk.Label(f_units, text="Units:", font=("Segoe UI", 9), fg=self.text_color, bg=self.bg_color).pack(side=tk.LEFT, padx=(0, 8))
        self.var_unit = tk.StringVar(value=self.config.get("unit", "km"))
        r_km = tk.Radiobutton(f_units, text="Kilometers (km/h)", variable=self.var_unit, value="km", command=self._on_unit_toggled, bg=self.bg_color, fg=self.text_color, selectcolor=self.card_bg)
        r_km.pack(side=tk.LEFT, padx=(0, 8))
        r_mi = tk.Radiobutton(f_units, text="Miles (mph)", variable=self.var_unit, value="mi", command=self._on_unit_toggled, bg=self.bg_color, fg=self.text_color, selectcolor=self.card_bg)
        r_mi.pack(side=tk.LEFT)

        self.var_sim = tk.BooleanVar(value=self.config.get("simulation_mode", False))
        chk_sim = tk.Checkbutton(
            sec_pref,
            text="🚗 Demo / Simulation Mode (Test without ETS2)",
            variable=self.var_sim,
            command=self._on_sim_toggled,
            font=("Segoe UI", 8),
            fg=self.gold_color,
            bg=self.bg_color,
            selectcolor=self.card_bg
        )
        chk_sim.pack(anchor="w", pady=(0, 8))

        # Overlay Hotkeys & Manual Controls
        f_controls = tk.Frame(sec_pref, bg=self.bg_color)
        f_controls.pack(fill=tk.X)

        self.btn_toggle_vis = tk.Button(
            f_controls,
            text="👁 Toggle Overlay (Ctrl+F9 / Ins)",
            command=self._on_toggle_visibility,
            bg="#30363d",
            fg="#c9d1d9",
            font=("Segoe UI", 8),
            relief=tk.FLAT,
            cursor="hand2"
        )
        self.btn_toggle_vis.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        self.btn_toggle_lock = tk.Button(
            f_controls,
            text="🔓 Lock/Unlock Drag (Ctrl+F10 / Home)",
            command=self._on_toggle_lock,
            bg="#30363d",
            fg="#c9d1d9",
            font=("Segoe UI", 8),
            relief=tk.FLAT,
            cursor="hand2"
        )
        self.btn_toggle_lock.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        # Bottom Status Bar
        status_bar = tk.Frame(self.root, bg=self.card_bg, padx=12, pady=6)
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
                self.btn_install_plugin.config(text="Reinstall Plugin", bg="#30363d")
            else:
                self.lbl_plugin_status.config(text="⚠️ Plugin Not Installed", fg=self.orange_color)
                self.btn_install_plugin.config(text="⚡ 1-Click Install Plugin", bg="#238636")
        else:
            self.lbl_ets2_path.config(text="❌ ETS2 installation not found automatically.")
            self.lbl_plugin_status.config(text="Game Not Found", fg=self.orange_color)

    def set_network_status(self, text: str, connected: bool):
        fg = self.green_color if connected else self.orange_color
        self.lbl_net_status.config(text=f"● Relay: {text}", fg=fg)

    def set_telemetry_status(self, text: str, connected: bool):
        fg = self.green_color if connected else self.muted_color
        self.lbl_telemetry_status.config(text=f"● ETS2: {text}", fg=fg)

    def _update_share_banner(self):
        code = self.var_room_code.get().strip().upper()
        if self.var_host_mode.get():
            lan_ip = get_local_ip()
            share_url = f"http://{lan_ip}:8080/room/{code}"
            self.lbl_share_link.config(text=f"Share: {share_url}")
            self.f_share.pack(fill=tk.X, pady=(0, 8))
        else:
            self.f_share.pack_forget()

    def _on_copy_share_link(self):
        code = self.var_room_code.get().strip().upper()
        lan_ip = get_local_ip()
        share_url = f"http://{lan_ip}:8080/room/{code}"
        self.root.clipboard_clear()
        self.root.clipboard_append(share_url)
        messagebox.showinfo("Copied", f"Convoy link copied to clipboard:\n{share_url}\n\nSend this link to friends so they can view the live leaderboard or join with Room Code '{code}'!")

    def _on_host_mode_toggled(self):
        is_host = self.var_host_mode.get()
        self.config.set("host_mode", is_host)
        if is_host:
            self.var_server_url.set("http://localhost:8080")
            self.config.set("server_url", "http://localhost:8080")
        self._update_share_banner()
        if self.on_toggle_host_server:
            self.on_toggle_host_server(is_host)
        self._on_join_convoy()

    def _on_use_cloud_server(self):
        """Switch to the hosted (Render) relay server."""
        cloud_url = "https://convoypace-relay-server.onrender.com"
        self.var_server_url.set(cloud_url)
        self.config.set("server_url", cloud_url)
        self.config.set("host_mode", False)
        self.var_host_mode.set(False)
        self._update_share_banner()
        if self.on_join_room:
            self.on_join_room(self.var_room_code.get().strip().upper(), self.var_driver_name.get().strip() or "Driver", cloud_url)

    def _on_create_convoy(self):
        new_code = generate_room_code()
        self.var_room_code.set(new_code)
        if not self.var_host_mode.get():
            self.var_host_mode.set(True)
            self._on_host_mode_toggled()
        else:
            self._update_share_banner()
            self._on_join_convoy()

        lan_ip = get_local_ip()
        share_url = f"http://{lan_ip}:8080/room/{new_code}"
        self.root.clipboard_clear()
        self.root.clipboard_append(share_url)
        messagebox.showinfo("Convoy Created", f"Room Code: {new_code}\nWeb HUD Link: {share_url}\n\nCopied link to clipboard! Share it with your friends.")

    def _on_join_convoy(self):
        code = self.var_room_code.get().strip().upper()
        name = self.var_driver_name.get().strip() or "Driver"
        server_url = self.var_server_url.get().strip() or "http://localhost:8080"
        self.config.set("last_room_code", code, auto_save=False)
        self.config.set("driver_name", name, auto_save=False)
        self.config.set("server_url", server_url, auto_save=True)
        self._update_share_banner()
        if self.on_join_room:
            self.on_join_room(code, name, server_url)

    def _on_open_web_hud(self):
        server_url = self.config.get("server_url", "http://localhost:8080")
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
