#!/usr/bin/env python3
"""
Office Badminton Auction Tracker — Web Edition
------------------------------------------------
A small local web app. Run this script from a terminal:

    pip install flask
    python server.py

Then open the address it prints (usually http://127.0.0.1:8080) in any
browser. The page is the auctioneer console; all data is saved to
auction_data.json next to this script, so closing the browser or the
script is safe — reopen it later and everything is still there.

This file is just the backend (routes + state). The actual pages live in
templates/ (console.html, viewer.html) and static/ (the CSS and JS for
each page) — Flask serves those automatically since they sit in the
default templates/ and static/ folders next to this script.
"""

import json
import os
import queue
import shutil
import webbrowser
import threading
from datetime import datetime

from flask import Flask, jsonify, request, send_file, Response, render_template

PURSE = 25000
SLOTS = 3   # players each team bids for — fixed, not derived from players.json
DEFAULT_TEAMS_IF_MISSING = 10
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_FILE = os.path.join(SCRIPT_DIR, "auction_data.json")
BACKUPS_DIR = os.path.join(SCRIPT_DIR, "backups")
PLAYERS_FILE = os.path.join(SCRIPT_DIR, "players.json")
TEAMS_FILE = os.path.join(SCRIPT_DIR, "teams.json")

# template_folder/static_folder default to "templates"/"static" next to this
# file, which is exactly where they live — nothing extra to configure.
app = Flask(__name__)
_lock = threading.RLock()

# _subscribers   — viewer SSE connections (non-host). Counted in viewer_count.
# _console_subs  — console SSE connections (host).   NOT counted in viewer_count.
# Both receive every broadcast so the console sees viewer_count changes live.
_subscribers = []
_console_subs = []
_subscribers_lock = threading.Lock()


# ---------------------------------------------------------------------------
# players.json / teams.json — edited by the auctioneer before the auction.
# Team count comes from how many entries are in teams.json (edit the file
# and hit Reset to change it). players.json is the pool of players up for
# auction — its size doesn't have to match num_teams * SLOTS; extra players
# just stay unsold. How many of those each team can buy is the fixed SLOTS
# constant above.
# ---------------------------------------------------------------------------

def ensure_teams_file():
    """Create a starter teams.json the first time the script runs. Each
    entry pre-fills a team's name and captain."""
    if not os.path.exists(TEAMS_FILE):
        sample = [
            {"name": f"Team {i}", "captain": ""}
            for i in range(1, DEFAULT_TEAMS_IF_MISSING + 1)
        ]
        with open(TEAMS_FILE, "w") as f:
            json.dump(sample, f, indent=2)

    with open(TEAMS_FILE, "r") as f:
        return json.load(f)


def ensure_players_file(num_teams):
    """Create a starter players.json the first time the script runs, so
    there's something to edit. Returns the pool as a list of dicts with a
    stable numeric id assigned by position in the file."""
    if not os.path.exists(PLAYERS_FILE):
        total = max(1, num_teams) * SLOTS
        sample = [
            {"name": f"Player {i}", "base_price": 500, "skill": "B", "gender": "M"}
            for i in range(1, total + 1)
        ]
        with open(PLAYERS_FILE, "w") as f:
            json.dump(sample, f, indent=2)

    with open(PLAYERS_FILE, "r") as f:
        raw = json.load(f)

    pool = []
    for i, p in enumerate(raw, start=1):
        raw_gender = (p.get("gender") or "M").strip().upper()
        gender = "F" if raw_gender in ("F", "FEMALE", "SHE", "HER") else "M"
        pool.append({
            "id": i,
            "name": (p.get("name") or f"Player {i}").strip(),
            "base_price": int(p.get("base_price") or 0),
            "skill": (p.get("skill") or "").strip(),
            "gender": gender,
        })
    return pool


# ---------------------------------------------------------------------------
# State handling
# ---------------------------------------------------------------------------

def default_state():
    teams_info = ensure_teams_file()
    num_teams = max(1, len(teams_info))
    players_pool = ensure_players_file(num_teams)

    teams = []
    for i in range(1, num_teams + 1):
        info = teams_info[i - 1] if i - 1 < len(teams_info) else {}
        teams.append({
            "id": i,
            "name": (info.get("name") or f"Team {i}").strip() or f"Team {i}",
            "captain": (info.get("captain") or "").strip(),
            "players": [],
        })

    for p in players_pool:
        p["sold"] = False
        p["team_id"] = None

    return {
        "config": {"num_teams": num_teams, "slots": SLOTS, "purse": PURSE},
        "teams": teams,
        "players": players_pool,
        "log": [],
        "current_bid_player_id": None,
        "theme": "court",
    }


def load_state():
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r") as f:
            state = json.load(f)
        # Migrate saves from before the player pool / captain presets / live
        # config existed.
        if "players" not in state:
            num_teams = len(state.get("teams", [])) or DEFAULT_TEAMS_IF_MISSING
            pool = ensure_players_file(num_teams)
            for p in pool:
                p["sold"] = False
                p["team_id"] = None
            state["players"] = pool
        if "config" not in state:
            num_teams = len(state.get("teams", [])) or DEFAULT_TEAMS_IF_MISSING
            state["config"] = {"num_teams": num_teams, "slots": SLOTS, "purse": PURSE}
        if "current_bid_player_id" not in state:
            state["current_bid_player_id"] = None
        if "theme" not in state:
            state["theme"] = "court"

        # Migrate: backfill missing 'gender' field on any player entry (both
        # in the pool and already bought into teams). Read the current
        # players.json to get the canonical gender for each id, then fall
        # back to "M" if it's genuinely not specified anywhere.
        needs_gender = any("gender" not in p for p in state.get("players", []))
        if needs_gender:
            try:
                num_teams = len(state.get("teams", [])) or DEFAULT_TEAMS_IF_MISSING
                fresh_pool = ensure_players_file(num_teams)
                gender_map = {p["id"]: p["gender"] for p in fresh_pool}
            except Exception:
                gender_map = {}
            for p in state.get("players", []):
                if "gender" not in p:
                    p["gender"] = gender_map.get(p["id"], "M")
            # Also patch players already stored inside team rosters
            for team in state.get("teams", []):
                for rp in team.get("players", []):
                    if "gender" not in rp:
                        rp["gender"] = gender_map.get(rp.get("player_id"), "M")

        return state
    return default_state()


def save_state(state):
    with open(SAVE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def backup_current_data():
    """Copy the current auction_data.json into backups/ before it gets
    overwritten by a reset. Returns the backup path, or None if there was
    nothing to back up yet."""
    if not os.path.exists(SAVE_FILE):
        return None
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUPS_DIR, f"auction_data_backup_{stamp}.json")
    shutil.copy2(SAVE_FILE, backup_path)
    return backup_path


def spent(team):
    return sum(p["cost"] for p in team["players"])


def remaining(team, state):
    return state["config"]["purse"] - spent(team)


def state_with_budgets(state):
    """Attach computed fields the frontend needs, without mutating saved file."""
    out = json.loads(json.dumps(state))
    for t in out["teams"]:
        t["spent"] = spent(t)
        t["remaining"] = remaining(t, state)
    out["purse"] = state["config"]["purse"]
    out["slots"] = state["config"]["slots"]
    out["current_bid_player"] = next(
        (p for p in out["players"] if p["id"] == out.get("current_bid_player_id")), None
    )
    with _subscribers_lock:
        out["viewer_count"] = len(_subscribers)
    return out


def is_host():
    """True only for requests coming from the machine running this script
    (i.e. opened via 127.0.0.1 / localhost). Every other device on the
    network — even on the same WiFi — is treated as read-only."""
    return request.remote_addr in ("127.0.0.1", "::1")


def require_host(view):
    from functools import wraps

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_host():
            return jsonify(error="Read-only view — open this on the auctioneer's "
                                  "laptop to make changes."), 403
        return view(*args, **kwargs)
    return wrapped


def _push_to_list(lst, payload):
    """Push payload to every queue in lst; return queues that are dead."""
    dead = []
    for q in lst:
        try:
            q.put_nowait(payload)
        except queue.Full:
            dead.append(q)
    return dead


def broadcast_update():
    """Push the latest state to every connected viewer and console immediately.
    Called at the end of any action that changes data, and also whenever a
    viewer connects or disconnects (so the console's viewer count stays live)."""
    with _lock:
        state = load_state()
        payload = json.dumps(state_with_budgets(state))
    with _subscribers_lock:
        dead_v = _push_to_list(_subscribers, payload)
        dead_c = _push_to_list(_console_subs, payload)
        for q in dead_v:
            _subscribers.remove(q)
        for q in dead_c:
            _console_subs.remove(q)


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.route("/api/state")
def api_state():
    with _lock:
        state = load_state()
        return jsonify(state_with_budgets(state))


@app.route("/api/stream")
def api_stream():
    """Server-Sent Events feed for viewers. Broadcasts on connect and
    disconnect so the console's viewer count updates in real time."""
    def gen():
        q = queue.Queue(maxsize=20)
        with _subscribers_lock:
            _subscribers.append(q)
        # Notify console of updated viewer count — run in a daemon thread so
        # we're not holding _subscribers_lock during the broadcast.
        threading.Thread(target=broadcast_update, daemon=True).start()
        try:
            with _lock:
                state = load_state()
            yield f"data: {json.dumps(state_with_budgets(state))}\n\n"
            while True:
                try:
                    payload = q.get(timeout=25)
                    yield f"data: {payload}\n\n"
                except queue.Empty:
                    yield ": keep-alive\n\n"
        finally:
            with _subscribers_lock:
                if q in _subscribers:
                    _subscribers.remove(q)
            threading.Thread(target=broadcast_update, daemon=True).start()

    return Response(
        gen(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/console-stream")
def api_console_stream():
    """SSE feed for the auctioneer console only (host-only). Connections here
    are NOT counted in viewer_count — the console subscribes to this so it
    can receive live broadcasts (including viewer count changes) without
    inflating the viewer number shown to the room."""
    if not is_host():
        return jsonify(error="Console stream is host-only."), 403

    def gen():
        q = queue.Queue(maxsize=20)
        with _subscribers_lock:
            _console_subs.append(q)
        try:
            with _lock:
                state = load_state()
            yield f"data: {json.dumps(state_with_budgets(state))}\n\n"
            while True:
                try:
                    payload = q.get(timeout=25)
                    yield f"data: {payload}\n\n"
                except queue.Empty:
                    yield ": keep-alive\n\n"
        finally:
            with _subscribers_lock:
                if q in _console_subs:
                    _console_subs.remove(q)

    return Response(
        gen(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/sale", methods=["POST"])
@require_host
def api_sale():
    data = request.get_json(force=True)
    team_id = data.get("team_id")
    player_id = data.get("player_id")
    cost = data.get("cost")

    with _lock:
        state = load_state()
        team = next((t for t in state["teams"] if t["id"] == team_id), None)
        player = next((p for p in state["players"] if p["id"] == player_id), None)

        if team is None:
            return jsonify(error="Team not found."), 400
        if player is None:
            return jsonify(error="Pick a player from the list."), 400
        if player["sold"]:
            return jsonify(error=f"{player['name']} has already been sold."), 400
        if not isinstance(cost, int) or cost <= 0:
            return jsonify(error="Cost must be a positive whole number."), 400
        if cost < player["base_price"]:
            return jsonify(error=f"Cost can't be below {player['name']}'s base price "
                                  f"of {player['base_price']:,}."), 400
        if len(team["players"]) >= state["config"]["slots"]:
            return jsonify(error=f"{team['name']} already has {state['config']['slots']} players."), 400
        if cost > remaining(team, state):
            return jsonify(error=f"{team['name']} only has {remaining(team, state):,} tokens left."), 400

        # Enforce: each team must have at least 1 female player. If this is
        # the last slot and there are no females yet, only a female player
        # can be bought.
        slots = state["config"]["slots"]
        is_last_slot = len(team["players"]) == slots - 1
        team_has_female = any(p.get("gender") == "F" for p in team["players"])
        if is_last_slot and not team_has_female and player.get("gender") != "F":
            # Count available female players to give a helpful message
            available_females = [
                p for p in state["players"]
                if not p["sold"] and p.get("gender") == "F"
            ]
            return jsonify(
                error=f"{team['name']} has no female players yet — the last slot must be filled by a female player. "
                      f"({len(available_females)} female player{'s' if len(available_females) != 1 else ''} still available)"
            ), 400

        player["sold"] = True
        player["team_id"] = team_id
        team["players"].append({
            "player_id": player["id"],
            "name": player["name"],
            "base_price": player["base_price"],
            "skill": player["skill"],
            "gender": player.get("gender", "M"),
            "cost": cost,
        })
        state["log"].append({
            "team_id": team_id,
            "player_id": player["id"],
            "player": player["name"],
            "cost": cost,
            "ts": datetime.now().isoformat(timespec="seconds"),
        })
        if state.get("current_bid_player_id") == player["id"]:
            state["current_bid_player_id"] = None
        save_state(state)
        broadcast_update()
        return jsonify(state_with_budgets(state))


@app.route("/api/current", methods=["POST"])
@require_host
def api_current():
    """Tell viewers which player is currently up for bidding. Called when
    the auctioneer picks a player in the console dropdown, before the sale
    is confirmed. Pass player_id: null to clear it."""
    data = request.get_json(force=True)
    player_id = data.get("player_id")
    with _lock:
        state = load_state()
        if player_id is not None:
            player = next((p for p in state["players"] if p["id"] == player_id), None)
            if player is None:
                return jsonify(error="Player not found."), 400
            if player["sold"]:
                return jsonify(error=f"{player['name']} has already been sold."), 400
        state["current_bid_player_id"] = player_id
        save_state(state)
        broadcast_update()
        return jsonify(state_with_budgets(state))


VALID_THEMES = ("court", "bosch")


@app.route("/api/theme", methods=["POST"])
@require_host
def api_theme():
    """Switch the color theme for everyone — console and every connected
    viewer pick it up immediately since it goes out over the same live
    update channel as a sale or undo."""
    data = request.get_json(force=True)
    theme = data.get("theme")
    if theme not in VALID_THEMES:
        return jsonify(error=f"Theme must be one of {', '.join(VALID_THEMES)}."), 400
    with _lock:
        state = load_state()
        state["theme"] = theme
        save_state(state)
        broadcast_update()
        return jsonify(state_with_budgets(state))


@app.route("/api/undo", methods=["POST"])
@require_host
def api_undo():
    with _lock:
        state = load_state()
        if not state["log"]:
            return jsonify(error="Nothing to undo."), 400
        last = state["log"].pop()
        team = next((t for t in state["teams"] if t["id"] == last["team_id"]), None)
        if team:
            for i, p in enumerate(team["players"]):
                if p.get("player_id") == last.get("player_id"):
                    team["players"].pop(i)
                    break
        player = next((p for p in state["players"] if p["id"] == last.get("player_id")), None)
        if player:
            player["sold"] = False
            player["team_id"] = None
        save_state(state)
        broadcast_update()
        return jsonify(state_with_budgets(state))


@app.route("/api/remove", methods=["POST"])
@require_host
def api_remove():
    data = request.get_json(force=True)
    team_id = data.get("team_id")
    index = data.get("index")
    with _lock:
        state = load_state()
        team = next((t for t in state["teams"] if t["id"] == team_id), None)
        if team is None or index is None or not (0 <= index < len(team["players"])):
            return jsonify(error="Could not find that player."), 400
        removed = team["players"].pop(index)
        state["log"] = [
            l for l in state["log"]
            if not (l["team_id"] == team_id and l.get("player_id") == removed.get("player_id"))
        ]
        player = next((p for p in state["players"] if p["id"] == removed.get("player_id")), None)
        if player:
            player["sold"] = False
            player["team_id"] = None
        save_state(state)
        broadcast_update()
        return jsonify(state_with_budgets(state))


@app.route("/api/team", methods=["POST"])
@require_host
def api_team():
    data = request.get_json(force=True)
    team_id = data.get("team_id")
    with _lock:
        state = load_state()
        team = next((t for t in state["teams"] if t["id"] == team_id), None)
        if team is None:
            return jsonify(error="Team not found."), 400
        if "name" in data and data["name"].strip():
            team["name"] = data["name"].strip()
        if "captain" in data:
            team["captain"] = data["captain"].strip()
        save_state(state)
        broadcast_update()
        return jsonify(state_with_budgets(state))


@app.route("/api/reset", methods=["POST"])
@require_host
def api_reset():
    with _lock:
        backup_path = backup_current_data()
        state = default_state()
        save_state(state)
        broadcast_update()
        out = state_with_budgets(state)
        out["backup_file"] = os.path.basename(backup_path) if backup_path else None
        return jsonify(out)


@app.route("/api/export")
@require_host
def api_export():
    with _lock:
        if not os.path.exists(SAVE_FILE):
            save_state(default_state())
        return send_file(SAVE_FILE, as_attachment=True, download_name="auction_results.json")


# ---------------------------------------------------------------------------
# Frontend — console.html for the host, viewer.html for everyone else.
# Both live in templates/, with their CSS/JS in static/.
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("console.html") if is_host() else render_template("viewer.html")


def get_lan_ip():
    """Best-effort guess at this machine's LAN IP (the one other devices on
    the same WiFi can reach). Falls back to 127.0.0.1 if it can't tell."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't actually send anything — just asks the OS which local
        # interface it would use to reach an external address.
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def main():
    local_url = "http://127.0.0.1:8080"
    lan_ip = get_lan_ip()
    print("Starting auction board...")
    print(f"  On this laptop      : {local_url}")
    if lan_ip != "127.0.0.1":
        print(f"  From other devices  : http://{lan_ip}:8080  (same WiFi only)")
    else:
        print("  Could not detect a LAN IP — other devices may not be able to connect.")
    print("Press Ctrl+C to stop.\n")
    threading.Timer(1.0, lambda: webbrowser.open(local_url)).start()
    # host="0.0.0.0" makes the server listen on every network interface,
    # not just localhost, so other devices on the WiFi can reach it.
    # threaded=True matters here: the live viewer connections (SSE) stay
    # open continuously, so without this the server could only handle one
    # browser tab at a time.
    app.run(debug=False, port=8080, host="0.0.0.0", threaded=True)


if __name__ == "__main__":
    main()
