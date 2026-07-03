# Architecture — EPT Badminton Auction App

## Overview

A single-process Python/Flask web app designed for **local LAN use**. No database, no authentication framework, no build pipeline. The entire backend is `server.py`; the frontend is plain HTML + CSS + vanilla JavaScript.

---

## Directory Structure

```
auction_app/
├── server.py               # Flask app — all routes, state logic, SSE
├── players.json            # Player pool (edited before auction starts)
├── teams.json              # Team + captain definitions
├── rules.json              # Rules shown in the overlay
├── auction_data.json       # Live auction state (auto-created at runtime)
├── backups/                # Timestamped pre-reset backups (auto-created)
├── static/
│   ├── style.css           # Shared base styles + theme variables + rules overlay
│   ├── console.css         # Console-specific styles
│   ├── console.js          # Console logic (SSE, sale form, undo, export…)
│   ├── viewer.css          # Viewer-specific styles
│   └── viewer.js           # Viewer logic (SSE, render teams + pool)
└── templates/
    ├── console.html        # Auctioneer UI (Jinja2, host-only)
    └── viewer.html         # Read-only live board (Jinja2)
```

---

## Backend — `server.py`

### Key Constants

| Constant | Default | Purpose |
|---|---|---|
| `PURSE` | 20,000 | Starting tokens per team |
| `SLOTS` | 3 | Auction bid slots per team (captain is separate) |
| `DEFAULT_TEAMS_IF_MISSING` | 10 | Fallback team count if `teams.json` is absent |

### State Model

All live state is a single JSON object written to `auction_data.json`:

```jsonc
{
  "config": { "num_teams": 20, "slots": 3, "purse": 20000 },
  "teams": [
    {
      "id": 1,
      "name": "Team 1",
      "captain": "D Viswanath",
      "captain_gender": "M",
      "captain_skill": "Intermediate",
      "players": [
        { "player_id": 5, "name": "…", "base_price": 2000, "skill": "…", "gender": "M", "cost": 3500 }
      ]
    }
  ],
  "players": [
    { "id": 1, "name": "…", "base_price": 2000, "skill": "…", "gender": "M", "sold": false, "team_id": null }
  ],
  "log": [ "…sale log entries…" ],
  "current_bid_player_id": null,
  "theme": "court",
  "show_rules": false
}
```

`state_with_budgets()` computes derived fields (`spent`, `remaining`, `current_bid_player`, `viewer_count`, `lan_ip`) on the fly for API responses without touching the saved file.

### Host vs. Viewer

```
request.remote_addr in ("127.0.0.1", "::1")  →  is_host() = True
```

The `@require_host` decorator returns HTTP 403 to any non-localhost request. Flask serves `console.html` only to local requests; all others get `viewer.html`. No tokens or cookies are involved — access control is purely IP-based.

### Real-time Updates — Server-Sent Events

Two SSE endpoints use in-process `queue.Queue` objects:

| Endpoint | Audience | Counted in `viewer_count`? |
|---|---|---|
| `/api/stream` | Viewer browsers | Yes |
| `/api/console-stream` | Host console | No |

`broadcast_update()` is called after every state-mutating action. It serialises the current state and `put_nowait`s it to every live queue. Dead (full/disconnected) queues are pruned at broadcast time. A 25-second keep-alive comment (`": keep-alive"`) prevents proxies from closing idle connections.

### Thread Safety

A single `threading.RLock` (`_lock`) serialises all reads + writes to `auction_data.json`. A separate `threading.Lock` (`_subscribers_lock`) guards the subscriber lists. Broadcast calls spawned from SSE generators use daemon threads to avoid holding either lock across a slow broadcast.

---

## API Routes

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/` | host | Serve `console.html` |
| GET | `/viewer` | any | Serve `viewer.html` |
| GET | `/api/state` | any | Full state JSON snapshot |
| GET | `/api/stream` | any | SSE stream for viewers |
| GET | `/api/console-stream` | host | SSE stream for console |
| POST | `/api/sale` | host | Record a sale (`team_id`, `player_id`, `cost`) |
| POST | `/api/undo` | host | Revert last sale |
| POST | `/api/set-bid-player` | host | Set current bidding player (`player_id` or `null`) |
| POST | `/api/theme` | host | Change theme (`theme`: court/bosch/stage) |
| POST | `/api/rules` | host | Toggle/set rules overlay (`show`: bool, optional) |
| GET | `/api/export` | host | Download `auction_results.csv` |
| POST | `/api/reset` | host | Backup + wipe state, reload from JSON files |

---

## Frontend

### Console (`console.js`)

- Subscribes to `/api/console-stream` on load.
- On each SSE message: re-renders team cards, summary bar, ticker, player dropdown (filtered to unsold), and team dropdown (filtered to teams with slots remaining).
- Sale form submits `POST /api/sale`; errors shown in `.console-msg`.
- "Now Bidding" header syncs with `state.current_bid_player` — updated automatically when a player is selected in the dropdown.

### Viewer (`viewer.js`)

- Subscribes to `/api/stream` on load.
- Re-renders team grid and player pool sidebar on every SSE message.
- Rules overlay shown/hidden based on `state.show_rules`.

### Themes

CSS custom properties (`--bg`, `--accent`, `--card`, etc.) are declared per theme class (`body.court`, `body.bosch`, `body.stage`) in `style.css`. The active theme class is applied by JavaScript when it receives a state update containing `theme`.

---

## Data Flow Diagram

```
 players.json ──┐
 teams.json  ──┤──► default_state() ──► auction_data.json
 rules.json  ──┘         ▲                    │
                         │                    ▼
                    POST /api/*          load_state()
                   (host only)               │
                         │              state_with_budgets()
                         │                    │
                         └──► broadcast_update()
                                    │
                         ┌──────────┴──────────┐
                         ▼                     ▼
                  /api/console-stream    /api/stream
                   (host console)         (viewers)
```

---

## Persistence & Recovery

- `auction_data.json` is written synchronously (under `_lock`) after every sale, undo, theme change, or reset.
- The app re-reads the file at startup and migrates older saves (missing fields are backfilled).
- `POST /api/reset` copies `auction_data.json` to `backups/auction_data_backup_<timestamp>.json` before wiping.

---

## Deployment Notes

- Designed for **single-event LAN use** — not hardened for public internet exposure.
- Flask's built-in dev server is used (`threaded=True`). Adequate for a room of ~50 viewers over local Wi-Fi.
- To change the port, edit the `app.run(port=…)` call at the bottom of `server.py`.
