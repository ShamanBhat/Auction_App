#!/usr/bin/env python3
"""
Office Badminton Auction Tracker — Web Edition
------------------------------------------------
A small local web app. Run this script from a terminal:

    pip install flask
    python auction_web.py

Then open the address it prints (usually http://127.0.0.1:5000) in any
browser. The page is the auctioneer console; all data is saved to
auction_data.json next to this script, so closing the browser or the
script is safe — reopen it later and everything is still there.
"""

import json
import os
import webbrowser
import threading
from datetime import datetime

from flask import Flask, jsonify, request, send_file

PURSE = 25000
SLOTS = 3
NUM_TEAMS = 10
SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auction_data.json")

app = Flask(__name__)
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# State handling
# ---------------------------------------------------------------------------

def default_state():
    return {
        "teams": [
            {"id": i, "name": f"Team {i}", "captain": "", "players": []}
            for i in range(1, NUM_TEAMS + 1)
        ],
        "log": [],
    }


def load_state():
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r") as f:
            return json.load(f)
    return default_state()


def save_state(state):
    with open(SAVE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def spent(team):
    return sum(p["cost"] for p in team["players"])


def remaining(team):
    return PURSE - spent(team)


def state_with_budgets(state):
    """Attach computed fields the frontend needs, without mutating saved file."""
    out = json.loads(json.dumps(state))
    for t in out["teams"]:
        t["spent"] = spent(t)
        t["remaining"] = remaining(t)
    out["purse"] = PURSE
    out["slots"] = SLOTS
    return out


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.route("/api/state")
def api_state():
    with _lock:
        state = load_state()
        return jsonify(state_with_budgets(state))


@app.route("/api/sale", methods=["POST"])
def api_sale():
    data = request.get_json(force=True)
    team_id = data.get("team_id")
    name = (data.get("player") or "").strip()
    cost = data.get("cost")

    with _lock:
        state = load_state()
        team = next((t for t in state["teams"] if t["id"] == team_id), None)

        if team is None:
            return jsonify(error="Team not found."), 400
        if not name:
            return jsonify(error="Player name can't be empty."), 400
        if not isinstance(cost, int) or cost <= 0:
            return jsonify(error="Cost must be a positive whole number."), 400
        if len(team["players"]) >= SLOTS:
            return jsonify(error=f"{team['name']} already has {SLOTS} players."), 400
        if cost > remaining(team):
            return jsonify(error=f"{team['name']} only has {remaining(team):,} tokens left."), 400

        team["players"].append({"name": name, "cost": cost})
        state["log"].append({
            "team_id": team_id,
            "player": name,
            "cost": cost,
            "ts": datetime.now().isoformat(timespec="seconds"),
        })
        save_state(state)
        return jsonify(state_with_budgets(state))


@app.route("/api/undo", methods=["POST"])
def api_undo():
    with _lock:
        state = load_state()
        if not state["log"]:
            return jsonify(error="Nothing to undo."), 400
        last = state["log"].pop()
        team = next((t for t in state["teams"] if t["id"] == last["team_id"]), None)
        if team:
            for i, p in enumerate(team["players"]):
                if p["name"] == last["player"] and p["cost"] == last["cost"]:
                    team["players"].pop(i)
                    break
        save_state(state)
        return jsonify(state_with_budgets(state))


@app.route("/api/remove", methods=["POST"])
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
            if not (l["team_id"] == team_id and l["player"] == removed["name"] and l["cost"] == removed["cost"])
        ]
        save_state(state)
        return jsonify(state_with_budgets(state))


@app.route("/api/team", methods=["POST"])
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
        return jsonify(state_with_budgets(state))


@app.route("/api/reset", methods=["POST"])
def api_reset():
    with _lock:
        state = default_state()
        save_state(state)
        return jsonify(state_with_budgets(state))


@app.route("/api/export")
def api_export():
    with _lock:
        if not os.path.exists(SAVE_FILE):
            save_state(default_state())
        return send_file(SAVE_FILE, as_attachment=True, download_name="auction_results.json")


# ---------------------------------------------------------------------------
# Frontend (single page, served at /)
# ---------------------------------------------------------------------------

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Office Badminton Auction</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;600;700&family=Inter:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
:root{
  --court:#0E2A2B; --court-deep:#0A1F20; --panel:#133C3D; --line:#2B5E5C;
  --shuttle:#F4F1E6; --gold:#E8B23C; --gold-dim:#8a6c2e;
  --ok:#6FCF97; --warn:#F2994A; --danger:#EB5757; --text-dim:#9FC1BC;
}
*{box-sizing:border-box;}
body{margin:0;background:radial-gradient(circle at 50% 0%, #143F40 0%, var(--court) 45%, var(--court-deep) 100%);
  color:var(--shuttle);font-family:'Inter',sans-serif;min-height:100vh;padding:28px 20px 60px;}
.wrap{max-width:1180px;margin:0 auto;}
header{display:flex;align-items:flex-end;justify-content:space-between;flex-wrap:wrap;gap:16px;
  border-bottom:2px dashed var(--line);padding-bottom:18px;margin-bottom:22px;}
.eyebrow{font-family:'Space Mono',monospace;font-size:11px;letter-spacing:.18em;color:var(--gold);text-transform:uppercase;}
h1{font-family:'Oswald',sans-serif;font-weight:700;font-size:36px;margin:4px 0 0;text-transform:uppercase;}
.ticker{font-family:'Space Mono',monospace;font-size:13px;color:var(--text-dim);background:var(--court-deep);
  border:1px solid var(--line);border-radius:6px;padding:10px 14px;min-width:280px;max-width:420px;}
.ticker b{color:var(--gold);font-weight:700;}
.console{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:20px 22px;margin-bottom:30px;position:relative;}
.console::before{content:"AUCTIONEER CONSOLE";position:absolute;top:-11px;left:18px;background:var(--gold);
  color:var(--court-deep);font-family:'Space Mono',monospace;font-size:11px;font-weight:700;letter-spacing:.1em;
  padding:3px 10px;border-radius:4px;}
.console-grid{display:grid;grid-template-columns:1.4fr 1.4fr 1fr auto;gap:14px;align-items:end;margin-top:10px;}
@media (max-width:760px){.console-grid{grid-template-columns:1fr 1fr;}}
.field label{display:block;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--text-dim);margin-bottom:6px;}
.field select,.field input{width:100%;background:var(--court-deep);border:1px solid var(--line);color:var(--shuttle);
  border-radius:6px;padding:10px 12px;font-size:15px;font-family:'Inter',sans-serif;}
.field select:focus,.field input:focus{outline:none;border-color:var(--gold);}
.btn{background:var(--gold);color:var(--court-deep);border:none;border-radius:6px;padding:11px 18px;
  font-family:'Oswald',sans-serif;font-weight:600;letter-spacing:.04em;font-size:15px;text-transform:uppercase;
  cursor:pointer;white-space:nowrap;}
.btn:hover{background:#f3c869;}
.btn:disabled{background:#5b5642;color:#9a9682;cursor:not-allowed;}
.btn.secondary{background:transparent;color:var(--text-dim);border:1px solid var(--line);}
.btn.secondary:hover{color:var(--shuttle);border-color:var(--shuttle);}
.console-msg{margin-top:12px;font-family:'Space Mono',monospace;font-size:13px;min-height:18px;}
.console-msg.error{color:var(--danger);}
.console-msg.ok{color:var(--ok);}
.console-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:14px;border-top:1px solid var(--line);padding-top:14px;}
.summary-bar{display:flex;gap:22px;flex-wrap:wrap;margin-bottom:18px;font-family:'Space Mono',monospace;font-size:13px;color:var(--text-dim);}
.summary-bar b{color:var(--shuttle);font-size:15px;}
.teams{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px;}
.team-card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px 16px 14px;display:flex;flex-direction:column;gap:10px;}
.team-card.full{border-color:var(--gold-dim);}
.team-card.over{border-color:var(--danger);}
.team-head{display:flex;justify-content:space-between;align-items:baseline;}
.team-name{font-family:'Oswald',sans-serif;font-size:18px;text-transform:uppercase;letter-spacing:.02em;}
.team-name input{background:transparent;border:none;color:var(--shuttle);font-family:'Oswald',sans-serif;font-size:18px;
  text-transform:uppercase;width:100%;padding:0;letter-spacing:.02em;}
.team-name input:focus{outline:none;border-bottom:1px dashed var(--gold);}
.slot-count{font-family:'Space Mono',monospace;font-size:12px;color:var(--text-dim);}
.captain-row input{background:transparent;border:none;border-bottom:1px dotted var(--line);color:var(--text-dim);
  font-size:12px;width:100%;padding:2px 0;font-family:'Inter',sans-serif;}
.captain-row input:focus{outline:none;border-color:var(--gold);color:var(--shuttle);}
.purse-meter{background:var(--court-deep);border-radius:5px;height:8px;overflow:hidden;}
.purse-fill{height:100%;background:var(--gold);transition:width .3s ease;}
.purse-fill.low{background:var(--warn);}
.purse-fill.crit{background:var(--danger);}
.purse-nums{display:flex;justify-content:space-between;font-family:'Space Mono',monospace;font-size:12px;color:var(--text-dim);}
.purse-nums .left{color:var(--ok);font-weight:700;}
.roster{list-style:none;margin:4px 0 0;padding:0;display:flex;flex-direction:column;gap:4px;}
.roster li{display:flex;justify-content:space-between;font-size:13px;background:var(--court-deep);border-radius:4px;padding:6px 9px;}
.roster li .pcost{color:var(--gold);font-family:'Space Mono',monospace;}
.roster li .rm{cursor:pointer;color:var(--danger);font-family:'Space Mono',monospace;margin-left:8px;opacity:.7;}
.roster li .rm:hover{opacity:1;}
.roster .placeholder{font-size:12px;color:var(--text-dim);font-style:italic;background:none;padding:5px 2px;}
footer{text-align:center;margin-top:34px;font-family:'Space Mono',monospace;font-size:11px;color:var(--text-dim);}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <div class="eyebrow">Office League · Live Auction</div>
      <h1>Badminton Bid Board</h1>
    </div>
    <div class="ticker" id="ticker"><span>No sales yet — first lot is on the table.</span></div>
  </header>

  <div class="console">
    <div class="console-grid">
      <div class="field">
        <label for="teamSelect">Team (buyer)</label>
        <select id="teamSelect"></select>
      </div>
      <div class="field">
        <label for="playerName">Player assigned</label>
        <input type="text" id="playerName" placeholder="e.g. Arjun Rao" autocomplete="off">
      </div>
      <div class="field">
        <label for="playerCost">Cost (tokens)</label>
        <input type="number" id="playerCost" placeholder="0" min="0" step="50">
      </div>
      <button class="btn" id="confirmBtn">Confirm Sale</button>
    </div>
    <div class="console-msg" id="consoleMsg"></div>
    <div class="console-actions">
      <button class="btn secondary" id="undoBtn">Undo last sale</button>
      <a class="btn secondary" id="exportBtn" href="/api/export">Export log (.json)</a>
      <button class="btn secondary" id="resetBtn">Reset auction</button>
    </div>
  </div>

  <div class="summary-bar">
    <div>Teams filled: <b id="sumFilled">0/10</b></div>
    <div>Players sold: <b id="sumSold">0/30</b></div>
    <div>Tokens spent: <b id="sumSpent">0</b></div>
    <div>Tokens unspent: <b id="sumLeft">250000</b></div>
  </div>

  <div class="teams" id="teamGrid"></div>
  <footer>Saved automatically to auction_data.json next to the script</footer>
</div>

<script>
let STATE = null;

function esc(s){ const d=document.createElement('div'); d.textContent = s==null?'':s; return d.innerHTML; }

async function api(path, opts){
  const res = await fetch(path, opts);
  const data = await res.json();
  if(!res.ok){ throw new Error(data.error || 'Something went wrong.'); }
  return data;
}

function showMsg(text, type){
  const el = document.getElementById('consoleMsg');
  el.textContent = text;
  el.className = 'console-msg' + (type ? ' '+type : '');
}

function populateTeamSelect(){
  const sel = document.getElementById('teamSelect');
  const prev = sel.value;
  sel.innerHTML = '';
  STATE.teams.forEach(t=>{
    const full = t.players.length >= STATE.slots;
    const opt = document.createElement('option');
    opt.value = t.id;
    opt.textContent = `${t.name}${t.captain ? ' — '+t.captain : ''} (${full ? 'FULL' : (STATE.slots - t.players.length)+' slot left'})`;
    if(full) opt.disabled = true;
    sel.appendChild(opt);
  });
  if(prev) sel.value = prev;
}

function renderTicker(){
  const el = document.getElementById('ticker');
  if(!STATE.log.length){ el.innerHTML = '<span>No sales yet — first lot is on the table.</span>'; return; }
  const last = STATE.log[STATE.log.length-1];
  const team = STATE.teams.find(t=>t.id===last.team_id);
  el.innerHTML = `SOLD &nbsp;<b>${esc(last.player)}</b> &nbsp;→&nbsp; ${esc(team?team.name:'?')} &nbsp;for&nbsp; <b>${last.cost.toLocaleString()}</b> tokens`;
}

function renderSummary(){
  const filled = STATE.teams.filter(t=>t.players.length>=STATE.slots).length;
  const sold = STATE.teams.reduce((s,t)=>s+t.players.length,0);
  document.getElementById('sumFilled').textContent = `${filled}/${STATE.teams.length}`;
  document.getElementById('sumSold').textContent = `${sold}/${STATE.teams.length*STATE.slots}`;
  const spentTotal = STATE.teams.reduce((s,t)=>s+t.spent,0);
  document.getElementById('sumSpent').textContent = spentTotal.toLocaleString();
  document.getElementById('sumLeft').textContent = (STATE.teams.length*STATE.purse - spentTotal).toLocaleString();
}

function renderTeams(){
  const grid = document.getElementById('teamGrid');
  grid.innerHTML = '';
  STATE.teams.forEach(team=>{
    const rem = team.remaining;
    const pct = Math.max(0, Math.min(100, (rem/STATE.purse)*100));
    const full = team.players.length >= STATE.slots;
    const card = document.createElement('div');
    card.className = 'team-card' + (full?' full':'') + (rem<0?' over':'');
    const fillClass = pct<=15?'crit':(pct<=35?'low':'');
    let rosterHtml = team.players.length === 0
      ? '<li class="placeholder">No players bought yet</li>'
      : team.players.map((p,idx)=>`
          <li><span>${esc(p.name)}</span>
            <span><span class="pcost">${p.cost.toLocaleString()}</span>
            <span class="rm" data-team="${team.id}" data-idx="${idx}" title="Remove">✕</span></span>
          </li>`).join('');
    card.innerHTML = `
      <div class="team-head">
        <div class="team-name"><input type="text" value="${esc(team.name)}" data-team="${team.id}" data-field="name"/></div>
        <div class="slot-count">${team.players.length}/${STATE.slots}</div>
      </div>
      <div class="captain-row"><input type="text" placeholder="Captain name" value="${esc(team.captain)}" data-team="${team.id}" data-field="captain"/></div>
      <div class="purse-meter"><div class="purse-fill ${fillClass}" style="width:${pct}%"></div></div>
      <div class="purse-nums"><span class="left">${rem.toLocaleString()} left</span><span>of ${STATE.purse.toLocaleString()}</span></div>
      <ul class="roster">${rosterHtml}</ul>`;
    grid.appendChild(card);
  });
  grid.querySelectorAll('input[data-field]').forEach(inp=>{
    inp.addEventListener('change', async e=>{
      const body = { team_id: parseInt(e.target.dataset.team,10), [e.target.dataset.field]: e.target.value };
      try{ STATE = await api('/api/team', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); renderAll(); }
      catch(err){ showMsg(err.message,'error'); }
    });
  });
  grid.querySelectorAll('.rm').forEach(btn=>{
    btn.addEventListener('click', async e=>{
      const body = { team_id: parseInt(e.target.dataset.team,10), index: parseInt(e.target.dataset.idx,10) };
      try{ STATE = await api('/api/remove', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); renderAll(); showMsg('Removed.','ok'); }
      catch(err){ showMsg(err.message,'error'); }
    });
  });
}

function renderAll(){ populateTeamSelect(); renderTeams(); renderTicker(); renderSummary(); }

async function confirmSale(){
  const teamId = parseInt(document.getElementById('teamSelect').value,10);
  const nameInput = document.getElementById('playerName');
  const costInput = document.getElementById('playerCost');
  const name = nameInput.value.trim();
  const cost = parseInt(costInput.value,10);
  if(!name){ showMsg("Enter the player's name.",'error'); nameInput.focus(); return; }
  if(isNaN(cost) || cost<=0){ showMsg('Enter a valid cost greater than 0.','error'); costInput.focus(); return; }
  try{
    STATE = await api('/api/sale', {method:'POST',headers:{'Content-Type':'application/json'},
      body: JSON.stringify({team_id:teamId, player:name, cost:cost})});
    nameInput.value=''; costInput.value='';
    showMsg(`✓ ${name} sold for ${cost.toLocaleString()} tokens.`,'ok');
    renderAll(); nameInput.focus();
  }catch(err){ showMsg(err.message,'error'); }
}

async function undoLast(){
  try{ STATE = await api('/api/undo', {method:'POST'}); renderAll(); showMsg('Last sale undone.','ok'); }
  catch(err){ showMsg(err.message,'error'); }
}

async function resetAuction(){
  if(!confirm('This clears every sale, budget and name. Are you sure?')) return;
  if(!confirm('Really sure? This cannot be undone.')) return;
  STATE = await api('/api/reset', {method:'POST'});
  renderAll(); showMsg('Auction reset.','ok');
}

document.getElementById('confirmBtn').addEventListener('click', confirmSale);
document.getElementById('undoBtn').addEventListener('click', undoLast);
document.getElementById('resetBtn').addEventListener('click', resetAuction);
document.getElementById('playerCost').addEventListener('keydown', e=>{ if(e.key==='Enter') confirmSale(); });
document.getElementById('playerName').addEventListener('keydown', e=>{ if(e.key==='Enter') document.getElementById('playerCost').focus(); });

(async function init(){
  STATE = await api('/api/state');
  renderAll();
})();
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return PAGE


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
    app.run(debug=False, port=8080, host="0.0.0.0")


if __name__ == "__main__":
    main()