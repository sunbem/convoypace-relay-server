# ConvoyPace Development Progress Tracker

> **Project:** ConvoyPace - ETS2 Convoy Live Distance Overlay & Leaderboard  
> **PRD Source:** [euro-truck-tracker.md](file:///J:/Project/euro-truck-leaderboard/euro-truck-tracker.md)  
> **Last Updated:** 2026-11-14

---

## 📊 Milestone Summary Table

| Milestone | Description | Status | Completion |
| :--- | :--- | :---: | :---: |
| **M1: Architecture & Foundation** | Directory setup, progress tracking, telemetry DLL bundling | ✅ Achieved | 100% |
| **M2: SCS Telemetry Engine** | Windows MMF `Local\SCSTelemetry` parser & realistic simulator | ✅ Achieved | 100% |
| **M3: Real-Time Relay Server & Web View** | WebSocket room server, leaderboard sorting, web HUD `/room/:code` | ✅ Achieved | 100% |
| **M4: Steam Auto-Detection & Plugin Installer** | Registry/Steam library scan & 1-click `scs-telemetry.dll` installer | ✅ Achieved | 100% |
| **M5: In-Game HUD Overlay (GUI)** | Frameless, click-through, hotkey-controlled topmost overlay HUD | ✅ Achieved | 100% |
| **M6: Packaging & End-to-End Verification** | Portable single `.exe` build, multi-client verification, docs | ✅ Achieved | 100% |
| **M7: Cloud Hosting & Overlay Fix** | Overlay black-window/click-through fix + Render deployment guide + UptimeRobot warm-ping strategy | ✅ Achieved | 100% |
| **M8: Client Cloud Preset** | Add Cloud Server preset button in Control Panel + CONVOYPACE_SERVER_URL env override | ✅ Achieved | 100% |
| **M9: Documentation & Verification** | Updated README.md with Render deploy guide, overlay troubleshooting, and progress tracking | ✅ Achieved | 100% |
| **M10: Profile Deduplication & Instant Sync** | Enforce 1 driver profile per user (case-insensitive deduplication), instant JOINED driver broadcast to web HUD & overlay | ✅ Achieved | 100% |

**Total Overall Progress:** `100%`

---

## 🛠 Detailed Action Plan & Step Checklist

### Milestone 1: Project Architecture & Foundation
- [x] Analyze PRD requirements (`euro-truck-tracker.md`)
- [x] Create `progress.md` with milestone summary and granular tasks
- [x] Set up clean directory structure (`client/`, `server/`, `shared/`, `assets/`, `bin/`)
- [x] Download and verify official 64-bit `scs-telemetry.dll` (v1.12.1) into `bin/`
- [x] Configure development dependencies and environment (`aiohttp`, `websockets`, `pyinstaller`)

### Milestone 2: SCS Telemetry Engine & Memory-Mapped Reader
- [x] Implement `shared/telemetry_model.py` with binary offsets matching `scs-telemetry-common.hpp`
- [x] Implement `client/telemetry_reader.py` (Windows `mmap` reader for `Local\SCSTelemetry`)
- [x] Implement `client/telemetry_simulator.py` (mock driving generator with realistic speed, distance countdown, route metadata)
- [x] Write unit tests for telemetry parser & simulator (`tests/test_telemetry.py`)
- [x] Verify handling of paused state, route completion, and disconnected state

### Milestone 3: Real-Time Relay Server & Multi-Display Web View
- [x] Implement lightweight WebSocket relay server (`server/relay_server.py` and optional `server/server.js`)
- [x] Implement in-memory room management (Create 4-6 char code, Join, Leave, 2-hour inactivity cleanup)
- [x] Implement real-time leaderboard sorting algorithm (rank by remaining distance ascending, delta to leader/you)
- [x] Implement finish state detection (`remaining_distance <= 0` -> rank `#1`, `#2`, etc.)
- [x] Implement mobile-friendly secondary monitor Web View served at `/room/:room_code`
- [x] Write automated server integration tests (`tests/test_server.py`)

### Milestone 4: Windows Client Core & Steam 1-Click Plugin Installer
- [x] Implement `client/steam_detector.py` (Steam registry detection, `libraryfolders.vdf` parser, ETS2 path finder)
- [x] Implement 1-click plugin installer logic (copy `scs-telemetry.dll` to `bin/win_x64/plugins/`)
- [x] Implement persistent configuration management `config.json` (Driver Name, Server URL, Units KM/MI, window position)
- [x] Implement WebSocket client connection worker (`client/network_client.py`) with auto-reconnect

### Milestone 5: In-Game HUD Overlay & Native GUI
- [x] Implement frameless, transparent, always-on-top overlay window using `tkinter` + Win32 API (`ctypes`)
- [x] Implement Win32 click-through toggle (`WS_EX_TRANSPARENT`) when locked
- [x] Implement Windows global hotkey hooks (Safe: Ctrl+F9/Ins toggle visibility, Ctrl+F10/Home toggle lock/drag)
- [x] Design compact, sleek HUD layout (Convoy Room Code, Route banner, Driver ranks, Distance, Delta, Speed, Status)
- [x] Implement Settings / Connection Manager window (Create/Join room, Unit toggle KM/MI, 1-Click Plugin install, Demo mode)
- [x] Implement driver status highlights (You / Leader / Finished / Paused)

### Milestone 6: Packaging, Multi-Client Verification & Documentation
- [x] Build PyInstaller standalone single-file `.exe` spec with bundled assets & DLL (`dist/ConvoyPace.exe`)
- [x] Perform multi-client simulation test (host + 3 simulated friends in room, overtakes, finish state)
- [x] Validate memory footprint (< 40MB RAM) and CPU overhead (< 0.2%)
- [x] Write comprehensive `README.md` with quickstart guide, hotkey references, and troubleshooting instructions
- [x] Final project review and delivery

### Milestone 10: Profile Deduplication & Instant Joined Broadcast
- [x] Enforce one driver profile per user on relay servers (`server/relay_server.py` and `server/server.js`) via case-insensitive deduplication by driver name on join.
- [x] Introduce `JOINED` driver status on the relay server so drivers appear in the room immediately upon clicking Join, prior to receiving their first ETS2 telemetry packet.
- [x] Update web HUD (`server/web/index.html`) to display joined drivers immediately with "Ready / Syncing..." state instead of leaving the board empty.
- [x] Update in-game overlay (`client/overlay_window.py`) to render joined drivers immediately with "Syncing..." distance placeholder.
- [x] Trigger an immediate telemetry tick upon room join in `client/main.py` for sub-100ms first telemetry push.
- [x] Add automated unit test in `tests/test_server.py` verifying case-insensitive deduplication and instant `JOINED` status broadcast.
