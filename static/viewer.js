// Read-only scoreboard — subscribes to the live SSE feed and renders
// whatever state the server pushes. No write calls happen from this file
// at all; the server also independently rejects writes from non-host
// devices, so this is belt-and-suspenders, not the only safeguard.

function esc(s){ const d=document.createElement('div'); d.textContent = s==null?'':s; return d.innerHTML; }
function genderBadge(g){ return `<span class="gender-badge ${g}">${g==='F'?'She/Her':'He/Him'}</span>`; }

function syncViewportChrome(){
  const header = document.querySelector('header');
  const footer = document.querySelector('footer');
  const root = document.documentElement;
  if(header){ root.style.setProperty('--header-safe', `${Math.ceil(header.offsetHeight)}px`); }
  if(footer){ root.style.setProperty('--footer-safe', `${Math.ceil(footer.offsetHeight)}px`); }
}

window.addEventListener('resize', syncViewportChrome);

let _lastTickerKey = null;

function renderTicker(state){
  const el = document.getElementById('ticker');
  if(!state.log.length){ el.innerHTML = '<span>No sales yet — first lot is on the table.</span>'; return; }
  const last = state.log[state.log.length-1];
  const team = state.teams.find(t=>t.id===last.team_id);
  const key = `${last.player}|${last.team_id}|${last.cost}`;
  if(key !== _lastTickerKey){
    _lastTickerKey = key;
    el.classList.remove('ticker-animate');
    void el.offsetWidth; // force reflow to restart animation
    el.innerHTML = `SOLD &nbsp;<b>${esc(last.player)}</b> &nbsp;to&nbsp; <b>${esc(team?team.name:'?')}</b> &nbsp;for&nbsp; <b>${last.cost.toLocaleString()}</b> tokens`;
    el.classList.add('ticker-animate');
    el.addEventListener('animationend',()=>el.classList.remove('ticker-animate'),{once:true});
  }
}

let _prevTeamCounts = {};

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
        <div class="cap-top">
          <span class="c-badge">C</span>
          <span class="c-name">${esc(team.captain)}</span>
        </div>
        <div class="cap-sub">
          ${team.captain_skill ? `<span class="c-meta">${esc(team.captain_skill)}</span>` : ''}
          ${genderBadge(team.captain_gender||'M')}
        </div>
      </li>`;
    let rosterHtml = team.players.length === 0
      ? '<li class="placeholder">No players bought yet</li>'
      : team.players.map(p=>`
          <li class="roster-item">
            <div class="ri-top">
              <span class="ri-name">${esc(p.name)}</span>
              <span class="pcost">${p.cost.toLocaleString()}</span>
            </div>
            <div class="ri-sub">
              ${p.skill?`<span class="ri-skill">(${esc(p.skill)})</span>`:''}
              ${genderBadge(p.gender||'M')}
            </div>
          </li>`).join('');
    const isLastSlot = !full && team.players.length === state.slots - 1;
    const captainIsFemale = team.captain_gender === 'F';
    const teamHasFemale = team.players.some(p => p.gender === 'F');
    const needsFemale = isLastSlot && !teamHasFemale && !captainIsFemale;
    const femaleCount = (captainIsFemale ? 1 : 0) + team.players.filter(p => p.gender === 'F').length;
    const femaleFull = !full && femaleCount >= 2;
    const femaleWarnHtml = needsFemale
      ? `<div class="card-female-warn">⚠ Next player must be female</div>`
      : (femaleFull
        ? `<div class="card-female-warn">⚠ Max 2 females reached</div>`
        : '');
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
    if(_prevTeamCounts[team.id] !== undefined && team.players.length > _prevTeamCounts[team.id]){
      card.classList.add('sold-flash');
      card.addEventListener('animationend',()=>card.classList.remove('sold-flash'),{once:true});
    }
  });
  _prevTeamCounts = {};
  state.teams.forEach(t=>{ _prevTeamCounts[t.id] = t.players.length; });
}

let _lastBidPlayerId = null;
let _nbExiting = false;

function renderNowBidding(state){
  const box = document.getElementById('nowBidding');
  if(!box) return;
  const p = state.current_bid_player;
  const hadPlayer = _lastBidPlayerId !== null;
  const changed = p ? p.id !== _lastBidPlayerId : hadPlayer;
  function applyContent(){
    if(p){
      box.classList.remove('empty');
      box.innerHTML = `<div class="nb-label">Now bidding</div>
      <div class="nb-name">${esc(p.name)}</div>
      <div class="nb-meta">Base ${p.base_price.toLocaleString()}${p.skill ? ' · '+esc(p.skill) : ''}${p.gender ? ' · '+(p.gender==='F'?'She/Her':'He/Him') : ''}</div>`;
      box.classList.remove('nb-animate'); void box.offsetWidth; box.classList.add('nb-animate');
      box.addEventListener('animationend',()=>box.classList.remove('nb-animate'),{once:true});
    } else {
      box.classList.add('empty'); box.classList.remove('nb-animate');
      box.innerHTML = `<div class="nb-label">Now bidding</div><div class="nb-name">—</div><div class="nb-meta">&nbsp;</div>`;
    }
  }
  if(changed && hadPlayer && !_nbExiting){
    _nbExiting = true;
    _lastBidPlayerId = p ? p.id : null;
    box.classList.add('nb-exit');
    setTimeout(()=>{ box.classList.remove('nb-exit'); _nbExiting = false; applyContent(); }, 260);
  } else if(!_nbExiting){
    _lastBidPlayerId = p ? p.id : null;
    if(changed) applyContent();
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

function renderRules(state){
  const overlay = document.getElementById('rulesOverlay');
  if(!overlay) return;
  const show = !!state.show_rules;
  overlay.classList.toggle('open', show);
  overlay.setAttribute('aria-hidden', show ? 'false' : 'true');
}

function renderSplash(state){
  const overlay = document.getElementById('splashOverlay');
  if(!overlay) return;
  const show = !!state.show_splash;
  overlay.classList.toggle('open', show);
  overlay.setAttribute('aria-hidden', show ? 'false' : 'true');
}

async function refresh(){
  try{
    const res = await fetch('/api/state');
    const state = await res.json();
    renderTicker(state); renderTeams(state); renderNowBidding(state); renderPoolList(state); applyTheme(state); renderRules(state); renderSplash(state);
  }catch(e){ /* ignore, the stream below will catch up once reconnected */ }
}

// Live push connection — the page updates the instant the auctioneer
// records a sale, undo, or edit, instead of polling on a timer.
function connectStream(){
  const es = new EventSource('/api/stream');
  es.onmessage = (e)=>{
    const state = JSON.parse(e.data);
    renderTicker(state); renderTeams(state); renderNowBidding(state); renderPoolList(state); applyTheme(state); renderRules(state); renderSplash(state);
  };
  es.onerror = ()=>{
    // EventSource retries automatically; do an extra one-off fetch so the
    // board still has fresh data while it's reconnecting.
    refresh();
  };
}

connectStream();
syncViewportChrome();
