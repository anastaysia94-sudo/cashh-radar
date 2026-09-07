(() => {
  const $ = s => document.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const money = n => n == null || n === '' ? '—' : new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2}).format(Number(n));
  const state = {csrf:'', authenticated:false, pipeline:new Map(), learning:null, currentId:null};

  function injectStyles(){
    if($('#cashhLoopStyles')) return;
    const s=document.createElement('style');s.id='cashhLoopStyles';s.textContent=`
      .loop-overview{max-width:1500px;margin:18px auto;border:1px solid rgba(110,191,255,.16);border-radius:20px;padding:18px;background:linear-gradient(135deg,rgba(55,229,255,.08),rgba(152,255,101,.04));box-shadow:0 18px 50px rgba(0,0,0,.18)}
      .loop-overview-head,.loop-stage-head{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap}.loop-overview h3,.loop-panel h3{margin:4px 0}.loop-overview p,.loop-panel p{color:#9eb5c8;line-height:1.55}.loop-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin-top:12px}.loop-kpi{border:1px solid #1e3857;background:#071725;border-radius:12px;padding:11px}.loop-kpi span{display:block;color:#7690a8;font-size:10px;text-transform:uppercase;letter-spacing:.08em}.loop-kpi b{display:block;margin-top:5px}.loop-panel{margin:18px 0;border:1px solid #245071;border-radius:17px;padding:16px;background:linear-gradient(180deg,#0b2136,#081827)}
      .loop-stage{display:inline-flex;align-items:center;gap:6px;border:1px solid #2d607f;border-radius:999px;padding:6px 9px;color:#a9ddf3;font-size:11px;font-weight:850;text-transform:uppercase;letter-spacing:.06em}.loop-stage:before{content:'';width:7px;height:7px;border-radius:50%;background:#37e5ff;box-shadow:0 0 12px #37e5ff}.loop-score{font-size:32px;font-weight:950}.loop-score small{font-size:10px;color:#8ca5ba;display:block}.loop-reasons{display:grid;gap:7px;padding:0;margin:10px 0;list-style:none}.loop-reasons li{border-left:2px solid #2a6688;padding:7px 10px;color:#b4c9d8;font-size:12px}.loop-action{border:1px solid #274b64;border-radius:13px;padding:13px;background:#071725;margin:12px 0}.loop-copy{white-space:pre-wrap;background:#06131f;border:1px solid #1d3d57;border-radius:11px;padding:12px;color:#e6f8ff;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;line-height:1.5}.loop-toolbar{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}.loop-form{display:grid;gap:9px;margin-top:12px}.loop-form label{display:grid;gap:5px;color:#91a7bd;font-size:12px}.loop-form input,.loop-form select,.loop-form textarea{width:100%;border:1px solid #1e3857;background:#071725;color:#ecf8ff;border-radius:10px;padding:10px}.loop-form textarea{min-height:76px;resize:vertical}.loop-timeline{display:grid;gap:7px;margin-top:12px}.loop-event{border-left:2px solid #214c69;padding:7px 10px;font-size:12px;color:#a9bfd1}.loop-event b{color:#fff}.loop-card-stage{margin-left:6px}.loop-good{color:#98ff65}.loop-warn{color:#ffc85c}.loop-muted{color:#91a7bd}.loop-empty{padding:12px;border:1px dashed #294862;border-radius:12px;color:#91a7bd}.loop-best{display:flex;gap:14px;align-items:flex-start}.loop-best-main{flex:1}.loop-best-score{min-width:74px;text-align:center}.loop-best-score strong{font-size:30px}.loop-best-score small{display:block;color:#8099af;font-size:10px}.loop-mini{font-size:11px;color:#86a0b7}.loop-hidden-legacy{display:none!important}
      @media(max-width:760px){.loop-kpis{grid-template-columns:1fr 1fr}.loop-best{display:block}.loop-best-score{text-align:left;margin-top:8px}}
    `;document.head.appendChild(s);
  }

  async function api(path, opts={}){
    const method=(opts.method||'GET').toUpperCase();
    const headers={'Content-Type':'application/json',...(opts.headers||{})};
    if(['POST','PUT','PATCH','DELETE'].includes(method)){
      if(!state.csrf) await refreshSession();
      if(state.csrf) headers['X-CSRF-Token']=state.csrf;
    }
    const res=await fetch(path,{credentials:'same-origin',...opts,headers});
    let data={};try{data=await res.json()}catch{data={detail:await res.text().catch(()=>res.statusText)}}
    if(!res.ok){const err=new Error(data.detail||data.message||`Request failed (${res.status})`);err.status=res.status;throw err}
    return data;
  }

  async function refreshSession(){
    try{const d=await fetch('/api/me',{credentials:'same-origin'}).then(r=>r.json());state.authenticated=!!d.authenticated;state.csrf=d.csrf_token||'';return d}catch{return {authenticated:false}}
  }

  function requireAccount(){
    const btn=$('#accountBtn');if(btn) btn.click();
  }

  function openModal(html){
    const modal=$('#modal'), content=$('#modalContent');
    if(!modal||!content) return;
    content.innerHTML=html;modal.classList.remove('hidden');
  }

  function stageLabel(x){return String(x||'discovered').replaceAll('_',' ')}

  function pipelineChip(id){
    const p=state.pipeline.get(id);return p?`<span class="badge loop-card-stage">${esc(stageLabel(p.stage))}</span>`:'';
  }

  function decorateCards(){
    document.querySelectorAll('[data-detail]').forEach(btn=>{
      const id=btn.dataset.detail;if(!id) return;const card=btn.closest('.opportunity-card,.module-row');if(!card) return;
      const kicker=card.querySelector('.opp-kicker');if(kicker&&!kicker.querySelector('.loop-card-stage')) kicker.insertAdjacentHTML('beforeend',pipelineChip(id));
    });
  }

  function renderOverview(){
    let box=$('#cashhLoopOverview');
    if(!box){box=document.createElement('section');box.id='cashhLoopOverview';box.className='loop-overview';const workspace=$('.workspace');if(workspace) workspace.parentNode.insertBefore(box,workspace)}
    if(!box) return;
    if(!state.authenticated){box.innerHTML=`<div class="loop-overview-head"><div><span class="eyebrow">ONE CANONICAL LOOP</span><h3>Find → verify → score → act → track → learn</h3><p>Sign in to connect opportunity discovery to actions, replies, outcomes, and learning.</p></div><button class="primary-btn" data-loop-signin>Sign in to activate</button></div>`;return}
    const items=[...state.pipeline.values()].sort((a,b)=>(b.final_score||0)-(a.final_score||0));const best=items[0];
    const groups=state.learning?.groups||[];const outcomes=items.filter(x=>x.latest_outcome_stage).length;const responses=items.filter(x=>x.last_response&&Object.keys(x.last_response).length).length;
    box.innerHTML=`<div class="loop-overview-head"><div><span class="eyebrow">CANONICAL CASHH RADAR LOOP</span><h3>${best?'Best active signal':'Your execution loop is ready'}</h3><p>${best?`${esc(best.title)} is currently the strongest opportunity that has entered your loop.`:'Open any opportunity and run Radar once. From then on, one record carries the full lifecycle.'}</p></div>${best?`<button class="primary-btn" data-loop-open="${esc(best.opportunity_id)}">Open best opportunity</button>`:''}</div>
      ${best?`<div class="loop-best"><div class="loop-best-main"><div class="loop-toolbar"><span class="loop-stage">${esc(stageLabel(best.stage))}</span><span class="loop-mini">${esc(best.verification_status||'unverified')} evidence • learned ${Number(best.learned_adjustment||0)>=0?'+':''}${esc(best.learned_adjustment||0)}</span></div><p>${esc(best.explanation?.summary||'')}</p></div><div class="loop-best-score"><strong>${esc(best.final_score??'—')}</strong><small>CANONICAL SCORE</small></div></div>`:''}
      <div class="loop-kpis"><div class="loop-kpi"><span>In loop</span><b>${items.length}</b></div><div class="loop-kpi"><span>Responses</span><b>${responses}</b></div><div class="loop-kpi"><span>Outcomes</span><b>${outcomes}</b></div><div class="loop-kpi"><span>Learning groups</span><b>${groups.length}</b></div></div>`;
  }

  async function refreshPipeline(){
    await refreshSession();
    if(!state.authenticated){state.pipeline.clear();renderOverview();return}
    try{
      const [p,l]=await Promise.all([api('/api/loop'),api('/api/loop-learning')]);
      state.pipeline=new Map((p.pipeline||[]).map(x=>[x.opportunity_id,x]));state.learning=l;renderOverview();decorateCards();
    }catch{renderOverview()}
  }

  function actionHtml(a){
    if(!a||!Object.keys(a).length) return '<div class="loop-empty">No generated action yet.</div>';
    const steps=(a.next_steps||[]).map(s=>`<li>${esc(s)}</li>`).join('');
    return `<div class="loop-action"><b>Specific next action</b><p>${esc(a.primary_action||'')}</p>${a.source_url?`<a class="source-link" href="${esc(a.source_url)}" target="_blank" rel="noopener">Open canonical source ↗</a>`:''}${a.content?`<div class="loop-copy" data-loop-copy-text>${esc(a.content)}</div><button class="mini-btn" data-loop-copy>Copy draft</button>`:''}${steps?`<ul class="loop-reasons">${steps}</ul>`:''}</div>`;
  }

  function renderLoopPanel(id, d=null){
    const host=$('#cashhLoopPanel');if(!host||host.dataset.opportunityId!==id) return;
    const p=d?.pipeline||state.pipeline.get(id);const run=d&&d.score!=null?d:null;
    if(!p&&!run){host.innerHTML=`<div class="loop-stage-head"><div><span class="eyebrow">ONE LOOP</span><h3>Turn this signal into a tracked result</h3></div><span class="loop-stage">not started</span></div><p>Radar will verify, score, explain, generate the specific next action, then keep the reply and outcome on this same record.</p><button class="primary-btn" data-loop-run="${esc(id)}">Run Cashh Radar loop</button>`;return}
    const stage=run?.stage||p?.stage;const score=run?.score??p?.final_score;const verify=run?.verification||{status:p?.verification_status,evidence_score:p?.evidence_score};const explanation=run?.explanation||p?.explanation||{};const action=run?.action||p?.action||{};
    host.innerHTML=`<div class="loop-stage-head"><div><span class="eyebrow">CANONICAL EXECUTION RECORD</span><h3>One opportunity. One lifecycle.</h3></div><div class="loop-score">${esc(score??'—')}<small>CASHH SCORE</small></div></div><div class="loop-toolbar"><span class="loop-stage">${esc(stageLabel(stage))}</span><span class="badge">${esc(verify?.status||'unverified')} • evidence ${esc(verify?.evidence_score??'—')}/100</span>${Number(run?.learned_adjustment??p?.learned_adjustment??0)!==0?`<span class="badge green">learning ${Number(run?.learned_adjustment??p?.learned_adjustment)>0?'+':''}${esc(run?.learned_adjustment??p?.learned_adjustment)}</span>`:''}</div><p><b>${esc(explanation.summary||'')}</b></p><ul class="loop-reasons">${(explanation.reasons||[]).map(x=>`<li>${esc(x)}</li>`).join('')}</ul>${actionHtml(action)}<div class="loop-toolbar"><button class="primary-btn" data-loop-run="${esc(id)}">Refresh analysis</button><button class="ghost-btn" data-loop-actioned="${esc(id)}">I sent / applied</button><button class="ghost-btn" data-loop-response="${esc(id)}">Record response</button><button class="ghost-btn" data-loop-outcome="${esc(id)}">Record outcome</button><button class="ghost-btn" data-loop-history="${esc(id)}">Timeline</button></div><p class="loop-mini">Generating a draft does not count as contacting anyone. Cashh Radar advances only when you explicitly record what actually happened.</p>`;
  }

  async function loadLoopDetail(id){
    const host=$('#cashhLoopPanel');if(!host) return;
    try{const d=await api(`/api/loop/${encodeURIComponent(id)}`);state.pipeline.set(id,d.pipeline);renderLoopPanel(id,d)}catch(e){if(e.status===404)renderLoopPanel(id);else host.innerHTML=`<div class="loop-empty">${esc(e.message)}</div>`}
  }

  function attachDrawerPanel(){
    const detail=$('#detailContent');if(!detail) return;
    const source=detail.querySelector('[data-log-outcome],[data-make-outreach],[data-save]');if(!source) return;
    const id=source.dataset.logOutcome||source.dataset.makeOutreach||source.dataset.save;if(!id) return;
    state.currentId=id;
    detail.querySelectorAll('[data-make-outreach],[data-log-outcome]').forEach(x=>x.classList.add('loop-hidden-legacy'));
    let panel=$('#cashhLoopPanel');if(!panel){panel=document.createElement('section');panel.id='cashhLoopPanel';panel.className='loop-panel';detail.appendChild(panel)}
    panel.dataset.opportunityId=id;panel.innerHTML='<div class="loop-empty">Loading canonical execution record…</div>';
    refreshSession().then(()=>{if(!state.authenticated){panel.innerHTML=`<div class="loop-empty">Sign in to activate the unified action → response → outcome → learning loop. <button class="mini-btn" data-loop-signin>Sign in</button></div>`;return}loadLoopDetail(id)});
  }

  async function runLoop(id){
    if(!state.authenticated){requireAccount();return}
    const host=$('#cashhLoopPanel');if(host)host.innerHTML='<div class="loop-empty">Verifying, scoring, explaining, and generating the next action…</div>';
    try{const d=await api('/api/loop/run',{method:'POST',body:JSON.stringify({opportunity_id:id,asset_type:'auto',generate_action:true})});renderLoopPanel(id,d);await refreshPipeline()}catch(e){if(host)host.innerHTML=`<div class="loop-empty">${esc(e.message)}</div>`}
  }

  function actionedForm(id){openModal(`<span class="eyebrow">ACTION CONFIRMATION</span><h2 id="modalTitle">Record what you actually did</h2><p>This is the point where Cashh Radar moves from generated advice to external evidence.</p><form id="loopActionedForm" class="loop-form"><label>Channel<select name="channel"><option value="source">Official application/source</option><option value="email">Email</option><option value="dm">DM / message</option><option value="marketplace">Marketplace</option><option value="other">Other</option></select></label><label>Notes<textarea name="notes" placeholder="What was sent/submitted?"></textarea></label><label>Reference or confirmation URL (optional)<input name="external_reference"></label><button class="primary-btn">Record action</button></form><div id="loopFormMsg"></div>`);$('#loopActionedForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);try{await api(`/api/loop/${encodeURIComponent(id)}/actioned`,{method:'POST',body:JSON.stringify(Object.fromEntries(f))});$('#loopFormMsg').innerHTML='<div class="notice success">Action recorded. The next evidence to capture is the response.</div>';await refreshPipeline();setTimeout(()=>{const close=$('#closeModal');if(close)close.click();loadLoopDetail(id)},500)}catch(err){$('#loopFormMsg').innerHTML=`<div class="notice danger">${esc(err.message)}</div>`}})}

  function responseForm(id){openModal(`<span class="eyebrow">RESPONSE TRACKER</span><h2 id="modalTitle">What came back?</h2><form id="loopResponseForm" class="loop-form"><label>Response<select name="response_type"><option value="reply">Reply</option><option value="question">Question</option><option value="interview">Interview / meeting</option><option value="accepted">Accepted / won</option><option value="rejected">Rejected / lost</option><option value="no_response">No response yet</option></select></label><label>Notes<textarea name="notes" placeholder="What did they say? Keep it factual."></textarea></label><button class="primary-btn">Record response</button></form><div id="loopFormMsg"></div>`);$('#loopResponseForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);try{await api(`/api/loop/${encodeURIComponent(id)}/response`,{method:'POST',body:JSON.stringify(Object.fromEntries(f))});$('#loopFormMsg').innerHTML='<div class="notice success">Response recorded.</div>';await refreshPipeline();setTimeout(()=>{const close=$('#closeModal');if(close)close.click();loadLoopDetail(id)},500)}catch(err){$('#loopFormMsg').innerHTML=`<div class="notice danger">${esc(err.message)}</div>`}})}

  function outcomeForm(id){openModal(`<span class="eyebrow">OUTCOME → LEARNING</span><h2 id="modalTitle">Record the result</h2><p>The latest outcome becomes bounded evidence for sufficiently similar future opportunities.</p><form id="loopOutcomeForm" class="loop-form"><label>Outcome<select name="stage"><option value="started">Started</option><option value="applied">Applied</option><option value="contacted">Contacted</option><option value="replied">Replied</option><option value="interview">Interview</option><option value="negotiating">Negotiating</option><option value="won">Won</option><option value="paid">Paid</option><option value="fulfilled">Fulfilled</option><option value="follow_up">Follow-up</option><option value="lost">Lost</option></select></label><label>Amount actually received (optional)<input name="amount" type="number" min="0" step="0.01"></label><label>Notes<textarea name="notes"></textarea></label><button class="primary-btn">Record outcome & learn</button></form><div id="loopFormMsg"></div>`);$('#loopOutcomeForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);const payload={stage:f.get('stage'),notes:f.get('notes'),amount:f.get('amount')?Number(f.get('amount')):null};try{const d=await api(`/api/loop/${encodeURIComponent(id)}/outcome`,{method:'POST',body:JSON.stringify(payload)});$('#loopFormMsg').innerHTML=`<div class="notice success">Outcome recorded. ${esc(d.effect||'')}</div><div class="loop-kpis"><div class="loop-kpi"><span>New score</span><b>${esc(d.score)}</b></div><div class="loop-kpi"><span>Relevant history</span><b>${esc(d.learning?.relevant_samples??0)}</b></div><div class="loop-kpi"><span>Adjustment</span><b>${Number(d.learning?.adjustment||0)>=0?'+':''}${esc(d.learning?.adjustment||0)}</b></div><div class="loop-kpi"><span>Amount</span><b>${money(payload.amount)}</b></div></div>`;await refreshPipeline();setTimeout(()=>loadLoopDetail(id),300)}catch(err){$('#loopFormMsg').innerHTML=`<div class="notice danger">${esc(err.message)}</div>`}})}

  async function historyModal(id){
    try{const d=await api(`/api/loop/${encodeURIComponent(id)}`);openModal(`<span class="eyebrow">EVIDENCE TIMELINE</span><h2 id="modalTitle">Opportunity lifecycle</h2><div class="loop-toolbar"><span class="loop-stage">${esc(stageLabel(d.pipeline.stage))}</span><span class="badge">score ${esc(d.pipeline.final_score??'—')}</span></div><div class="loop-timeline">${(d.events||[]).map(x=>`<div class="loop-event"><b>${esc(x.event_type.replaceAll('_',' '))}</b> → ${esc(stageLabel(x.stage))}<br><span>${esc(new Date(x.created_at).toLocaleString())}</span></div>`).join('')||'<div class="loop-empty">No events yet.</div>'}</div>`)}catch(e){openModal(`<h2 id="modalTitle">Timeline unavailable</h2><p>${esc(e.message)}</p>`)}
  }

  document.addEventListener('click',e=>{
    const t=e.target.closest('[data-loop-run],[data-loop-actioned],[data-loop-response],[data-loop-outcome],[data-loop-history],[data-loop-copy],[data-loop-signin],[data-loop-open]');if(!t)return;
    if(t.dataset.loopSignin!==undefined){requireAccount();return}
    if(t.dataset.loopOpen){const btn=document.querySelector(`[data-detail="${CSS.escape(t.dataset.loopOpen)}"]`);if(btn)btn.click();return}
    if(t.dataset.loopRun)runLoop(t.dataset.loopRun);
    else if(t.dataset.loopActioned)actionedForm(t.dataset.loopActioned);
    else if(t.dataset.loopResponse)responseForm(t.dataset.loopResponse);
    else if(t.dataset.loopOutcome)outcomeForm(t.dataset.loopOutcome);
    else if(t.dataset.loopHistory)historyModal(t.dataset.loopHistory);
    else if(t.dataset.loopCopy!==undefined){const text=$('[data-loop-copy-text]')?.textContent||'';navigator.clipboard?.writeText(text).then(()=>{t.textContent='Copied'})}
  });

  function boot(){
    injectStyles();refreshPipeline();
    const detail=$('#detailContent');if(detail)new MutationObserver(()=>attachDrawerPanel()).observe(detail,{childList:true,subtree:false});
    const list=$('#opportunityList');if(list)new MutationObserver(()=>decorateCards()).observe(list,{childList:true,subtree:true});
    setInterval(()=>{if(state.authenticated)refreshPipeline()},60000);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
