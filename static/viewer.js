// Read-only scoreboard — subscribes to the live SSE feed and renders
// whatever state the server pushes. No write calls happen from this file
// at all; the server also independently rejects writes from non-host
// devices, so this is belt-and-suspenders, not the only safeguard.

function esc(s){ const d=document.createElement('div'); d.textContent = s==null?'':s; return d.innerHTML; }
function genderBadge(g){ return `<span class="gender-badge ${g}">${g==='F'?'She/Her':'He/Him'}</span>`; }

function renderTicker(state){
  const el = document.getElementById('ticker');
  if(!state.log.length){ el.innerHTML = '<span>No sales yet — first lot is on the table.</span>'; return; }
  const last = state.log[state.log.length-1];
  const team = state.teams.find(t=>t.id===last.team_id);
  el.innerHTML = `SOLD &nbsp;<b>${esc(last.player)}</b> &nbsp;→&nbsp; ${esc(team?team.name:'?')} &nbsp;for&nbsp; <b>${last.cost.toLocaleString()}</b> tokens`;
}

function renderSummary(state){
  const filled = state.teams.filter(t=>t.players.length>=state.slots).length;
  const sold = state.teams.reduce((s,t)=>s+t.players.length,0);
  document.getElementById('sumFilled').textContent = `${filled}/${state.teams.length}`;
  document.getElementById('sumSold').textContent = `${sold}/${state.players.length}`;
  const spentTotal = state.teams.reduce((s,t)=>s+t.spent,0);
  document.getElementById('sumSpent').textContent = spentTotal.toLocaleString();
  document.getElementById('sumLeft').textContent = (state.teams.length*state.purse - spentTotal).toLocaleString();
}

function renderTeams(state){
  const grid = document.getElementById('teamGrid');
  grid.innerHTML = '';
  state.teams.forEach(team=>{
    const rem = team.remaining;
    const pct = Math.max(0, Math.min(100, (rem/state.purse)*100));
    const full = team.players.length >= state.slots;
    const card = document.createElement('div');
    card.className = 'team-card' + (full?' full':'') + (rem<0?' over':'');
    const fillClass = pct<=15?'crit':(pct<=35?'low':'');
    const captainHtml = `
      <li class="captain-entry">
        <span class="c-badge">C</span>
        <span class="c-name">${esc(team.captain)}</span>
        <span class="c-meta">${team.captain_skill ? esc(team.captain_skill)+' · ' : ''}${genderBadge(team.captain_gender||'M')}</span>
      </li>`;
    let rosterHtml = team.players.length === 0
      ? '<li class="placeholder">No players bought yet</li>'
      : team.players.map(p=>`<li><span>${esc(p.name)}${p.skill?` <span style="color:var(--text-dim)">(${esc(p.skill)})</span>`:''} ${genderBadge(p.gender||'M')}</span><span class="pcost">${p.cost.toLocaleString()}</span></li>`).join('');
    const isLastSlot = !full && team.players.length === state.slots - 1;
    const captainIsFemale = team.captain_gender === 'F';
    const teamHasFemale = team.players.some(p => p.gender === 'F');
    const needsFemale = isLastSlot && !teamHasFemale && !captainIsFemale;
    const femaleWarnHtml = needsFemale
      ? `<div class="card-female-warn">⚠ Next player must be female</div>`
      : '';
    card.innerHTML = `
      <div class="team-head">
        <div class="team-name">${esc(team.name)}</div>
        <div class="slot-count">${team.players.length}/${state.slots}</div>
      </div>
      <div class="purse-meter"><div class="purse-fill ${fillClass}" style="width:${pct}%"></div></div>
      <div class="purse-nums"><span class="left">${rem.toLocaleString()} left</span><span>of ${state.purse.toLocaleString()}</span></div>
      <ul class="roster captain-section">${captainHtml}</ul>
      <ul class="roster">${rosterHtml}</ul>
      ${femaleWarnHtml}`;
    grid.appendChild(card);
  });
}

function renderNowBidding(state){
  const box = document.getElementById('nowBidding');
  const p = state.current_bid_player;
  if(p){
    box.classList.remove('empty');
    box.innerHTML = `<div class="nb-label">Now bidding</div>
      <div class="nb-name">${esc(p.name)}</div>
      <div class="nb-meta">Base ${p.base_price.toLocaleString()}${p.skill ? ' · Skill '+esc(p.skill) : ''}</div>`;
  } else {
    box.classList.add('empty');
    box.innerHTML = `<div class="nb-label">Now bidding</div><div class="nb-name">Waiting for the next player</div>`;
  }
}

function renderPoolList(state){
  const list = document.getElementById('poolList');
  list.innerHTML = '';
  state.players.forEach(p=>{
    const li = document.createElement('li');
    let cls = '';
    if(p.sold) cls += 'sold ';
    if(state.current_bid_player && state.current_bid_player.id === p.id) cls += 'current ';
    li.className = cls.trim();
    let statusHtml;
    if(p.sold){
      const team = state.teams.find(t=>t.id===p.team_id);
      const boughtFor = team ? (team.players.find(x=>x.player_id===p.id)?.cost || 0) : 0;
      statusHtml = `<span class="ps sold">${team?esc(team.name):'Sold'} · ${boughtFor.toLocaleString()}</span>`;
    } else {
      statusHtml = `<span class="ps available">Available</span>`;
    }
    li.innerHTML = `<span class="pn"><span>${esc(p.name)} ${genderBadge(p.gender||'M')}</span><span class="sk">Base ${p.base_price.toLocaleString()}${p.skill?' · '+esc(p.skill):''}</span></span>${statusHtml}`;
    list.appendChild(li);
  });
}

function applyTheme(state){
  const theme = state.theme || 'court';
  document.body.classList.toggle('theme-bosch', theme === 'bosch');
  document.body.classList.toggle('theme-stage', theme === 'stage');
}

async function refresh(){
  try{
    const res = await fetch('/api/state');
    const state = await res.json();
    renderTicker(state); renderSummary(state); renderTeams(state); renderNowBidding(state); renderPoolList(state); applyTheme(state);
  }catch(e){ /* ignore, the stream below will catch up once reconnected */ }
}

// Live push connection — the page updates the instant the auctioneer
// records a sale, undo, or edit, instead of polling on a timer.
function connectStream(){
  const es = new EventSource('/api/stream');
  es.onmessage = (e)=>{
    const state = JSON.parse(e.data);
    renderTicker(state); renderSummary(state); renderTeams(state); renderNowBidding(state); renderPoolList(state); applyTheme(state);
  };
  es.onerror = ()=>{
    // EventSource retries automatically; do an extra one-off fetch so the
    // board still has fresh data while it's reconnecting.
    refresh();
  };
}

connectStream();
