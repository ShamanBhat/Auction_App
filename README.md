# Office Badminton Auction Tracker

A small local web app for running a live player auction — one auctioneer
console that records sales, and a read-only scoreboard that anyone on the
WiFi can watch update in real time.

Built for: 10 teams, 4 players each (1 captain + 3 bid on), 25,000-token
purse per team — but every number here is editable, see **Customization**
below.

---

## What's in this folder

```
auction_app/
├── server.py              ← run this
├── players.json            ← edit with your real player list
├── teams.json               ← edit with your real teams/captains
├── auction_data.json        ← created automatically once the auction starts
├── templates/
│   ├── console.html         ← the auctioneer's page (markup only)
│   └── viewer.html          ← the read-only scoreboard (markup only)
└── static/
    ├── style.css             ← shared look (theme colors, team cards, layout)
    ├── console.css            ← console-only styling (the bid form, toggle, etc.)
    ├── viewer.css              ← viewer-only styling
    ├── console.js              ← console's logic (talks to the API, renders the page)
    └── viewer.js                ← viewer's logic (listens for live updates)
```

Everything is split by concern on purpose: `server.py` is pure backend
(routes and state), the `templates/` files are just HTML structure, and
`static/` holds the styling and the browser-side JavaScript — so if you
want to tweak a color, you're in `static/*.css`, not hunting through
Python. Nothing here needs editing to run the app as-is.

| File                | What it is                                                              |
|---------------------|--------------------------------------------------------------------------|
| `server.py`          | The app itself. Run this.                                               |
| `players.json`       | The pool of players up for auction — **edit this with your real list.** |
| `teams.json`         | Team names and captains — **edit this with your real teams.**           |
| `auction_data.json`  | Created automatically once the auction starts. This is the live save file — don't edit by hand while the app is running. |

---

## 1. Set up your players and teams

Open **`players.json`** and replace the example entries with your real
player list. Each player needs:

```json
{ "name": "Arjun Rao", "base_price": 1000, "skill": "A" }
```

- `base_price` — the minimum bid the auctioneer can enter for that player.
- `skill` — any short label you want (`A`/`B`/`C`, "Pro", whatever). Shown
  next to the player's name everywhere.

You can list any number of players — it doesn't need to match
`teams × 3` exactly. Extra players just stay unsold in the pool.

Open **`teams.json`** and fill in real team names and captains:

```json
{ "name": "Smashers", "captain": "Vikram Shetty" }
```

The number of teams is simply how many entries are in this file — add or
remove rows to change the team count. Captains show up pre-filled on the
team cards the moment the app starts (still editable from the console if
something changes on the day).

If you skip this step entirely, the app auto-generates placeholder
versions of both files on first run so it never crashes — but you'll want
to replace those before the real auction.

---

## 2. Install and run

You need Python 3 and Flask:

```bash
pip install flask
python server.py
```

You'll see something like:

```
Starting auction board...
  On this laptop      : http://127.0.0.1:8080
  From other devices  : http://192.168.1.42:8080  (same WiFi only)
Press Ctrl+C to stop.
```

A browser tab opens automatically on the laptop running the script — that's
your **auctioneer console**.

Press `Ctrl+C` in the terminal whenever you're done. Nothing is lost when
you stop it — see the section on saved data below.

---

## 3. Two views: console vs. scoreboard

This app treats the **laptop it's running on** as the auctioneer, and
**every other device** as a read-only viewer. This is based on which
machine the request is coming from, not a password — anyone with another
browser tab open on the same laptop also counts as the auctioneer.

**On the host laptop** (`http://127.0.0.1:8080`), you get the full console:

- A form to record a sale: pick the **team**, pick the **player** from a
  dropdown (only unsold players are listed, each showing its base price
  and skill), enter the **cost**, and confirm. The cost field auto-fills
  with the base price and the server rejects anything below it.
- The moment you select a player in the dropdown (even before confirming
  the sale), it's broadcast as **"Now bidding"** to everyone watching —
  so the room sees who's up before the price is locked in.
- A live sidebar listing **every player** in the pool with their status
  (Available, or which team bought them and for how much).
- **Undo last sale**, **remove** any individual player from a team's
  roster (✕ next to their name — both put the player back in the pool),
  **export** the full results as a `.json` file, and **reset** the whole
  auction back to a blank state (re-reading `players.json`/`teams.json`,
  so this is also how you pick up edits you made to those files mid-event).
- A **theme toggle** (top right) — switch between the default "Court"
  look and a black/red "Bosch" theme. This applies to every connected
  viewer immediately, not just your own screen.
- Team names and captains are editable inline on each team card.

**On every other device** (`http://<lan-ip>:8080`, e.g. `http://192.168.1.42:8080`
from the printed address), you get a read-only scoreboard: the "Now
bidding" banner, the full player pool with status, and every team's
remaining budget and roster — updating live, with no buttons to press.
Any attempt to submit a sale, undo, edit, or reset from a non-host device
is rejected by the server itself, regardless of what URL is typed.

Updates reach viewers instantly (a live push connection), not on a
delay — so there's no "refresh to see the latest" lag.

---

## 4. Saved data

Every action is written immediately to `auction_data.json`, next to the
script. That means:

- You can stop the script and restart it later — everything picks up
  exactly where it left off.
- If you need a clean backup or want to analyze the results afterward,
  use **Export log (.json)** on the console, or just copy
  `auction_data.json` directly.
- **Reset auction** on the console wipes this file and rebuilds from
  `players.json` / `teams.json` — there's no undo for this one (it asks
  for confirmation twice before doing it).

---

## 5. Running it across the room

For other devices to reach the scoreboard, they need to be on the **same
WiFi network** as the host laptop, and use the LAN address printed in the
terminal (not `127.0.0.1`, which only works on the host machine itself).

If a device can't connect:

- Double-check it's on the same WiFi (not a guest network separated from
  the main one — some offices split these).
- The host laptop's firewall may be blocking incoming connections on port
  8080. On Windows this is usually a Defender Firewall prompt the first
  time you run it; on Mac, check System Settings → Network → Firewall.
- Make sure nothing else on the laptop is already using port 8080 — the
  terminal will show an "Address already in use" error if so.

---

## 6. Customization

A few things are deliberately hardcoded constants near the top of
`server.py` rather than exposed in the UI — change them there if
needed:

| Constant | Default | What it controls |
|---|---|---|
| `PURSE`  | `25000` | Tokens each team starts with |
| `SLOTS`  | `3`     | Players each team can buy (on top of their captain) |
| port `8080` (in `main()`, near the bottom) | `8080` | The port the server runs on |

Number of teams is **not** a constant — it's simply how many entries are
in `teams.json`.

---

## Troubleshooting quick reference

| Problem | Likely fix |
|---|---|
| "Address already in use" on startup | Something else is using port 8080 — change the port in `main()`, or close the other program. |
| Other devices can't open the scoreboard | Use the LAN URL, not `127.0.0.1`; check both devices are on the same WiFi; check the host's firewall. |
| A viewer tries an action and gets an error | Expected — only the host laptop can make changes. |
| Console shows "No players left in the pool" | Every player in `players.json` has been sold. Add more entries and hit Reset if you need to extend the auction. |
| Need to redo a sale | Use **Undo last sale** (most recent only) or the ✕ next to a specific player on their team's roster. |
