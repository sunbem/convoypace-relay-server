# ConvoyPace Render Deployment Checklist

## Prerequisites
- [ ] Render account created at https://render.com
- [ ] Project files accessible (server/ folder with relay_server.py and requirements.txt)

## Option A: Deploy via GitHub (Recommended)

### Step 1: Initialize Git and Push to GitHub
```bash
cd j:/Project/euro-truck-leaderboard
git init
git add .
git commit -m "Initial commit: ConvoyPace relay server"
```

Create a new repository on GitHub (e.g., `convoypace`), then:
```bash
git remote add origin https://github.com/YOUR_USERNAME/convoypace.git
git branch -M main
git push -u origin main
```

### Step 2: Create Web Service on Render
1. Log in to https://render.com
2. Click **New +** → **Web Service**
3. Connect GitHub account and select `convoypace` repository
4. Configure:
   - **Name**: `convoypace-relay-server`
   - **Environment**: `Python`
   - **Region**: Choose closest (Oregon, Ohio, Frankfurt)
   - **Branch**: `main`
   - **Build Command**: `pip install -r server/requirements.txt`
   - **Start Command**: `python server/relay_server.py`
   - **Root Directory**: Leave blank
5. Click **Create Web Service**

### Step 3: Set Environment Variables
In Render dashboard → Environment → Environment Variables:
| Key | Value |
|-----|-------|
| `PORT` | `8080` |
| `PORT_HOST` | `0.0.0.0` |

### Step 4: Wait for Deployment
Render will build and start the server. You'll get a URL like:
```
https://convoypace-relay-server.onrender.com
```

## Option B: Manual Upload (No GitHub)
1. Log in to Render → **New +** → **Web Service**
2. Use upload option or create GitHub repo first
3. Follow Step 2-4 from Option A

## Step 5: Keep Free Tier Warm (UptimeRobot)
Render free tier spins down after ~15 min inactivity.

1. Create free account at https://uptimerobot.com
2. Add monitor:
   - **Type**: HTTP(s)
   - **Name**: ConvoyPace Relay Warm Ping
   - **URL**: `https://convoypace-relay-server.onrender.com/health`
   - **Interval**: 5 minutes
3. Save

> **Note**: Free tier + UptimeRobot = ~5-min max gap on wake. For 24/7 uptime, upgrade to Render Starter (~$7/month).

## Step 6: Update Client to Use Cloud URL

### Method 1: Control Panel (Easiest)
1. Launch `dist/ConvoyPace.exe`
2. Open Control Panel
3. Click **☁️ Use Cloud Server (Render)**
4. Enter: `https://convoypace-relay-server.onrender.com`
5. Click **Join** or **Create Convoy**

### Method 2: Environment Variable
```bash
set CONVOYPACE_SERVER_URL=https://convoypace-relay-server.onrender.com
dist/ConvoyPace.exe
```

### Method 3: config.json
Edit `client/config.json`:
```json
{
  "server_url": "https://convoypace-relay-server.onrender.com",
  "host_mode": false
}
```

## Step 7: Verify Deployment
1. Visit: `https://convoypace-relay-server.onrender.com/health`
   - Expected: `{"status": "ok", "active_rooms": 0, "connected_clients": 0, "version": "1.0.0"}`
2. Launch `dist/ConvoyPace.exe`
3. Set server URL to Render URL
4. Create convoy and join from second client
5. Confirm real-time leaderboard sync works

## Troubleshooting
| Issue | Fix |
|-------|-----|
| Build fails: `ModuleNotFoundError: No module named 'aiohttp'` | Ensure `server/requirements.txt` contains `aiohttp>=3.9.0` |
| Start command fails | Verify `python server/relay_server.py` works locally first |
| WebSocket connections drop | Render free tier spun down; set up UptimeRobot pings |
| Client can't connect | Confirm `CONVOYPACE_SERVER_URL` uses `https://` and no trailing slash |
| Health check returns 404 | The `/health` endpoint exists in `relay_server.py` at line 227 |

## Files Already Prepared
- [`render.yaml`](render.yaml:1) — Render Blueprint (auto-deploy config)
- [`server/requirements.txt`](server/requirements.txt:1) — Python dependencies (`aiohttp`)
- [`server/relay_server.py`](server/relay_server.py:325) — Reads `PORT` and `PORT_HOST` env vars
- [`server/web/index.html`](server/web/index.html:1) — Web HUD served by the server
