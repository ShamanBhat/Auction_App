// Auctioneer console — talks to the Flask API (/api/...) and renders the
// console page. Only ever loaded on the host laptop (console.html is only
// served to requests from 127.0.0.1).

let STATE = null;

function syncViewportChrome(){
  const header = document.querySelector('header');
  const footer = document.querySelector('footer');
  const root = document.documentElement;
  if(header){ root.style.setProperty('--header-safe', `${Math.ceil(header.offsetHeight)}px`); }
  if(footer){ root.style.setProperty('--footer-safe', `${Math.ceil(footer.offsetHeight)}px`); }
}

window.addEventListener('resize', syncViewportChrome);

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

function populatePlayerSelect(){
  const sel = document.getElementById('playerSelect');
  const prev = sel.value;
  const teamId = parseInt(document.getElementById('teamSelect').value,10);
  const team = STATE.teams.find(t=>t.id===teamId);
  const isLastSlot = team && team.players.length === STATE.slots - 1;
  const captainIsFemale = team && team.captain_gender === 'F';
  const teamHasFemale = team && team.players.some(p=>p.gender==='F');
  const needsFemale = isLastSlot && !teamHasFemale && !captainIsFemale;
  const available = STATE.players.filter(p=>!p.sold);
  sel.innerHTML = '';
  if(available.length === 0){
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = 'No players left in the pool';
    sel.appendChild(opt);
  } else {
    const ph = document.createElement('option');
    ph.value = '';
    ph.textContent = 'Select a player';
    ph.selected = true;
    sel.appendChild(ph);

    available.forEach(p=>{
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = p.name;
      // Grey out males when last slot requires a female
      if(needsFemale && p.gender !== 'F') opt.disabled = true;
      sel.appendChild(opt);
    });
  }
  if(prev && Array.from(sel.options).some(o=>o.value===prev && !o.disabled)){
    sel.value = prev;
  }
  updateBaseHint();
}

function genderBadge(g){ return `<span class="gender-badge ${g}">${g==='F'?'She/Her':'He/Him'}</span>`; }

function updateBaseHint(){
  const sel = document.getElementById('playerSelect');
  const hint = document.getElementById('baseHint');
  const warn = document.getElementById('teamWarn');
  const costInput = document.getElementById('playerCost');
  const player = STATE.players.find(p=>String(p.id)===sel.value);
  if(player){
    const gLabel = player.gender === 'F' ? 'She/Her' : 'He/Him';
    hint.style.color = 'var(--text-dim)';
    hint.textContent = `Base ${player.base_price.toLocaleString()} · ${player.skill || ''} · ${gLabel}`;
    if(!costInput.value){ costInput.value = player.base_price; }
    costInput.min = player.base_price;
  } else {
    hint.textContent = '';
  }
  if(warn){
    const teamId = parseInt(document.getElementById('teamSelect').value,10);
    const team = STATE.teams.find(t=>t.id===teamId);
    if(team){
      const isLastSlot = team.players.length === STATE.slots - 1;
      const captainIsFemale = team.captain_gender === 'F';
      const teamHasFemale = team.players.some(p=>p.gender==='F');
      if(isLastSlot && !teamHasFemale && !captainIsFemale){
        warn.style.color = '#f77ec0';
        warn.textContent = '⚠ Last slot must be female';
      } else {
        warn.textContent = '';
      }
    }
  }
}

async function announceCurrentBid(){
  const sel = document.getElementById('playerSelect');
  const playerId = sel.value ? parseInt(sel.value,10) : null;
  try{
    STATE = await api('/api/current', {method:'POST',headers:{'Content-Type':'application/json'},
      body: JSON.stringify({player_id: playerId})});
    renderNowBidding(); renderPoolList();
  }catch(err){ showMsg(err.message,'error'); }
}

let _lastBidPlayerId = null;

function renderNowBidding(){
  const box = document.getElementById('nowBidding');
  if(!box) return;
  const p = STATE.current_bid_player;
  if(p){
    const changed = p.id !== _lastBidPlayerId;
    _lastBidPlayerId = p.id;
    box.classList.remove('empty');
    box.innerHTML = `<div class="nb-label">Now bidding</div>
      <div class="nb-name">${esc(p.name)}</div>
      <div class="nb-meta">Base ${p.base_price.toLocaleString()}${p.skill ? ' · '+esc(p.skill) : ''}${p.gender ? ' · '+(p.gender==='F'?'She/Her':'He/Him') : ''}</div>`;
    if(changed){
      box.classList.remove('nb-animate');
      void box.offsetWidth;
      box.classList.add('nb-animate');
      box.addEventListener('animationend',()=>box.classList.remove('nb-animate'),{once:true});
    }
  } else {
    _lastBidPlayerId = null;
    box.classList.add('empty');
    box.classList.remove('nb-animate');
    box.innerHTML = `<div class="nb-label">Now bidding</div><div class="nb-name">—</div><div class="nb-meta">&nbsp;</div>`;
  }
}

function renderPoolList(){
  const list = document.getElementById('poolList');
  list.innerHTML = '';
  STATE.players.forEach(p=>{
    const li = document.createElement('li');
    if(p.sold) li.className = 'sold';
    let statusHtml;
    if(p.sold){
      const team = STATE.teams.find(t=>t.id===p.team_id);
      statusHtml = `<span class="ps sold">${team?esc(team.name):'Sold'} · ${(team?.players.find(x=>x.player_id===p.id)?.cost||0).toLocaleString()}</span>`;
    } else {
      statusHtml = `<span class="ps available">Available</span>`;
    }
    li.innerHTML = `<span class="pn"><span>${esc(p.name)} ${genderBadge(p.gender||'M')}</span><span class="sk">Base ${p.base_price.toLocaleString()}${p.skill?' · '+esc(p.skill):''}</span></span>${statusHtml}`;
    list.appendChild(li);
  });
}

let _lastTickerKey = null;

function renderTicker(){
  const el = document.getElementById('ticker');
  if(!STATE.log.length){ el.innerHTML = '<span>No sales yet — first lot is on the table.</span>'; return; }
  const last = STATE.log[STATE.log.length-1];
  const team = STATE.teams.find(t=>t.id===last.team_id);
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

function renderSummary(){
  const filled = STATE.teams.filter(t=>t.players.length>=STATE.slots).length;
  const sold = STATE.teams.reduce((s,t)=>s+t.players.length,0);
  document.getElementById('sumFilled').textContent = `${filled}/${STATE.teams.length}`;
  document.getElementById('sumSold').textContent = `${sold}/${STATE.players.length}`;
  const spentTotal = STATE.teams.reduce((s,t)=>s+t.spent,0);
  document.getElementById('sumSpent').textContent = spentTotal.toLocaleString();
  document.getElementById('sumLeft').textContent = (STATE.teams.length*STATE.purse - spentTotal).toLocaleString();
}

const _pendingFlash = new Set();

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
    const captainHtml = `
      <li class="captain-entry">
        <div class="cap-top">
          <span class="c-badge">C</span>
          <span class="c-name"><input class="captain-entry-input" type="text" value="${esc(team.captain)}" placeholder="Captain name" data-team="${team.id}" data-field="captain"/></span>
        </div>
        <div class="cap-sub">
          ${team.captain_skill ? `<span class="c-meta">${esc(team.captain_skill)}</span>` : ''}
          ${genderBadge(team.captain_gender||'M')}
        </div>
      </li>`;
    let rosterHtml = team.players.length === 0
      ? '<li class="placeholder">No players bought yet</li>'
      : team.players.map((p,idx)=>`
          <li class="roster-item">
            <div class="ri-top">
              <span class="ri-name">${esc(p.name)}</span>
              <span class="pcost">${p.cost.toLocaleString()}</span>
            </div>
            <div class="ri-sub">
              ${p.skill?`<span class="ri-skill">(${esc(p.skill)})</span>`:''}
              ${genderBadge(p.gender||'M')}
            </div>
            <span class="rm" data-team="${team.id}" data-idx="${idx}" title="Remove">✕</span>
          </li>`).join('');
    const isLastSlotCard = !full && team.players.length === STATE.slots - 1;
    const captainIsFemaleCard = team.captain_gender === 'F';
    const teamHasFemaleCard = team.players.some(p => p.gender === 'F');
    const cardFemaleWarn = (isLastSlotCard && !teamHasFemaleCard && !captainIsFemaleCard)
      ? `<div class="card-female-warn">⚠ Next player must be female</div>`
      : '';
    card.innerHTML = `
      <div class="team-head">
        <div class="team-name"><input type="text" value="${esc(team.name)}" data-team="${team.id}" data-field="name"/></div>
        <div class="slot-count">${team.players.length}/${STATE.slots}</div>
      </div>
      <div class="purse-meter"><div class="purse-fill ${fillClass}" style="width:${pct}%"></div></div>
      <div class="purse-nums"><span class="left">${rem.toLocaleString()} left</span><span>of ${STATE.purse.toLocaleString()}</span></div>
      <ul class="roster captain-section">${captainHtml}</ul>
      <ul class="roster">${rosterHtml}</ul>
      ${cardFemaleWarn}`;
    grid.appendChild(card);
    if(_pendingFlash.has(team.id)){
      _pendingFlash.delete(team.id);
      card.classList.add('sold-flash');
      card.addEventListener('animationend',()=>card.classList.remove('sold-flash'),{once:true});
    }
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

function renderAll(){ populateTeamSelect(); populatePlayerSelect(); renderTeams(); renderTicker(); renderSummary(); renderNowBidding(); renderPoolList(); applyTheme(); renderViewerCount(); }

function renderViewerCount(){
  const n = STATE.viewer_count || 0;
  const el = document.getElementById('viewerCount');
  const num = document.getElementById('viewerNum');
  const lanEl = document.getElementById('lanIp');
  if(!el || !num) return;
  num.textContent = n;
  el.className = 'viewer-count' + (n === 0 ? ' none' : '');
  if(lanEl){
    const ip = STATE.lan_ip;
    lanEl.textContent = (ip && ip !== '127.0.0.1') ? `📡 ${ip}:8080` : '';
  }
}

function applyTheme(){
  const theme = STATE.theme || 'court';
  document.body.classList.toggle('theme-bosch', theme === 'bosch');
  document.body.classList.toggle('theme-stage', theme === 'stage');
  document.querySelectorAll('#themeToggle .tt-btn').forEach(btn=>{
    btn.classList.toggle('active', btn.dataset.theme === theme);
  });
}

async function setTheme(theme){
  try{ STATE = await api('/api/theme', {method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({theme})}); applyTheme(); }
  catch(err){ showMsg(err.message,'error'); }
}

document.querySelectorAll('#themeToggle .tt-btn').forEach(btn=>{
  btn.addEventListener('click', ()=>setTheme(btn.dataset.theme));
});

async function confirmSale(){
  const teamId = parseInt(document.getElementById('teamSelect').value,10);
  const playerSelect = document.getElementById('playerSelect');
  const costInput = document.getElementById('playerCost');
  const playerId = parseInt(playerSelect.value,10);
  const cost = parseInt(costInput.value,10);
  const selectedPlayer = STATE.players.find(p=>p.id===playerId);
  const soldName = selectedPlayer ? selectedPlayer.name : 'Player';
  if(!playerId){ showMsg('Pick a player from the list.','error'); playerSelect.focus(); return; }
  if(isNaN(cost) || cost<=0){ showMsg('Enter a valid cost greater than 0.','error'); costInput.focus(); return; }
  try{
    STATE = await api('/api/sale', {method:'POST',headers:{'Content-Type':'application/json'},
      body: JSON.stringify({team_id:teamId, player_id:playerId, cost:cost})});
    _pendingFlash.add(teamId);
    costInput.value='';
    showMsg(`✓ ${soldName} sold for ${cost.toLocaleString()} tokens.`,'ok');
    renderAll();
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
  renderAll();
  showMsg(STATE.backup_file ? `Auction reset. Previous data backed up to backups/${STATE.backup_file}` : 'Auction reset.', 'ok');
}

document.getElementById('confirmBtn').addEventListener('click', confirmSale);
document.getElementById('undoBtn').addEventListener('click', undoLast);
document.getElementById('resetBtn').addEventListener('click', resetAuction);
document.getElementById('teamSelect').addEventListener('change', ()=>{ populatePlayerSelect(); });
document.getElementById('playerSelect').addEventListener('change', ()=>{ updateBaseHint(); announceCurrentBid(); });
document.getElementById('playerCost').addEventListener('keydown', e=>{ if(e.key==='Enter') confirmSale(); });

(async function init(){
  STATE = await api('/api/state');
  syncViewportChrome();
  renderAll();
  connectConsoleStream();
})();

function connectConsoleStream(){
  const es = new EventSource('/api/console-stream');
  es.onmessage = (e)=>{
    const incoming = JSON.parse(e.data);
    // Only update STATE if it came from an external action (viewer connecting,
    // another tab doing a sale, etc.) — don't clobber a pending input.
    STATE = incoming;
    renderViewerCount();
    // Re-render only the parts that change from external pushes;
    // avoid re-rendering dropdowns mid-input by checking focus.
    const focused = document.activeElement;
    const inputFocused = focused && (focused.tagName === 'INPUT' || focused.tagName === 'SELECT');
    if(!inputFocused){ renderAll(); } else { renderViewerCount(); renderTicker(); renderSummary(); }
  };
  es.onerror = ()=>{
    // Browser will auto-reconnect; do a one-off fetch to stay in sync.
    api('/api/state').then(s=>{ STATE=s; renderViewerCount(); }).catch(()=>{});
  };
}
