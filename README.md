# ConvoyPace 🚚
> **Ultra-Lightweight ETS2 Convoy Live Distance Overlay & Real-Time Leaderboard**

ConvoyPace is a portable companion app and real-time relay system designed for Euro Truck Simulator 2 (ETS2) online convoy players. When hauling identical freight jobs with friends, ConvoyPace reads live remaining route distances directly from ETS2's telemetry memory (`Local\SCSTelemetry`), synchronizes drivers over a shared room code, and renders a sleek, transparent, always-on-top HUD overlay right on top of the game screen—complete with an optional secondary monitor / smartphone web view.

---

## ✨ Features

- **🎮 Seamless In-Game HUD Overlay:**
  - **Frameless & Transparent:** Crisp dark-mode HUD (`rgba(15, 17, 23, 0.85)`) placed directly in-game.
  - **Click-Through (`WS_EX_TRANSPARENT`):** When locked, clicks pass directly into the game—zero accidental focus loss.
  - **Draggable When Unlocked:** Reposition anywhere on screen; window coordinates auto-save.
  - **Global Hotkeys:**
    - `F9`: Toggle Overlay Visibility (Hide / Show)
    - `F10`: Toggle Lock / Drag Mode
- **⚡ Zero-Config Friend Experience:**
  - Standalone portable `.exe` (friends need **no** Python, Node.js, or external runtimes).
  - **1-Click Plugin Setup:** Automatically locates Steam ETS2 installations across all drives (`libraryfolders.vdf`, registry) and installs the required 64-bit `scs-telemetry.dll` into `bin\win_x64\plugins\` with a single button.
- **🏁 Real-Time Leaderboard & Distance Deltas:**
  - Dynamic sort by remaining distance ascending (lowest remaining distance = `#1 Leader`).
  - Real-time gap calculation (`+4 km`, `+17 km`) relative to the leader.
  - Finish state detection: when reaching destination, marks player as `🏁 FINISHED (#1, #2...)`.
  - Metric (km & km/h) and Imperial (mi & mph) toggles.
- **📱 Secondary Monitor & Smartphone Web HUD:**
  - Responsive web dashboard served at `http://<server-ip>:8080/room/<room_code>`.
  - Keep the leaderboard on a second monitor, phone, or tablet without obscuring your windshield.
- **🚗 Built-in Simulation / Demo Mode:**
  - Test driving, speed variations, and finish ranking immediately without launching ETS2.
- **🪶 Ultra-Low Resource Usage:**
  - Memory footprint: `< 40MB RAM`.
  - CPU usage: `< 0.2%`.

---

## 📸 In-Game HUD Layout

```text
🚚 CONVOY: TRUCK-42  [Berlin -> Paris]
-------------------------------------------
#1  Alex        142 km   (1h 48m)   85 km/h
#2  You (Sam)   146 km   (+4 km)    82 km/h
#3  Mike        159 km   (+17 km)   79 km/h
#4  Leo         🏁 FINISHED (#1)
-------------------------------------------
[Ctrl+F9: Hide] [Ctrl+F10: Unlock]
```

---

## 🚀 Quickstart Guide

### 1. Host Creates a Convoy
1. Launch `ConvoyPace.exe` (or `python client/main.py`).
2. If this is your first time, click **⚡ 1-Click Install Plugin** to ensure `scs-telemetry.dll` is in your ETS2 directory.
3. Click **✨ Create Convoy** — a room code (e.g., `TRUCK-42`) is generated and copied to your clipboard.
4. Share the Room Code with your friends via Discord / Steam chat.

### 2. Friends Join the Convoy
1. Friends open `ConvoyPace.exe`.
2. Enter their **Driver Name**, paste the **Room Code**, and click **🚀 Join**.
3. Launch Euro Truck Simulator 2 and accept your freight job!
4. The HUD overlay will automatically populate with live distance, speed, and ranking.

### 3. Secondary Monitor / Smartphone Web View
- Open your browser or phone to `http://<server-ip>:8080/room/<ROOM_CODE>`.
- The web page syncs over WebSockets in real time.

---

## ⌨️ Hotkey Reference (Safe Convoy Bindings)

> **Important ETS2 Note:** Bare `F9` (opens in-game chat) and bare `F10` (writes uncompressed screenshot dumps) are intentionally avoided so ConvoyPace never interferes with your driving or multiplayer chat.

| Primary Hotkey | Utility / Single-Key Alternative | Action | Behavior |
| :---: | :---: | :--- | :--- |
| **`Ctrl + F9`** | **`Insert`** or **`F11`** | **Toggle Visibility** | Instantly hides or shows the overlay HUD. |
| **`Ctrl + F10`** | **`Home`** | **Toggle Lock / Drag** | Switches between **🔒 Locked** (click-through into game) and **🔓 Drag Mode** (click and drag to move). |

---

## 🏗️ Architecture & Project Structure

```text
euro-truck-leaderboard/
├── bin/
│   └── scs-telemetry.dll          # Bundled 64-bit SCS Telemetry SDK DLL (v1.12.1)
├── client/
│   ├── main.py                    # Application coordinator & entry point
│   ├── overlay_window.py          # Frameless, transparent Win32 HUD window
│   ├── control_panel.py           # Settings, room manager & 1-click plugin GUI
│   ├── steam_detector.py          # Steam registry & multi-drive ETS2 detector
│   ├── plugin_installer.py        # 1-Click installer with checksum verification
│   ├── telemetry_reader.py        # Windows mmap reader for Local\SCSTelemetry
│   ├── telemetry_simulator.py     # Realistic mock telemetry generator
│   ├── network_client.py          # Threaded WebSocket client with auto-reconnect
│   ├── config_manager.py          # Persistent JSON settings manager
│   └── win32_utils.py             # Win32 click-through & global hotkey hooks
├── server/
│   ├── relay_server.py            # High-performance Python aiohttp WebSocket server
│   ├── server.js                  # Standalone Node.js relay server alternative
│   ├── package.json               # Node.js dependencies
│   └── web/
│       └── index.html             # Responsive mobile & secondary monitor Web HUD
├── shared/
│   ├── telemetry_model.py         # Binary layout & dataclasses for Local\SCSTelemetry
│   └── scs-telemetry-common.hpp   # Official SCS SDK telemetry struct reference
├── tests/
│   ├── test_telemetry.py          # Binary packing/unpacking & simulator unit tests
│   ├── test_server.py             # Room lifecycle & leaderboard WebSocket tests
│   ├── test_client_core.py        # Steam detection & plugin installer tests
│   ├── test_app_lifecycle.py      # GUI initialization & tick tests
│   └── test_multi_client_convoy.py# 4-driver race simulation & RAM benchmark
├── ConvoyPace.spec                # PyInstaller packaging configuration
└── progress.md                    # Development milestones & progress tracker
```

---

## 🌐 Relay Server Hosting

The relay server is completely stateless and in-memory; rooms auto-expire after 2 hours of inactivity.

### Option A: Run Locally (Host Machine)
```bash
python server/relay_server.py --port 8080
# OR with Node.js
node server/server.js
```

### Option B: Deploy to Cloud (Render)
Deploy `server/` to Render's free tier. The server is a standard Python aiohttp web service.

1. **Create a Render account** at <https://render.com> and create a new Web Service.
2. Connect your repository (or upload the `server/` folder) and set the following:
   - **Build Command**: `pip install -r server/requirements.txt`
   - **Start Command**: `python server/relay_server.py`
   - **Environment Variable**: `PORT=8080` (Render injects this automatically)
3. Once deployed, Render will give you a public URL like `https://convoypace-relay-server.onrender.com`.
4. **Important — Free-tier sleep**: Render free tier spins down after ~15 min of inactivity, which drops live WebSocket connections. To keep the server warm:
   - **Option 1 (recommended)**: Upgrade to Render Starter tier (~$7/mo) — the server stays up 24/7.
   - **Option 2 (free)**: Set up UptimeRobot (free tier) to ping `https://<your-service>.onrender.com/health` every 5 minutes. This keeps the service warm but adds a ~5-min max gap on wake.
5. After deploying, update the client's server URL:
   - **Via config.json**: Edit `client/config.json` and set `"server_url": "https://<your-render-url>.onrender.com"`.
   - **Via environment variable**: Set `CONVOYPACE_SERVER_URL=https://<your-render-url>.onrender.com` when launching the client.
   - **Via Control Panel**: Click **☁️ Use Cloud Server (Render)** in the ConvoyPace GUI and enter your URL.

### Option C: Keep Local Embedded Server as Fallback
If the cloud URL becomes unreachable, the host can toggle "Host Convoy on this PC" to run the relay locally (already supported). This gives you the best of both worlds: cloud for cross-network friends, local for LAN.

---

## 🧪 Automated Test Suite

Run the full automated test suite covering all modules:

```bash
python -m unittest discover tests
```

Tests include:
- `test_telemetry`: Byte-level binary compatibility with SCS SDK memory map.
- `test_server`: Multi-client room join, real-time sorting, and finish rankings.
- `test_client_core`: Steam registry discovery, `libraryfolders.vdf` parsing, and DLL deployment.
- `test_app_lifecycle`: GUI state transitions, hotkey events, and headless cleanup.
- `test_multi_client_convoy`: 4-driver full convoy race with overtakes and memory verification.

---

## 📄 License
MIT License. Euro Truck Simulator 2 is a registered trademark of SCS Software. ConvoyPace is an independent open-source tool.

