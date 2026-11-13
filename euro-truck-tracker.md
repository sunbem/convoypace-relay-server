# Product Requirements Document (PRD): ETS2 Convoy Live Distance Leaderboard

## 1. Agent Execution & Project Management Instructions
**CRITICAL INSTRUCTIONS FOR THE AI CODING AGENT:**
1. **Task Tracking (`progress.md`):** Before writing any application code, you MUST create a file named `progress.md` in the root directory.
2. **Milestone & Step Structure:** `progress.md` must break the entire development lifecycle into clear Phases/Milestones and granular, actionable steps.
3. **Status Indicators:** Use explicit visual indicators in `progress.md` so the developer can immediately see what is completed, in progress, or pending:
   - `[x]` or `✅` = Completed
   - `[~]` or `🔄` = In Progress
   - `[ ]` or `⬜` = Pending / Not Started
   - Include a top-level **Milestone Summary Table** in `progress.md` showing Milestone Name, Status (`✅ Achieved` / `🔄 In Progress` / `⬜ Pending`), and Completion Percentage.
4. **Continuous Updates:** You MUST update `progress.md` immediately after completing each step or milestone before moving to the next task.
5. **Simplicity & Portability:** Prioritize minimal dependencies, low CPU/RAM overhead (< 40MB RAM), and a single-file portable executable build for end-users.

---

## 2. Project Overview
* **Product Name:** ConvoyPace (ETS2 Convoy Live Distance Overlay & Tracker)
* **Problem Statement:** When playing Euro Truck Simulator 2 (ETS2) in online Convoy mode on identical freight jobs, players have no shared leaderboard displaying each driver's remaining distance to the destination. Players must constantly interrupt driving to ask each other for distance updates via voice/text chat.
* **Solution:** A ultra-lightweight, portable Windows companion app paired with a minimal real-time relay server. The client reads live remaining navigation distance directly from ETS2's telemetry memory, syncs it with convoy friends via a shared Room Code, and displays a sleek, transparent, always-on-top in-game HUD overlay (plus an optional browser view for second monitors/phones).

---

## 3. Target Users & Distribution Requirements
* **Users:** A small group of friends (2–8 players per convoy) playing ETS2 on Windows (Steam).
* **Zero-Config Friend Experience:**
  * Friends must NOT be required to install Python, Node.js, or external runtimes.
  * Distribute as a standalone portable `.exe` (e.g., built via PyInstaller/Nuitka or Go/C#).
  * **One-Click Plugin Setup:** The app must automatically detect the Steam ETS2 installation path (via Windows Registry / standard Steam library folders) and offer a 1-click button to install the required `scs-telemetry.dll` into `Euro Truck Simulator 2\bin\win_x64\plugins\`.

---

## 4. Recommended Tech Stack
* **Client Application (Windows):** Python 3.11+ (packaged to single `.exe` via PyInstaller) OR Go / C# (.NET 8 single-file trimmed `.exe`).
  * *If Python:* `truck_telemetry` / `pyets2` (or direct `mmap` reader for `Local\SCSTelemetry`), `websockets` / `python-socketio`, and `tkinter` or `PyQt6` (frameless, transparent, click-through overlay window).
* **Relay Server (Lightweight):** Node.js (`ws` or `Socket.IO`) or Python (`FastAPI` + WebSockets) or Go (`gorilla/websocket`).
  * Stateless in-memory room management (no heavy database required; rooms auto-expire after 2 hours of inactivity).
  * Deployable to free-tier cloud hosts (Render, Railway, Fly.io) OR runnable locally by the host.
* **Web View (Bonus/Secondary Display):** Simple static HTML/JS served directly by the relay server at `/room/<room_code>` so friends on a second monitor or phone can also view the live leaderboard.

---

## 5. Core Functional Requirements

### 5.1 Telemetry Data Extraction (ETS2 Shared Memory)
The client must read the following fields from the SCS Telemetry SDK memory-mapped file (`Local\SCSTelemetry`) every **1000ms (1 second)**:
* `navigation.distance` (Remaining route distance in meters -> convert to `km` and `mi` based on user toggle).
* `navigation.time` (Estimated remaining time in seconds -> format as `HH:MM`).
* `speed` (Current truck speed in `km/h` or `mph`).
* `job.destinationCity` & `job.destinationCompany` (To verify everyone is heading to the same destination).
* `job.cargo` & `job.cargoDamage` (Optional indicator for cargo status).
* `game.paused` / `sdk.active` (Detect if the player is in the menu, disconnected, or actively driving).

### 5.2 Room & Convoy Sync
* **Create / Join Room:**
  * Host clicks **"Create Convoy"** -> generates a short 4-to-6 character Room Code (e.g., `TRUCK-42`) and copies it to clipboard.
  * Friends enter their **Driver Name**, paste the **Room Code**, and click **"Join"**.
  * Save Driver Name and last Server URL in a local `config.json` next to the `.exe`.
* **Real-Time Broadcast:**
  * Client sends telemetry payload via WebSocket every **1–2 seconds**.
  * Server sorts all active players in the room by `remaining_distance` ascending (lowest remaining distance = `#1 Leader`).
  * **Delivered State:** When `remaining_distance <= 0` (or job completed event triggers), mark player status as `🏁 FINISHED` with their finish timestamp/order (`#1`, `#2`, etc.).

### 5.3 In-Game HUD Overlay
* **Window Behavior:**
  * Frameless, borderless, always-on-top (`WS_EX_TOPMOST`).
  * Semi-transparent dark background (`rgba(15, 17, 23, 0.75)`) with crisp, high-contrast typography.
  * **Draggable** when unlocked; **Click-Through** (`WS_EX_TRANSPARENT`) when locked so mouse clicks in-game never accidentally focus the overlay.
  * Global hotkey (e.g., `F9`) to toggle overlay visibility and (`F10`) to toggle lock/drag mode.
* **Overlay UI Layout (Compact Leaderboard):**
  ```text
  🚚 CONVOY: TRUCK-42  [Berlin -> Paris]
  -------------------------------------------
  #1  Alex        142 km   (1h 48m)   85 km/h
  #2  You (Sam)   146 km   (+4 km)    82 km/h
  #3  Mike        159 km   (+17 km)   79 km/h
  #4  Leo         🏁 FINISHED (#1)
  -------------------------------------------
  [F9: Hide] [F10: Unlock]