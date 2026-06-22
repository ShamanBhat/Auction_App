// Auctioneer console — talks to the Flask API (/api/...) and renders the
// console page. Only ever loaded on the host laptop (console.html is only
// served to requests from 127.0.0.1).

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
    available.forEach(p=>{
      const opt = document.createElement('option');
      opt.value = p.id;
      const skill = p.skill ? ` · ${p.skill}` : '';
      const gLabel = p.gender === 'F' ? ' · She/Her' : ' · He/Him';
      opt.textContent = `${p.name} — base ${p.base_price.toLocaleString()}${skill}${gLabel}`;
      // Grey out males when last slot requires a female
      if(needsFemale && p.gender !== 'F') opt.disabled = true;
      sel.appendChild(opt);
    });
  }
  if(prev) sel.value = prev;
  updateBaseHint();
}

function genderBadge(g){ return `<span class="gender-badge ${g}">${g==='F'?'She/Her':'He/Him'}</span>`; }

function updateBaseHint(){
  const sel = document.getElementById('playerSelect');
  const hint = document.getElementById('baseHint');
  const warn = document.getElementById('femaleWarn');
  const costInput = document.getElementById('playerCost');
  const player = STATE.players.find(p=>String(p.id)===sel.value);
  if(player){
    hint.innerHTML = `Base price: ${player.base_price.toLocaleString()}${player.skill ? ' · Skill '+player.skill : ''} ${genderBadge(player.gender)}`;
    if(!costInput.value){ costInput.value = player.base_price; }
    costInput.min = player.base_price;
  } else {
    hint.textContent = '\u00A0';
  }
  // Check if selected team's last slot requires a female player
  if(warn){
    const teamId = parseInt(document.getElementById('teamSelect').value,10);
    const team = STATE.teams.find(t=>t.id===teamId);
    if(team){
      const isLastSlot = team.players.length === STATE.slots - 1;
      const captainIsFemale = team.captain_gender === 'F';
      const teamHasFemale = team.players.some(p=>p.gender==='F');
      if(isLastSlot && !teamHasFemale && !captainIsFemale){
        warn.textContent = '⚠ Last slot — must be a female player (She/Her)';
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

function renderNowBidding(){
  const box = document.getElementById('nowBidding');
  const p = STATE.current_bid_player;
  if(p){
    box.classList.remove('empty');
    box.innerHTML = `<div class="nb-label">Now bidding</div>
      <div class="nb-name">${esc(p.name)}</div>
      <div class="nb-meta">Base ${p.base_price.toLocaleString()}${p.skill ? ' · Skill '+esc(p.skill) : ''}</div>`;
  } else {
    box.classList.add('empty');
    box.innerHTML = `<div class="nb-label">Now bidding</div><div class="nb-name">Select a player to show it here</div>`;
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
  document.getElementById('sumSold').textContent = `${sold}/${STATE.players.length}`;
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
    const captainHtml = `
      <li class="captain-entry">
        <span class="c-badge">C</span>
        <span class="c-name"><input class="captain-entry-input" type="text" value="${esc(team.captain)}" placeholder="Captain name" data-team="${team.id}" data-field="captain"/></span>
        <span class="c-meta">${team.captain_skill ? esc(team.captain_skill)+' · ' : ''}${genderBadge(team.captain_gender||'M')}</span>
      </li>`;
    let rosterHtml = team.players.length === 0
      ? '<li class="placeholder">No players bought yet</li>'
      : team.players.map((p,idx)=>`
          <li><span>${esc(p.name)}${p.skill?` <span style="color:var(--text-dim)">(${esc(p.skill)})</span>`:''} ${genderBadge(p.gender||'M')}</span>
            <span><span class="pcost">${p.cost.toLocaleString()}</span>
            <span class="rm" data-team="${team.id}" data-idx="${idx}" title="Remove">✕</span></span>
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
  if(!el || !num) return;
  num.textContent = n;
  el.className = 'viewer-count' + (n === 0 ? ' none' : '');
}

function applyTheme(){
  const theme = STATE.theme || 'court';
  document.body.classList.toggle('theme-bosch', theme === 'bosch');
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
  if(!playerId){ showMsg('Pick a player from the list.','error'); playerSelect.focus(); return; }
  if(isNaN(cost) || cost<=0){ showMsg('Enter a valid cost greater than 0.','error'); costInput.focus(); return; }
  try{
    STATE = await api('/api/sale', {method:'POST',headers:{'Content-Type':'application/json'},
      body: JSON.stringify({team_id:teamId, player_id:playerId, cost:cost})});
    const soldName = playerSelect.options[playerSelect.selectedIndex]?.textContent.split(' — ')[0] || 'Player';
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
