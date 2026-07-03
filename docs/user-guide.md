# EPT Badminton League — Auction App User Guide

## Overview

This app runs a **live, interactive player auction** for the EPT Badminton League. The auctioneer operates a private **Console** on their laptop; everyone else in the room watches a **Viewer** board that updates in real time on their own devices — no app install needed, just a browser.

---

## Quick Start

### 1. Install & Run

```bash
pip install flask
python server.py
```

The app opens automatically in your browser at `http://127.0.0.1:8080`.  
A LAN address (e.g. `http://192.168.1.x:8080`) is shown in the top-right corner — share this with viewers.

### 2. Before the Auction

Edit the data files while the server is **stopped**:

| File | What to edit |
|---|---|
| `players.json` | Add/remove players; set `name`, `base_price`, `skill`, `gender` |
| `teams.json` | Add/remove teams; set `name`, `captain`, `skill`, `gender` |
| `rules.json` | Edit the rules shown in the overlay |

After editing, restart the server and hit **Reset** to apply changes (existing data is backed up automatically).

---

## The Console (Auctioneer View)

Accessible only on the machine running the server — `http://127.0.0.1:8080`.

### Header Bar

| Element | Description |
|---|---|
| **Now Bidding** | Displays the player currently on the table (name, skill, base price) |
| **LAN IP** | The address viewers should open on their devices |
| **Viewer count** | Live count of connected viewer browsers |
| **Show Rules** | Toggles the rules overlay on all screens simultaneously |
| **Theme** | Switch between Court / Bosch / Stage colour themes |

### Making a Sale

1. Pick a **Team** from the dropdown.
2. Pick a **Player** from the player dropdown (unsold players only).
3. Enter the winning bid amount in **Tokens**.
4. Click **Confirm Sale**.

The app validates every sale and shows an error in red if something is wrong (over budget, wrong gender rule, player already sold, etc.).

### Other Console Actions

| Button | Effect |
|---|---|
| **Undo** | Reverts the most recent sale |
| **Export** | Downloads `auction_results.csv` with all sales |
| **Reset** | Clears all sales and restores the full player pool (backs up current data first) |

### Summary Bar

Below the console row, a live summary shows:
- Teams filled / total teams
- Players sold / total players
- Total tokens spent across all teams
- Total tokens unspent

### Team Cards

Each team card shows:
- Captain name, skill level, and gender badge
- Each bought player with their cost and skill badge
- Budget bar (tokens spent vs. remaining)
- A ♀ badge if the team has met the gender requirement

---

## The Viewer Board

Open `http://<LAN-IP>:8080` on any browser on the same Wi-Fi.

The viewer board is **read-only** — it shows:
- **Now Bidding** — the current player on the table (updates instantly)
- **Sale ticker** — scrolling log of the most recent sales
- **Team grid** — all teams with their rosters and budgets
- **All Players sidebar** — full player pool; sold players are crossed out
- **Rules overlay** — appears when the auctioneer activates it

---

## Auction Rules Summary

| Rule | Detail |
|---|---|
| **Team size** | 1 captain (pre-assigned) + 3 players via auction = 4 total |
| **Purse** | 20,000 tokens per team |
| **Base prices** | Beginner: 2,000 tokens · Intermediate: 5,000 tokens |
| **Gender quota** | Minimum 1 female, maximum 2 females per team (captain counts) |
| **Last-slot rule** | If a team has no female yet (and no female captain), their last slot must go to a female player |

---

## Data & Persistence

- All auction progress is saved automatically to `auction_data.json` after every sale.
- Closing the browser or stopping the server is safe — reopen and everything is restored.
- Every **Reset** creates a timestamped backup in the `backups/` folder.

---

## Themes

Three visual themes are available from the console:

| Theme | Style |
|---|---|
| **Court** | Badminton court green/teal |
| **Bosch** | Corporate blue, Bosch branding colours |
| **Stage** | Dark/dramatic stage lighting look |

Theme changes apply to all connected viewers instantly.
