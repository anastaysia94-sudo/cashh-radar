'use strict';
(()=>{
  const H=window.CRH;
  if(!H)return;

  const PENDING_KEY='cashh-prospect-server-pending-v1';
  const TIMER_IDLE_MS=120000;
  const bridge={authenticated:false,csrf:'',user:null,online:navigator.onLine,queue:new Map(),radar:null,syncing:new Set(),lastSync:null};
  const workTimer={running:false,prospectId:null,activeSeconds:0,lastTick:performance.now(),lastActivityAt:Date.now()};
  bridge.workTimer=workTimer;
  H.serverBridge=bridge;

  const managed=id=>{
    const p=data.find(x=>x.id===id);
    return !!(p&&H.isBusiness(p));
  };
  const getPending=()=>{try{return JSON.parse(localStorage.getItem(PENDING_KEY)||'{}')}catch{return {}}};
  const setPending=value=>localStorage.setItem(PENDING_KEY,JSON.stringify(value));
  const pendingCount=()=>Object.keys(getPending()).length;
  const snakeToPatch=s=>({
    status:s.status,
    verified:!!s.verified,
    email:s.contact_email||'',
    scriptType:s.script_type||undefined,
    subject:s.subject||undefined,
    message:s.message||undefined,
    preparedAt:s.prepared_at||null,
    sentAt:s.sent_at||null,
    lastContactType:s.last_contact_type||undefined,
    repliedAt:s.replied_at||null,
    outcomeStage:s.outcome_stage||undefined,
    outcomeAmount:s.outcome_amount??undefined,
    minutesSpent:Number(s.minutes_spent||0),
    estimatedFulfillmentMinutes:s.estimated_fulfillment_minutes||undefined,
    serverNotes:s.notes||'',
    serverUpdatedAt:s.updated_at
  });
  const statePayload=(id,eventType='sync')=>{
    const p=merge(data.find(x=>x.id===id));
    return {
      status:p.status||'CONTACT READY',
      verified:!!p.verified,
      contact_email:p.email||'',
      script_type:p.scriptType||null,
      subject:p.subject||null,
      message:p.message||null,
      prepared_at:p.preparedAt||null,
      sent_at:p.sentAt||null,
      last_contact_type:p.lastContactType||null,
      replied_at:p.repliedAt||null,
      outcome_stage:p.outcomeStage||null,
      outcome_amount:p.outcomeAmount??null,
      minutes_spent:Number(p.minutesSpent||0),
      estimated_fulfillment_minutes:p.estimatedFulfillmentMinutes||null,
      notes:p.serverNotes||'',
      event_type:eventType
    };
  };
  const inferEvent=patch=>{
    if(patch.outcomeStage||patch.outcomeAmount!==undefined)return 'outcome';
    if(patch.status==='WON / PAID')return 'paid';
    if(patch.status==='REPLIED'||patch.repliedAt)return 'reply';
    if(patch.status==='SENT'||patch.sentAt)return 'sent';
    if(patch.minutesSpent!==undefined)return 'effort';
    if(patch.verified!==undefined)return 'verification';
    return 'sync';
  };
  const api=async(path,options={})=>{
    const headers={...(options.headers||{})};
    if(options.body&&!headers['Content-Type'])headers['Content-Type']='application/json';
    if(bridge.csrf&&/^(POST|PUT|PATCH|DELETE)$/i.test(options.method||'GET'))headers['X-CSRF-Token']=bridge.csrf;
    const response=await fetch(path,{credentials:'same-origin',...options,headers});
    if(response.status===401)throw new Error('AUTH_REQUIRED');
    if(!response.ok){let detail='';try{detail=(await response.json()).detail||''}catch{}throw new Error(detail||`HTTP ${response.status}`)}
    return response.json();
  };

  function ensureBanner(){
    let el=document.getElementById('serverBridgeBanner');
    if(el)return el;
    el=document.createElement('div');el.id='serverBridgeBanner';el.className='serverBridgeBanner';
    document.querySelector('header')?.appendChild(el);
    return el;
  }
  function updateBanner(){
    const el=ensureBanner();if(!el)return;
    if(!bridge.authenticated){
      el.className='serverBridgeBanner local';
      el.innerHTML='<span><b>Local mode</b> · sign in to persist outreach, replies, outcomes, and learning across devices.</span><a href="/">Sign in to Cashh Radar</a>';
      return;
    }
    const pending=pendingCount();
    el.className=`serverBridgeBanner ${bridge.online?'synced':'offline'}`;
    el.innerHTML=`<span><b>${bridge.online?(pending?'Sync pending':'Server sync on'):'Offline'}</b> · ${bridge.online?'Prospect actions feed the same Cashh Radar lifecycle.':'Changes stay local until connection returns.'}</span><span>${pending?`${pending} pending`:(bridge.lastSync?'✓ saved':'connecting')}</span>`;
  }

  const baseSave=save;
  const timers=new Map();
  async function sendState(id,eventType='sync'){
    if(!bridge.authenticated||!managed(id))return;
    if(!navigator.onLine){const p=getPending();p[id]=eventType;setPending(p);updateBanner();return;}
    if(bridge.syncing.has(id)){const p=getPending();p[id]=eventType;setPending(p);return;}
    bridge.syncing.add(id);
    try{
      const result=await api(`/api/prospects/state/${encodeURIComponent(id)}`,{method:'PUT',body:JSON.stringify(statePayload(id,eventType))});
      bridge.queue.set(id,result);
      bridge.lastSync=new Date().toISOString();
      const pending=getPending();delete pending[id];setPending(pending);
      const server=result.state||{};
      baseSave(id,{serverUpdatedAt:server.updated_at,serverRanking:result.ranking,serverPipeline:result.pipeline},false);
    }catch(error){
      const p=getPending();p[id]=eventType;setPending(p);
      if(String(error.message)==='AUTH_REQUIRED'){bridge.authenticated=false;bridge.csrf='';}
    }finally{
      bridge.syncing.delete(id);updateBanner();enhanceFocus();
      const queued=getPending()[id];if(queued&&bridge.authenticated&&navigator.onLine)setTimeout(()=>sendState(id,queued),250);
    }
  }
  function scheduleState(id,eventType){
    clearTimeout(timers.get(id));
    timers.set(id,setTimeout(()=>sendState(id,eventType),450));
  }
  save=(id,patch,rerender=true)=>{
    baseSave(id,patch,rerender);
    if(managed(id))scheduleState(id,inferEvent(patch||{}));
  };

  async function flushPending(){
    if(!bridge.authenticated||!navigator.onLine)return;
    const pending=getPending();
    for(const [id,eventType] of Object.entries(pending))await sendState(id,eventType||'sync');
  }
  async function hydrateServerState(){
    const result=await api('/api/prospects/state');
    const local=loadState();
    for(const s of result.states||[]){
      if(!managed(s.prospect_id))continue;
      const localUpdated=Date.parse(local[s.prospect_id]?.updatedAt||0)||0;
      const serverUpdated=Date.parse(s.updated_at||0)||0;
      if(serverUpdated>=localUpdated)baseSave(s.prospect_id,snakeToPatch(s),false);
      else scheduleState(s.prospect_id,'reconcile');
    }
    render();
  }
  async function loadQueue(){
    try{
      const result=await api('/api/prospects/queue?limit=80');
      for(const item of result.items||[])bridge.queue.set(item.prospect.prospect_id,item);
      enhanceFocus();
    }catch{}
  }
  async function loadRadar(){
    try{bridge.radar=await api('/api/radar/unified?limit=24');if(currentTab==='stats')renderStats();}catch{}
  }
  async function connect(){
    try{
      const me=await fetch('/api/me',{credentials:'same-origin'}).then(r=>r.json());
      bridge.authenticated=!!me.authenticated;
      bridge.user=me.user||null;
      bridge.csrf=me.csrf_token||'';
      updateBanner();
      if(!bridge.authenticated)return;
      await hydrateServerState();
      await Promise.all([loadQueue(),loadRadar()]);
      await flushPending();
    }catch{bridge.online=false;updateBanner();}
  }

  function serverMetric(id){
    const fromApi=bridge.queue.get(id);
    if(fromApi?.ranking)return fromApi;
    const p=merge(data.find(x=>x.id===id));
    if(p?.serverRanking)return{ranking:p.serverRanking,pipeline:p.serverPipeline,prospect:{freshness_status:'source_snapshot'}};
    return null;
  }
  const money=v=>v==null?'—':`$${Number(v).toFixed(Number(v)%1?2:0)}/hr`;
  const dollars=v=>`$${Number(v||0).toFixed(2)}`;
  const pct=v=>v==null?'—':`${Number(v).toFixed(1)}%`;

  function timerMode(){
    if(!workTimer.running)return 'stopped';
    if(document.visibilityState!=='visible')return 'paused-hidden';
    if(currentTab!=='focus'||currentId!==workTimer.prospectId)return 'wrong-prospect';
    if(Date.now()-workTimer.lastActivityAt>TIMER_IDLE_MS)return 'paused-idle';
    return 'running';
  }
  function timerStatusText(){
    const mode=timerMode();
    const seconds=Math.floor(workTimer.activeSeconds);
    const mm=String(Math.floor(seconds/60)).padStart(2,'0');
    const ss=String(seconds%60).padStart(2,'0');
    if(mode==='running')return `${mm}:${ss} active`;
    if(mode==='paused-idle')return `${mm}:${ss} · paused for inactivity`;
    if(mode==='paused-hidden')return `${mm}:${ss} · paused while hidden`;
    return 'Stopped';
  }
  function renderTimerStatus(){
    const card=document.querySelector('.serverLifecycleCard');
    if(!card)return;
    const button=card.querySelector('[data-bridge="timer"]');
    const status=card.querySelector('.workTimerStatus');
    const runningHere=workTimer.running&&workTimer.prospectId===currentId;
    if(button)button.textContent=runningHere?'■ Stop timer':'▶ Start timer';
    if(status)status.textContent=timerStatusText();
  }
  function persistWholeTimerMinutes(){
    if(!workTimer.prospectId)return 0;
    const whole=Math.floor(workTimer.activeSeconds/60);
    if(whole<1)return 0;
    const row=data.find(x=>x.id===workTimer.prospectId);
    if(!row)return 0;
    const p=merge(row);
    workTimer.activeSeconds-=whole*60;
    save(workTimer.prospectId,{minutesSpent:Number(p.minutesSpent||0)+whole},true);
    return whole;
  }
  function stopWorkTimer(){
    if(!workTimer.running)return;
    persistWholeTimerMinutes();
    workTimer.running=false;
    workTimer.prospectId=null;
    workTimer.activeSeconds=0;
    workTimer.lastTick=performance.now();
    renderTimerStatus();
  }
  function toggleWorkTimer(id){
    if(workTimer.running&&workTimer.prospectId===id){stopWorkTimer();return;}
    if(workTimer.running)stopWorkTimer();
    workTimer.running=true;
    workTimer.prospectId=id;
    workTimer.activeSeconds=0;
    workTimer.lastActivityAt=Date.now();
    workTimer.lastTick=performance.now();
    renderTimerStatus();
  }
  function markActivity(){
    workTimer.lastActivityAt=Date.now();
    renderTimerStatus();
  }
  ['pointerdown','pointermove','touchstart','keydown','input'].forEach(type=>{
    document.addEventListener(type,markActivity,{passive:type!=='keydown'&&type!=='input'});
  });
  setInterval(()=>{
    const now=performance.now();
    const elapsed=Math.max(0,Math.min(2,(now-workTimer.lastTick)/1000));
    workTimer.lastTick=now;
    if(workTimer.running&&currentId!==workTimer.prospectId){stopWorkTimer();return;}
    if(timerMode()==='running'){
      workTimer.activeSeconds+=elapsed;
      if(workTimer.activeSeconds>=60)persistWholeTimerMinutes();
    }
    renderTimerStatus();
  },1000);

  function localPerformance(){
    const local=loadState();
    let sent=0,replied=0,paid=0,revenue=0,minutes=0;
    for(const row of data){
      if(!H.isBusiness(row)||!local[row.id])continue;
      const p=merge(row);
      if(p.sentAt)sent+=1;
      if(p.repliedAt)replied+=1;
      if(p.outcomeStage==='paid'){
        paid+=1;
        const amount=Number(p.outcomeAmount);
        if(Number.isFinite(amount)&&amount>=0)revenue+=amount;
      }
      const tracked=Number(p.minutesSpent||0);
      if(Number.isFinite(tracked)&&tracked>0)minutes+=tracked;
    }
    return {
      sent_count:sent,
      replied_count:replied,
      paid_count:paid,
      actual_revenue:revenue,
      tracked_minutes:minutes,
      reply_rate_pct:sent?(replied/sent)*100:null,
      paid_rate_pct:sent?(paid/sent)*100:null,
      realized_portfolio_hourly:minutes?revenue/(minutes/60):null
    };
  }

  function enhanceFocus(){
    const root=document.getElementById('focusView');if(!root||!currentId||!managed(currentId))return;
    const p=merge(data.find(x=>x.id===currentId));
    const metric=serverMetric(currentId);
    let card=root.querySelector('.serverLifecycleCard');
    if(!card){card=document.createElement('section');card.className='step serverLifecycleCard';const divider=root.querySelector('.divider');divider?.insertAdjacentElement('beforebegin',card);}
    if(!card)return;
    const hourly=metric?.ranking?.hourly;
    const pipeline=metric?.pipeline||p.serverPipeline;
    const freshness=metric?.prospect?.freshness_status||'source snapshot';
    const minutes=Number(p.minutesSpent||0);
    const realized=hourly?.kind==='realized';
    card.innerHTML=`
      <div class="stepHead"><span class="num">↗</span><strong>Server lifecycle + value per hour</strong></div>
      <div class="bridgeGrid">
        <div><b>${esc(pipeline?.stage||'not started')}</b><span>Cashh lifecycle</span></div>
        <div><b>${esc(freshness)}</b><span>Evidence freshness</span></div>
        <div><b>${esc(money(hourly?.value))}</b><span>${realized?'Realized':'Modeled offer value'}</span></div>
        <div><b>${minutes} min</b><span>Tracked work time</span></div>
      </div>
      <p class="mini">${esc(hourly?.basis||'The modeled rate uses the proposed offer and time assumptions. It becomes realized only after an actual amount and tracked time are recorded.')}</p>
      <div class="workTimerRow"><button class="btn soft" data-bridge="timer">${workTimer.running&&workTimer.prospectId===p.id?'■ Stop timer':'▶ Start timer'}</button><span class="workTimerStatus">${esc(timerStatusText())}</span></div>
      <p class="mini">The timer only counts after you start it, while this prospect is visible and you have been active in the last 2 minutes. Hidden or inactive time is paused automatically. Partial minutes are never rounded up.</p>
      <div class="bridgeActions">
        <button class="btn soft" data-bridge="add5">+5 min</button>
        <button class="btn soft" data-bridge="add15">+15 min</button>
        <button class="btn navy" data-bridge="reply">↩ Mark replied</button>
        <button class="btn good" data-bridge="paid">$ Mark paid</button>
        <button class="btn soft" data-bridge="refresh">↻ Recheck evidence</button>
      </div>
      <p class="mini bridgeSyncNote">${bridge.authenticated?'Saved actions update the same opportunity, outcomes, and learning used by the broader Cashh Radar.':'Sign in to Cashh Radar to turn local actions into persistent lifecycle evidence.'}</p>`;
    card.querySelector('[data-bridge="timer"]')?.addEventListener('click',()=>toggleWorkTimer(p.id));
    card.querySelector('[data-bridge="add5"]')?.addEventListener('click',()=>save(p.id,{minutesSpent:minutes+5},true));
    card.querySelector('[data-bridge="add15"]')?.addEventListener('click',()=>save(p.id,{minutesSpent:minutes+15},true));
    card.querySelector('[data-bridge="reply"]')?.addEventListener('click',()=>{
      const notes=prompt('Optional: what did the prospect say?','')||'';
      save(p.id,{status:'REPLIED',repliedAt:new Date().toISOString(),serverNotes:notes},true);
      toast('Reply recorded in the unified lifecycle.');
    });
    card.querySelector('[data-bridge="paid"]')?.addEventListener('click',()=>{
      const raw=prompt('Actual amount received',String(p.outcomeAmount??p.offerPrice??100));
      if(raw===null)return;const amount=Number(raw);if(!Number.isFinite(amount)||amount<0)return toast('Enter a valid amount received.');
      const notes=prompt('Optional payment/outcome note','')||p.serverNotes||'';
      save(p.id,{status:'WON / PAID',outcomeStage:'paid',outcomeAmount:amount,serverNotes:notes},true);
      toast('Paid outcome recorded. Cashh Radar can learn from it now.');
    });
    card.querySelector('[data-bridge="refresh"]')?.addEventListener('click',async()=>{
      if(!bridge.authenticated)return toast('Sign in first so the evidence refresh can be recorded.');
      try{
        const r=await api(`/api/prospects/${encodeURIComponent(p.id)}/refresh`,{method:'POST'});
        toast(`Evidence check: ${r.freshness_status}${r.http_status?` (HTTP ${r.http_status})`:''}`);
        await loadQueue();renderFocus();
      }catch(e){toast(`Evidence refresh failed: ${e.message}`);}
    });
    renderTimerStatus();
  }

  const focusObserver=new MutationObserver(enhanceFocus);
  document.getElementById('focusView')&&focusObserver.observe(document.getElementById('focusView'),{childList:true,subtree:true});

  const baseRenderStats=renderStats;
  renderStats=()=>{
    baseRenderStats();
    const root=document.getElementById('statsView');if(!root)return;
    const radar=bridge.radar;
    const actual=bridge.authenticated?localPerformance():null;
    bridge.performance=actual;
    const performance=document.createElement('div');performance.className='panel actualPerformancePanel';performance.style.marginTop='10px';
    performance.innerHTML=bridge.authenticated?`<h2 style="margin-top:0;color:var(--navy)">Actual prospect performance</h2>
      <p class="mini">Only synchronized actions and explicitly recorded outcomes count here. Proposed $100 offers are not revenue.</p>
      <div class="performanceGrid">
        <div><b>${actual.sent_count}</b><span>Sent</span></div>
        <div><b>${actual.replied_count}</b><span>Replies · ${pct(actual.reply_rate_pct)}</span></div>
        <div><b>${actual.paid_count}</b><span>Paid · ${pct(actual.paid_rate_pct)}</span></div>
        <div><b>${dollars(actual.actual_revenue)}</b><span>Actual revenue</span></div>
        <div><b>${actual.tracked_minutes} min</b><span>Tracked prospect work</span></div>
        <div><b>${money(actual.realized_portfolio_hourly)}</b><span>Portfolio realized yield</span></div>
      </div>
      <p class="mini">Portfolio realized yield divides actual paid dollars by all tracked prospect work, including work on prospects that did not pay.</p>`:
      `<h2 style="margin-top:0;color:var(--navy)">Actual prospect performance</h2><p class="mini">Sign in and sync with Cashh Radar to view real sent, reply, paid, revenue, time, and realized hourly performance. Local-mode placeholders are intentionally not treated as results.</p><a class="btn primary" href="/" style="display:block;text-align:center;margin-top:10px">Sign in to Cashh Radar</a>`;
    root.appendChild(performance);

    const others=(radar?.items||[]).filter(x=>x.source_family!=='client_prospect').slice(0,6);
    const server=document.createElement('div');server.className='panel unifiedRadarPanel';server.style.marginTop='10px';
    server.innerHTML=`<h2 style="margin-top:0;color:var(--navy)">Broader Cashh Radar</h2>
      <p class="mini">This queue is now one lane inside the same opportunity system. Other jobs, grants, contracts, and money paths remain visible here instead of vanishing behind sales outreach.</p>
      <div class="radarSummary"><b>${radar?radar.client_prospects:'—'}</b><span>client prospects</span><b>${radar?radar.other_money_opportunities:'—'}</b><span>other opportunities</span></div>
      <div class="radarMiniList">${others.length?others.map(x=>`<article><div><strong>${esc(x.title)}</strong><span>${esc(x.category)} · match ${esc(x.match)} · ${esc(money(x.hourly?.value))}</span></div>${x.source_url?`<a href="${esc(x.source_url)}" target="_blank" rel="noopener">Source</a>`:''}</article>`).join(''):'<p class="mini">Sign in and let the unified Radar load to see non-prospect opportunities here.</p>'}</div>
      <a class="btn primary" href="/" style="display:block;text-align:center;margin-top:10px">Open full Cashh Radar</a>`;
    root.appendChild(server);
  };

  window.addEventListener('online',()=>{bridge.online=true;updateBanner();flushPending();loadQueue();loadRadar();});
  window.addEventListener('offline',()=>{bridge.online=false;updateBanner();});
  document.addEventListener('visibilitychange',()=>{
    workTimer.lastTick=performance.now();
    renderTimerStatus();
    if(document.visibilityState==='visible'&&bridge.authenticated){flushPending();loadQueue();}
  });

  const style=document.createElement('style');style.textContent=`
    .serverBridgeBanner{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:7px 12px;font-size:12px;background:#e8fff8;color:#0f5132;border-top:1px solid rgba(0,0,0,.07)}
    .serverBridgeBanner.local{background:#fff4df;color:#704800}.serverBridgeBanner.offline{background:#f2f2f2;color:#555}.serverBridgeBanner a{font-weight:800;color:inherit}
    .bridgeGrid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:10px 0}.bridgeGrid>div{background:var(--soft,#f4f7fa);border-radius:10px;padding:9px}.bridgeGrid b,.bridgeGrid span{display:block}.bridgeGrid span{font-size:11px;opacity:.72;margin-top:3px}
    .workTimerRow{display:flex;gap:10px;align-items:center;margin:10px 0}.workTimerRow .btn{flex:0 0 auto}.workTimerStatus{font-size:12px;font-weight:800;color:var(--navy)}
    .bridgeActions{display:grid;grid-template-columns:1fr 1fr;gap:7px}.bridgeActions .btn:last-child{grid-column:1/-1}.radarSummary{display:grid;grid-template-columns:auto 1fr auto 1fr;gap:6px 10px;align-items:baseline;margin:8px 0 12px}.radarSummary b{font-size:22px}.radarSummary span{font-size:12px;opacity:.72}
    .performanceGrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:10px 0}.performanceGrid>div{background:var(--soft,#f4f7fa);padding:9px;border-radius:10px}.performanceGrid b,.performanceGrid span{display:block}.performanceGrid b{font-size:18px}.performanceGrid span{font-size:11px;opacity:.72;margin-top:3px}
    .radarMiniList article{display:flex;justify-content:space-between;gap:8px;padding:9px 0;border-top:1px solid rgba(0,0,0,.08)}.radarMiniList strong,.radarMiniList span{display:block}.radarMiniList span{font-size:11px;opacity:.72;margin-top:2px}.radarMiniList a{font-size:12px;font-weight:800;white-space:nowrap}
  `;document.head.appendChild(style);

  updateBanner();connect();
})();
