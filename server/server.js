/**
 * server/server.js - Ultra-lightweight Node.js real-time relay server for ConvoyPace.
 * Zero heavy dependencies (only ws, or standard http).
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const { WebSocketServer, WebSocket } = require('ws');

const PORT = process.env.PORT || 8080;
const WEB_DIR = path.join(__dirname, 'web');

// In-memory room store
const rooms = new Map();

function generateRoomCode() {
    const prefixes = ['TRUCK', 'CONVOY', 'HAUL', 'PACE', 'ROUTE'];
    const p = prefixes[Math.floor(Math.random() * prefixes.length)];
    const n = Math.floor(10 + Math.random() * 90);
    return `${p}-${n}`;
}

class ConvoyRoom {
    constructor(code) {
        this.code = code;
        this.createdAt = Date.now();
        this.lastActivity = Date.now();
        this.sessions = new Map();
        this.finishCounter = 0;
    }

    addSession(session) {
        this.sessions.set(session.id, session);
        this.lastActivity = Date.now();
    }

    removeSession(id) {
        this.sessions.delete(id);
        this.lastActivity = Date.now();
    }

    computeLeaderboard() {
        const drivers = Array.from(this.sessions.values()).filter(s => !s.isViewer);
        let destinationCity = '';
        let sourceCity = '';
        let cargoName = '';

        for (const s of drivers) {
            if (s.telemetry && s.telemetry.destination_city) {
                destinationCity = s.telemetry.destination_city;
                sourceCity = s.telemetry.source_city || '';
                cargoName = s.telemetry.cargo_name || '';
                break;
            }
        }

        const finished = [];
        const active = [];

        for (const s of drivers) {
            const isFinished = s.finishTime !== null || (s.telemetry && s.telemetry.is_finished);
            if (isFinished) {
                if (!s.finishRank) {
                    this.finishCounter++;
                    s.finishRank = this.finishCounter;
                }
                finished.push(s);
            } else {
                active.push(s);
            }
        }

        finished.sort((a, b) => (a.finishRank || 999) - (b.finishRank || 999));
        active.sort((a, b) => {
            const da = (a.telemetry && a.telemetry.route_distance_m) || 99999999;
            const db = (b.telemetry && b.telemetry.route_distance_m) || 99999999;
            return da - db;
        });

        const all = [...finished, ...active];
        const leaderDistM = active.length > 0 ? (active[0].telemetry?.route_distance_m || 0) : null;

        const results = all.map((s, idx) => {
            const t = s.telemetry || {};
            const distM = t.route_distance_m || 0;
            const distKm = t.distance_km || (distM / 1000);
            const distMi = t.distance_mi || (distKm * 0.621371);
            let deltaKm = 0;
            let deltaMi = 0;

            if (leaderDistM !== null && !finished.includes(s)) {
                const deltaM = Math.max(0, distM - leaderDistM);
                deltaKm = deltaM / 1000;
                deltaMi = deltaKm * 0.621371;
            }

            let status = 'DRIVING';
            if (finished.includes(s)) {
                status = 'FINISHED';
            } else if (t.paused) {
                status = 'PAUSED';
            } else if (!t.on_job) {
                status = 'FREE_ROAM';
            }

            return {
                session_id: s.id,
                rank: idx + 1,
                driver_name: s.driverName,
                distance_km: Math.round(distKm * 10) / 10,
                distance_mi: Math.round(distMi * 10) / 10,
                delta_km: Math.round(deltaKm * 10) / 10,
                delta_mi: Math.round(deltaMi * 10) / 10,
                speed_kmh: Math.round((t.speed_kmh || 0) * 10) / 10,
                speed_mph: Math.round((t.speed_mph || 0) * 10) / 10,
                time_formatted: t.time_formatted || '--:--',
                cargo_damage: Math.round((t.cargo_damage || 0) * 1000) / 10,
                status,
                finished_rank: s.finishRank || null,
                destination_city: t.destination_city || destinationCity,
                last_seen: Math.round(s.lastSeen / 1000)
            };
        });

        return {
            type: 'leaderboard_update',
            room_code: this.code,
            route: { source: sourceCity, destination: destinationCity, cargo: cargoName },
            drivers: results,
            timestamp: Date.now() / 1000
        };
    }

    broadcast() {
        const payload = JSON.stringify(this.computeLeaderboard());
        for (const [id, s] of this.sessions.entries()) {
            if (s.ws.readyState === WebSocket.OPEN) {
                try {
                    s.ws.send(payload);
                } catch (e) {
                    this.removeSession(id);
                }
            } else {
                this.removeSession(id);
            }
        }
    }
}

// HTTP Server
const server = http.createServer((req, res) => {
    const url = new URL(req.url, `http://${req.headers.host}`);

    if (url.pathname === '/health' || url.pathname === '/api/health') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        let clients = 0;
        for (const r of rooms.values()) clients += r.sessions.size;
        return res.end(JSON.stringify({ status: 'ok', active_rooms: rooms.size, connected_clients: clients }));
    }

    if (url.pathname === '/api/rooms' && req.method === 'POST') {
        const code = generateRoomCode();
        rooms.set(code, new ConvoyRoom(code));
        res.writeHead(200, { 'Content-Type': 'application/json' });
        return res.end(JSON.stringify({ room_code: code, url: `/room/${code}` }));
    }

    if (url.pathname.startsWith('/room/')) {
        const indexPath = path.join(WEB_DIR, 'index.html');
        if (fs.existsSync(indexPath)) {
            res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
            return fs.createReadStream(indexPath).pipe(res);
        }
    }

    if (url.pathname === '/') {
        res.writeHead(302, { Location: `/room/${generateRoomCode()}` });
        return res.end();
    }

    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('Not Found');
});

// WebSocket Server
const wss = new WebSocketServer({ server, path: '/ws' });

wss.on('connection', (ws) => {
    let currentRoom = null;
    let currentSession = null;

    ws.on('message', (raw) => {
        try {
            const msg = JSON.parse(raw);
            if (msg.type === 'join') {
                const code = (msg.room_code || 'DEFAULT').toUpperCase().trim();
                if (!rooms.has(code)) {
                    rooms.set(code, new ConvoyRoom(code));
                }
                currentRoom = rooms.get(code);
                currentSession = {
                    id: Math.random().toString(36).substring(2, 10),
                    ws,
                    driverName: msg.driver_name || 'Driver',
                    isViewer: Boolean(msg.is_viewer),
                    lastSeen: Date.now(),
                    telemetry: {},
                    finishTime: null,
                    finishRank: null
                };
                currentRoom.addSession(currentSession);
                ws.send(JSON.stringify({ type: 'joined', room_code: code, session_id: currentSession.id }));
                currentRoom.broadcast();
            } else if (msg.type === 'telemetry') {
                if (currentRoom && currentSession) {
                    currentSession.lastSeen = Date.now();
                    currentSession.telemetry = msg.data || {};
                    const isFin = currentSession.telemetry.is_finished || 
                                 (currentSession.telemetry.on_job && (currentSession.telemetry.route_distance_m || 100) <= 0);
                    if (isFin && currentSession.finishTime === null) {
                        currentSession.finishTime = Date.now();
                    }
                    currentRoom.broadcast();
                }
            } else if (msg.type === 'ping') {
                ws.send(JSON.stringify({ type: 'pong' }));
            }
        } catch (e) {
            console.error('Error handling message:', e);
        }
    });

    ws.on('close', () => {
        if (currentRoom && currentSession) {
            currentRoom.removeSession(currentSession.id);
            currentRoom.broadcast();
        }
    });
});

server.listen(PORT, () => {
    console.log(`🚀 ConvoyPace Node Relay Server listening on http://localhost:${PORT}`);
});

