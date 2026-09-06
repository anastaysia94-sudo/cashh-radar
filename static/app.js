(() => {
  const $ = s => document.querySelector(s);
  const $$ = s => [...document.querySelectorAll(s)];
  const list = $('#opportunityList');
  const filters = $('#filters');
  const drawer = $('#detailDrawer');
  const backdrop = $('#drawerBackdrop');
  const modal = $('#modal');
  const modalContent = $('#modalContent');
  const state = {records:[], view:'home', sort:'match', work:'all', cost:'all', exp:'all', trust:'all', saved:new Set(), me:null, csrf:'', sourceStatus:null};

  const esc = s => String(s ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const money = n => n == null ? 'Not supplied' : new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(Number(n));
  const dateLabel = s => { if(!s) return 'Not supplied'; const d=new Date(s); return Number.isNaN(d.getTime())?String(s):d.toLocaleDateString(); };
  const days = n => n == null ? 'Unknown' : Number(n)<=1?'~1 day':`~${n} days`;
  const incomeText = o => o.income_min==null&&o.income_max==null ? 'Not supplied' : `${money(o.income_min)}${o.income_max!=null&&o.income_max!==o.income_min?'–'+money(o.income_max):''}${o.income_period?'/'+o.income_period:''}${o.income_is_estimate?' est.':''}`;
  const verifyLabel = o => (o.verification?.status||'unverified').replaceAll('_',' ');

  async function api(path, opts={}){
    const headers = {'Content-Type':'application/json', ...(opts.headers||{})};
    const method=(opts.method||'GET').toUpperCase();
    if(state.csrf && ['POST','PUT','PATCH','DELETE'].includes(method)) headers['X-CSRF-Token']=state.csrf;
    const res=await fetch(path,{credentials:'same-origin',...opts,headers});
    let data={}; try{data=await res.json()}catch{data={detail:await res.text().catch(()=>res.statusText)}}
    if(!res.ok) throw new Error(data.detail||data.message||`Request failed (${res.status})`);
    return data;
  }
  function notice(msg, kind=''){ return `<div class="notice ${kind}">${esc(msg)}</div>`; }
  function toast(msg){
    let t=document.getElementById('cashhToast');
    if(!t){t=document.createElement('div');t.id='cashhToast';t.style='position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:100;background:#10243a;border:1px solid #2c5371;color:#fff;padding:11px 15px;border-radius:12px;box-shadow:0 14px 40px rgba(0,0,0,.35);max-width:90vw';document.body.appendChild(t)}
    t.textContent=msg;t.hidden=false;clearTimeout(t._timer);t._timer=setTimeout(()=>t.hidden=true,2600);
  }
  async function track(name, metadata={}){ try{ await api('/api/events',{method:'POST',body:JSON.stringify({event_name:name,metadata})}); }catch{} }

  async function loadMe(){
    const d=await api('/api/me'); state.me=d.authenticated?d.user:null; state.csrf=d.csrf_token||'';
    $('#accountBtn').textContent=state.me?state.me.email.split('@')[0]:'Sign in';
    $('#adminNav').classList.toggle('hidden', !(state.me&&state.me.role==='admin'));
    $('#watchCount').textContent=d.watch_count||0; $('#alertCount').textContent=d.unseen_alerts||0;
    if(state.me){
      const w=await api('/api/watchlist').catch(()=>({opportunities:[]})); state.saved=new Set((w.opportunities||[]).map(o=>o.id));
    } else state.saved.clear();
  }

  async function loadRecords(){
    const d=await api('/api/opportunities?include_expired=false'); state.records=d.opportunities||[]; render();
  }

  function filtered(){
    let data=[...state.records];
    if(state.view==='fast') data=data.filter(o=>o.speed_days!=null&&Number(o.speed_days)<=14);
    if(state.view==='remote') data=data.filter(o=>o.mode==='remote');
    if(state.view==='business') data=data.filter(o=>['Microbusiness','Digital Business','Freelance Service','Freelance / Research'].includes(o.category));
    if(state.work!=='all') data=data.filter(o=>o.mode===state.work);
    if(state.cost!=='all') data=data.filter(o=>Number(o.startup_cost||0)<=Number(state.cost));
    if(state.exp!=='all') data=data.filter(o=>o.experience===state.exp);
    if(state.trust!=='all'){
      if(state.trust==='verified') data=data.filter(o=>o.verification?.status==='verified');
      else data=data.filter(o=>o.trust===state.trust);
    }
    data.sort((a,b)=>{
      if(state.sort==='speed') return (a.speed_days??99999)-(b.speed_days??99999);
      if(state.sort==='income') return Number(b.income_max??-1)-Number(a.income_max??-1);
      if(state.sort==='cost') return Number(a.startup_cost||0)-Number(b.startup_cost||0);
      if(state.sort==='durability') return Number(b.durability||0)-Number(a.durability||0);
      return Number(b.match||0)-Number(a.match||0);
    });
    return data;
  }

  function card(o){
    const saved=state.saved.has(o.id); const v=o.verification||{};
    const link=o.source_url?`<a class="source-link" href="${esc(o.source_url)}" target="_blank" rel="noopener noreferrer">Open source ↗</a>`:'';
    return `<article class="opportunity-card ${o.trust==='source'?'source-card':''}">
      <div class="opp-top"><div><div class="opp-kicker"><span class="badge cyan">${esc(o.category)}</span><span class="status-chip ${esc(v.status)}">${esc(verifyLabel(o))}</span>${(o.tags||[]).slice(0,2).map(t=>`<span class="badge">${esc(t)}</span>`).join('')}</div>
      <h3 class="opp-title">${esc(o.title)}</h3><div class="opp-sub">${esc(o.organization||o.source_name||'')} ${link}</div></div><div class="score-box"><strong>${esc(o.match)}</strong><small>MATCH</small></div></div>
      <div class="opp-metrics"><div class="metric"><span>Time to income</span><b>${days(o.speed_days)}</b></div><div class="metric"><span>${esc(o.income_label||'Income')}</span><b>${esc(incomeText(o))}</b></div><div class="metric"><span>Startup</span><b>${money(o.startup_cost||0)}</b></div><div class="metric"><span>Freshness</span><b>${dateLabel(o.last_seen)}</b></div><div class="metric"><span>Deadline</span><b>${dateLabel(o.closes_at)}</b></div></div>
      <div class="opp-actions"><div class="why"><b>Why it may fit:</b> ${esc(o.why||'')}</div><div class="opp-buttons"><button class="mini-btn ${saved?'saved':''}" data-save="${esc(o.id)}">${saved?'Saved':'Save'}</button><button class="mini-btn" data-detail="${esc(o.id)}">Open intelligence</button></div></div>
    </article>`;
  }

  function render(){
    if(state.view==='sources'){renderSources();return}
    filters.classList.toggle('hidden', state.view==='compare');
    const data=filtered();
    $('#statCount').textContent=`${state.records.filter(o=>o.trust!=='demo').length} sourced + ${state.records.filter(o=>o.trust==='demo').length} models`;
    $('#resultsSummary').textContent=`${data.length} result${data.length===1?'':'s'} • evidence states are explicit • earnings are never guaranteed`;
    if(state.view==='compare') return renderCompare(data);
    list.innerHTML=data.length?data.map(card).join(''):`<div class="opportunity-card"><h3>No matching records</h3><p class="opp-sub">Clear filters or choose another view.</p></div>`;
  }

  function renderCompare(data){
    const picks=data.slice(0,3); if(!picks.length){list.innerHTML=notice('No opportunities available to compare.');return}
    list.innerHTML=`<div class="module-stack">${picks.map((o,i)=>`<div class="module-row"><div class="opp-kicker"><span class="badge cyan">#${i+1}</span><span class="status-chip ${esc(o.verification.status)}">${esc(verifyLabel(o))}</span></div><h3>${esc(o.title)}</h3><p>${esc(o.organization)}</p><div class="detail-grid"><div class="detail-card"><span>Match</span><b>${o.match}/100</b></div><div class="detail-card"><span>Income</span><b>${esc(incomeText(o))}</b></div><div class="detail-card"><span>Startup</span><b>${money(o.startup_cost)}</b></div><div class="detail-card"><span>Timing</span><b>${days(o.speed_days)}</b></div></div><p><b>Risk:</b> ${esc(o.risks)}</p><button class="mini-btn" data-detail="${esc(o.id)}">Open intelligence</button></div>`).join('')}</div>`;
  }

  function openDetail(id){
    const o=state.records.find(x=>x.id===id); if(!o)return; const saved=state.saved.has(id); const v=o.verification||{};
    const evidence=`<b>Status:</b> ${esc(verifyLabel(o))}. <b>Evidence score:</b> ${esc(v.evidence_score)}/100. <b>Source:</b> ${esc(o.source_name)}. <b>Observed:</b> ${dateLabel(o.last_seen)}.${o.source_record_id?` <b>Source ID:</b> ${esc(o.source_record_id)}.`:''}${o.source_url?` <a class="source-link" href="${esc(o.source_url)}" target="_blank" rel="noopener noreferrer">Open canonical source ↗</a>`:''}`;
    $('#detailContent').innerHTML=`<span class="eyebrow">CASHH RADAR INTELLIGENCE RECORD</span><h2 class="detail-title">${esc(o.title)}</h2><div class="opp-kicker"><span class="badge cyan">${esc(o.category)}</span><span class="status-chip ${esc(v.status)}">${esc(verifyLabel(o))}</span><span class="badge">${esc(o.mode)}</span></div><p class="opp-sub">${esc(o.why)}</p>
      <div class="detail-grid"><div class="detail-card"><span>Personalized match</span><b>${o.match}/100</b></div><div class="detail-card"><span>Time-to-income model</span><b>${days(o.speed_days)}</b></div><div class="detail-card"><span>${esc(o.income_label||'Income')}</span><b>${esc(incomeText(o))}</b></div><div class="detail-card"><span>Startup cost model</span><b>${money(o.startup_cost||0)}</b></div><div class="detail-card"><span>Last observed</span><b>${dateLabel(o.last_seen)}</b></div><div class="detail-card"><span>Deadline / close</span><b>${dateLabel(o.closes_at)}</b></div></div>
      <div class="evidence-box"><h4>Evidence & lineage</h4><p>${evidence}</p></div>${o.eligibility?`<h3>Eligibility signal</h3><p class="opp-sub">${esc(o.eligibility)}</p>`:''}<h3>Risk notes</h3><p class="opp-sub">${esc(o.risks||'No source-specific risk note supplied.')}</p><h3>Execution roadmap</h3><div class="steps">${(o.steps||[]).map(s=>`<div>${esc(s)}</div>`).join('')}</div>
      <div class="toolbar"><button class="primary-btn" data-save="${esc(o.id)}">${saved?'Remove from watchlist':'Add to watchlist'}</button><button class="ghost-btn" data-make-roadmap="${esc(o.id)}">Create roadmap</button><button class="ghost-btn" data-make-outreach="${esc(o.id)}">Draft outreach</button><button class="ghost-btn" data-log-outcome="${esc(o.id)}">Log outcome</button></div>${notice('Cashh Radar is decision support. It does not guarantee earnings, acceptance, funding, eligibility, or future availability.')}`;
    drawer.classList.add('open');backdrop.classList.remove('hidden');drawer.setAttribute('aria-hidden','false');track('opportunity_open',{id});
  }
  function closeDetail(){drawer.classList.remove('open');backdrop.classList.add('hidden');drawer.setAttribute('aria-hidden','true')}

  async function toggleSave(id){
    if(!state.me){openAccount('signin');return}
    try{
      if(state.saved.has(id)){await api(`/api/watchlist/${encodeURIComponent(id)}`,{method:'DELETE'});state.saved.delete(id)}
      else{await api(`/api/watchlist/${encodeURIComponent(id)}`,{method:'POST'});state.saved.add(id)}
      $('#watchCount').textContent=state.saved.size;render();if(drawer.classList.contains('open'))openDetail(id);track('watchlist_toggle',{id,saved:state.saved.has(id)});
    }catch(e){toast(e.message)}
  }

  async function renderSources(){
    filters.classList.add('hidden'); const d=await api('/api/source-status').catch(()=>null); state.sourceStatus=d;
    if(!d){list.innerHTML=notice('Source status is unavailable.','danger');return}
    $('#resultsSummary').textContent=`${d.opportunities} normalized records • ${d.source_records} source records • backend connected`;
    const runs=new Map((d.runs||[]).map(r=>[r.source_key,r]));
    list.innerHTML=(d.sources||[]).map(s=>{const r=runs.get(s.key);return `<article class="opportunity-card source-card"><div class="opp-top"><div><div class="opp-kicker"><span class="badge ${s.status==='enabled'?'green':s.status==='license-gated'?'amber':'cyan'}">${esc(s.status)}</span><span class="badge">Trust ${esc(s.trust)}</span></div><h3 class="opp-title">${esc(s.name)}</h3><div class="opp-sub">${esc(s.kind)}</div></div><div class="score-box"><strong>${esc(s.refresh)}</strong><small>REFRESH</small></div></div><div class="source-policy-grid"><div><span>Auth</span><b>${esc(s.auth)}</b></div><div><span>Last run</span><b>${esc(r?(r.status+' • '+dateLabel(r.finished_at||r.started_at)):'Not run locally')}</b></div><div><span>Fetched</span><b>${esc(r?r.fetched_count:'—')}</b></div><div><span>Normalized</span><b>${esc(r?r.normalized_count:'—')}</b></div></div><div class="evidence-box"><h4>Policy guardrail</h4><p>${esc(s.policy)}</p></div></article>`}).join('')+`<article class="opportunity-card"><h3>Grants.gov notice</h3><p class="opp-sub">Cashh Radar can use the Grants.gov API but is not endorsed or certified by the U.S. Department of Health and Human Services.</p></article>`;
  }

  function openModalHtml(html){modalContent.innerHTML=html;modal.classList.remove('hidden')}
  function closeModal(){modal.classList.add('hidden')}

  async function maybeAcceptOrganizationInvite(){
    const raw=new URLSearchParams(location.search).get('org_invite');
    if(!raw||!state.me) return false;
    try{
      const d=await api('/api/organizations/invites/accept',{method:'POST',body:JSON.stringify({token:raw})});
      const url=new URL(location.href);url.searchParams.delete('org_invite');history.replaceState({},'',url.pathname+url.search+url.hash);toast(`Joined Team workspace as ${d.role}`);return true;
    }catch(err){toast(`Workspace invite: ${err.message}`);return false}
  }

  function openAccount(mode='signin'){
    if(state.me){
      openModalHtml(`<span class="eyebrow">ACCOUNT</span><h2 id="modalTitle">${esc(state.me.email)}</h2><p>Plan: <b>${esc(state.me.plan)}</b> • Role: <b>${esc(state.me.role)}</b></p><div class="toolbar"><button class="primary-btn" data-account-profile>Opportunity profile</button><button class="ghost-btn" data-logout>Sign out</button></div>`);return;
    }
    openModalHtml(`<span class="eyebrow">CASHH RADAR ACCOUNT</span><h2 id="modalTitle">${mode==='register'?'Create account':'Sign in'}</h2><p>Sign in to persist saved opportunities, roadmaps, alerts, outreach assets, and outcomes.</p><form id="authForm" class="auth-form"><label>Email<input name="email" type="email" required autocomplete="email"></label><label>Password<input name="password" type="password" required minlength="10" autocomplete="${mode==='register'?'new-password':'current-password'}"></label><button class="primary-btn" type="submit">${mode==='register'?'Create account':'Sign in'}</button></form><div class="toolbar"><button class="ghost-btn" data-auth-switch="${mode==='register'?'signin':'register'}">${mode==='register'?'I already have an account':'Create an account'}</button>${mode==='signin'?'<button class="ghost-btn" data-password-reset>Forgot password?</button>':''}</div><div id="authError"></div>`);
    $('#authForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);try{const qs=new URLSearchParams(location.search);const payload={email:f.get('email'),password:f.get('password')};if(mode==='register'&&qs.get('ref'))payload.referral_code=qs.get('ref');const d=await api(`/api/${mode==='register'?'register':'login'}`,{method:'POST',body:JSON.stringify(payload)});if(d.verification_required){$('#authError').innerHTML=notice(d.message||'Check your email to verify your account.','success')+(d.dev_verification_token?`<div class="codebox">DEV VERIFY TOKEN: ${esc(d.dev_verification_token)}</div>`:'');return}if(d.two_step_required){openTwoStep(d.challenge_token,d.dev_code||'');return}state.me=d.user;state.csrf=d.csrf_token;await loadMe();await maybeAcceptOrganizationInvite();closeModal();await loadRecords();toast(mode==='register'?'Account created.':'Signed in.')}catch(err){$('#authError').innerHTML=notice(err.message,'danger')}})
  }

  function openTwoStep(challengeToken,devCode=''){
    openModalHtml(`<span class="eyebrow">TWO-STEP SIGN IN</span><h2 id="modalTitle">Enter your 6-digit code</h2><p>We sent a one-time code to your account email. It expires in 10 minutes.</p><form id="twoStepForm" class="auth-form"><label>Code<input name="code" inputmode="numeric" minlength="6" maxlength="6" pattern="[0-9]{6}" required></label><button class="primary-btn">Complete sign in</button></form>${devCode?`<div class="codebox">DEV CODE: ${esc(devCode)}</div>`:''}<div id="twoStepMsg"></div>`);
    $('#twoStepForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);try{const d=await api('/api/login/two-step',{method:'POST',body:JSON.stringify({challenge_token:challengeToken,code:f.get('code')})});state.me=d.user;state.csrf=d.csrf_token;await loadMe();await maybeAcceptOrganizationInvite();closeModal();await loadRecords();toast('Signed in securely.')}catch(err){$('#twoStepMsg').innerHTML=notice(err.message,'danger')}})
  }

  function openPasswordReset(){
    openModalHtml(`<span class="eyebrow">ACCOUNT RECOVERY</span><h2 id="modalTitle">Reset password</h2><p>Enter your account email. If SMTP is configured, Cashh Radar emails a 30-minute reset link. Development mode can display a test token.</p><form id="resetRequestForm" class="auth-form"><label>Email<input name="email" type="email" required></label><button class="primary-btn" type="submit">Create reset instructions</button></form><div id="resetMsg"></div>`);
    $('#resetRequestForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);try{const d=await api('/api/account/password-reset/request',{method:'POST',body:JSON.stringify({email:f.get('email')})});$('#resetMsg').innerHTML=notice(d.message,'success')+(d.dev_reset_token?`<div class="codebox">DEV TOKEN: ${esc(d.dev_reset_token)}</div><button class="mini-btn" data-reset-confirm-token="${esc(d.dev_reset_token)}">Use dev token</button>`:'')}catch(err){$('#resetMsg').innerHTML=notice(err.message,'danger')}})
  }

  function openPasswordResetConfirm(token=''){
    openModalHtml(`<span class="eyebrow">ACCOUNT RECOVERY</span><h2 id="modalTitle">Choose a new password</h2><form id="resetConfirmForm" class="auth-form"><label>Reset token<input name="token" value="${esc(token)}" required></label><label>New password<input name="password" type="password" minlength="10" required></label><button class="primary-btn" type="submit">Reset password</button></form><div id="resetConfirmMsg"></div>`);
    $('#resetConfirmForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);try{await api('/api/account/password-reset/confirm',{method:'POST',body:JSON.stringify({token:f.get('token'),new_password:f.get('password')})});$('#resetConfirmMsg').innerHTML=notice('Password reset. You can sign in now.','success')}catch(err){$('#resetConfirmMsg').innerHTML=notice(err.message,'danger')}})
  }

  async function openProfile(){
    const me=await api('/api/me');const p=me.profile||{};
    openModalHtml(`<span class="eyebrow">PERSONALIZATION</span><h2 id="modalTitle">Opportunity profile</h2><p>This changes your ranking; it does not alter source facts.</p><form id="profileForm" class="tool-form"><label>Main goal<textarea name="goal" placeholder="Example: remote income with no startup cost">${esc(p.goal||'')}</textarea></label><label>Work mode<select name="work_mode"><option value="any">Any</option><option value="remote">Remote</option><option value="hybrid">Hybrid</option><option value="local">Local</option></select></label><label>Startup budget<input name="startup_budget" type="number" min="0" value="${esc(p.startup_budget??0)}"></label><label>Urgency (days)<input name="urgency_days" type="number" min="1" value="${esc(p.urgency_days??14)}"></label><label>Experience<select name="experience"><option value="entry">Entry</option><option value="quick">Quick-skill</option><option value="experienced">Experienced</option></select></label><label>Location<input name="location" value="${esc(p.location||'')}"></label><button class="primary-btn">Save profile</button></form><div id="profileMsg"></div>`);
    $('#profileForm').work_mode.value=p.work_mode||'any';$('#profileForm').experience.value=p.experience||'entry';
    $('#profileForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);try{await api('/api/profile',{method:'PUT',body:JSON.stringify({goal:f.get('goal'),work_mode:f.get('work_mode'),startup_budget:Number(f.get('startup_budget')),urgency_days:Number(f.get('urgency_days')),experience:f.get('experience'),location:f.get('location')})});$('#profileMsg').innerHTML=notice('Profile saved. Rankings refreshed.','success');await loadRecords()}catch(err){$('#profileMsg').innerHTML=notice(err.message,'danger')}})
  }

  const onboardingSteps=[
    {eyebrow:'WELCOME',title:'Spot better money opportunities.',body:'Cashh Radar discovers, verifies, scores, and tracks opportunities so you can focus on realistic next actions.',icon:'◎'},
    {eyebrow:'PERSONALIZE',title:'Tell Radar what matters.',body:'Set your goal, work mode, startup budget, urgency, experience, and location. Rankings adapt without changing source facts.',icon:'◈'},
    {eyebrow:'TRACK',title:'Save signals worth watching.',body:'Use your Watchlist and Alerts to follow deadlines, material source changes, and strong matches.',icon:'☆'},
    {eyebrow:'ACT',title:'Turn a signal into a plan.',body:'Open an opportunity to build a roadmap, create source-aware outreach, and track the outcome from started to paid.',icon:'↗'}
  ];
  function openOnboarding(step=0){
    const x=onboardingSteps[Math.max(0,Math.min(step,onboardingSteps.length-1))];
    const dots=onboardingSteps.map((_,i)=>`<span class="onboarding-dot ${i===step?'active':''}"></span>`).join('');
    openModalHtml(`<div class="onboarding-shell"><img class="onboarding-logo" src="/static/assets/logo-mark.svg" alt="Cashh Radar"><span class="eyebrow">${x.eyebrow}</span><div class="onboarding-icon">${x.icon}</div><h2 id="modalTitle">${x.title}</h2><p>${x.body}</p><div class="onboarding-dots">${dots}</div><div class="toolbar onboarding-actions">${step?`<button class="ghost-btn" data-onboard-prev="${step-1}">Back</button>`:''}<button class="primary-btn" data-onboard-next="${step+1}">${step===onboardingSteps.length-1?'Explore opportunities':'Continue'}</button></div><button class="onboarding-skip" data-onboard-skip>Skip onboarding</button></div>`)
  }

  async function openWatchlist(){
    if(!state.me){openAccount();return} const d=await api('/api/watchlist');openModalHtml(`<span class="eyebrow">EXECUTION</span><h2 id="modalTitle">Watchlist</h2><p>${d.opportunities.length} saved opportunity(s).</p><div class="module-stack">${d.opportunities.map(o=>`<div class="module-row"><h4>${esc(o.title)}</h4><p>${esc(o.organization)} • ${esc(verifyLabel(o))}</p><button class="mini-btn" data-detail="${esc(o.id)}">Open</button> <button class="mini-btn" data-save="${esc(o.id)}">Remove</button></div>`).join('')||notice('Nothing saved yet.')}</div>`)
  }

  async function openAdvisor(prefill=''){
    const me=await api('/api/me').catch(()=>({profile:{}})); const p=me.profile||{};
    openModalHtml(`<span class="eyebrow">OPPORTUNITY ADVISOR</span><h2 id="modalTitle">Rank the best realistic options</h2><p>The advisor uses explainable scoring and evidence state, not guaranteed-outcome claims.</p><form id="advisorForm" class="tool-form"><label>What do you need?<textarea name="goal">${esc(prefill||p.goal||'')}</textarea></label><div class="modal-grid"><label>Work mode<select name="work_mode"><option value="any">Any</option><option value="remote">Remote</option><option value="hybrid">Hybrid</option><option value="local">Local</option></select></label><label>Budget<input name="startup_budget" type="number" min="0" value="${esc(p.startup_budget??0)}"></label><label>Urgency days<input name="urgency_days" type="number" min="1" value="${esc(p.urgency_days??14)}"></label><label>Experience<select name="experience"><option value="entry">Entry</option><option value="quick">Quick-skill</option><option value="experienced">Experienced</option></select></label></div><button class="primary-btn">Analyze opportunities</button></form><div id="advisorResult" class="module-stack" style="margin-top:14px"></div>`);
    $('#advisorForm').work_mode.value=p.work_mode||'any';$('#advisorForm').experience.value=p.experience||'entry';
    $('#advisorForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);const out=$('#advisorResult');out.innerHTML=notice('Analyzing current records…');try{const d=await api('/api/advisor',{method:'POST',body:JSON.stringify({goal:f.get('goal'),work_mode:f.get('work_mode'),startup_budget:Number(f.get('startup_budget')),urgency_days:Number(f.get('urgency_days')),experience:f.get('experience'),limit:5})});out.innerHTML=d.recommendations.map(r=>`<div class="module-row"><div class="opp-kicker"><span class="badge cyan">${r.match}/100</span><span class="status-chip ${esc(r.verification.status)}">${esc(r.verification.status.replaceAll('_',' '))}</span></div><h4>${esc(r.title)}</h4><p>${esc(r.why)}</p><p><b>Reasons:</b> ${esc(r.reasons.join(' • '))}</p><p><b>Risk:</b> ${esc(r.risks)}</p><button class="mini-btn" data-detail="${esc(r.id)}">Open intelligence</button></div>`).join('')+notice(d.disclaimer);track('advisor_run',{goal:String(f.get('goal')).slice(0,80)})}catch(err){out.innerHTML=notice(err.message,'danger')}})
  }

  async function makeRoadmap(id){
    if(!state.me){openAccount();return} try{const d=await api('/api/roadmaps',{method:'POST',body:JSON.stringify({opportunity_id:id})});closeDetail();openModalHtml(`<span class="eyebrow">ROADMAP CREATED</span><h2 id="modalTitle">${esc(d.title)}</h2><div class="steps">${d.steps.map(s=>`<div>${esc(s.title)}</div>`).join('')}</div>${notice('Saved to your Cashh Radar account.','success')}`);track('roadmap_created',{id})}catch(e){toast(e.message)}
  }

  async function openRoadmaps(){
    if(!state.me){openAccount();return}const d=await api('/api/roadmaps');openModalHtml(`<span class="eyebrow">INCOME ROADMAPS</span><h2 id="modalTitle">Execution plans</h2><div class="module-stack">${d.roadmaps.map(r=>`<div class="module-row"><h4>${esc(r.title)}</h4><p>${esc(r.opportunity_title)} • ${esc(r.status)}</p><div class="steps">${r.steps.map(s=>`<div>${esc(s.title)}</div>`).join('')}</div></div>`).join('')||notice('Create a roadmap from any opportunity intelligence record.')}</div>`)
  }

  async function makeOutreach(id){
    if(!state.me){openAccount();return} const o=state.records.find(x=>x.id===id);closeDetail();
    openModalHtml(`<span class="eyebrow">OUTREACH STUDIO</span><h2 id="modalTitle">${esc(o?.title||'Draft outreach')}</h2><form id="oneOutreach" class="tool-form"><label>Asset type<select name="asset_type"><option value="application_email">Application email</option><option value="proposal">Proposal opener</option><option value="dm">DM</option><option value="follow_up">Follow-up</option></select></label><button class="primary-btn">Generate truthful draft</button></form><div id="outreachResult"></div>`);
    $('#oneOutreach').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);try{const d=await api('/api/outreach',{method:'POST',body:JSON.stringify({opportunity_id:id,asset_type:f.get('asset_type')})});$('#outreachResult').innerHTML=`<div class="codebox">${esc(d.content)}</div>${notice(d.note)}`;track('outreach_generated',{id,type:f.get('asset_type')})}catch(err){$('#outreachResult').innerHTML=notice(err.message,'danger')}})
  }

  async function openStudio(){
    if(!state.me){openAccount();return}const opts=state.records.map(o=>`<option value="${esc(o.id)}">${esc(o.title)}</option>`).join('');openModalHtml(`<span class="eyebrow">APPLICATION & OUTREACH STUDIO</span><h2 id="modalTitle">Create a source-aware draft</h2><form id="studioForm" class="tool-form"><label>Opportunity<select name="opportunity_id">${opts}</select></label><label>Asset<select name="asset_type"><option value="application_email">Application email</option><option value="proposal">Proposal opener</option><option value="dm">DM</option><option value="follow_up">Follow-up</option></select></label><button class="primary-btn">Generate</button></form><div id="studioOutput"></div>`);$('#studioForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);try{const d=await api('/api/outreach',{method:'POST',body:JSON.stringify(Object.fromEntries(f))});$('#studioOutput').innerHTML=`<div class="codebox">${esc(d.content)}</div>${notice(d.note)}`}catch(err){$('#studioOutput').innerHTML=notice(err.message,'danger')}})
  }

  async function openAlerts(){
    if(!state.me){openAccount();return}const d=await api('/api/alerts');openModalHtml(`<span class="eyebrow">ALERTS</span><h2 id="modalTitle">Opportunity change & match alerts</h2><form id="alertForm" class="tool-form"><label>Name<input name="name" value="Deadline watch"></label><label>Rule<select name="kind"><option value="deadline">Saved opportunity deadline</option><option value="material_change">Material source change</option><option value="new_match">New high match</option></select></label><label>Look-ahead / recency days<input name="days" type="number" min="1" max="90" value="7"></label><button class="primary-btn">Create alert</button></form><div class="toolbar"><button class="ghost-btn" data-evaluate-alerts>Evaluate now</button></div><h3>Rules</h3><div class="module-stack">${d.rules.map(r=>`<div class="module-row"><h4>${esc(r.name)}</h4><p>${esc(r.rule.kind)} • ${esc(r.rule.days)} day(s) • ${r.enabled?'enabled':'disabled'}</p><button class="mini-btn" data-delete-alert="${r.id}">Delete</button></div>`).join('')||notice('No alert rules yet.')}</div><h3>Recent events</h3><div class="module-stack">${d.events.slice(0,20).map(x=>`<div class="module-row"><b>${esc(x.kind)}</b><span>${esc(x.message)} • ${dateLabel(x.created_at)}</span></div>`).join('')||notice('No alert events yet.')}</div><div id="alertMsg"></div>`);$('#alertForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);try{await api('/api/alerts',{method:'POST',body:JSON.stringify({name:f.get('name'),kind:f.get('kind'),days:Number(f.get('days')),enabled:true})});openAlerts()}catch(err){$('#alertMsg').innerHTML=notice(err.message,'danger')}})
  }

  async function logOutcome(id){
    if(!state.me){openAccount();return}closeDetail();const o=state.records.find(x=>x.id===id);openModalHtml(`<span class="eyebrow">OUTCOME TRACKER</span><h2 id="modalTitle">${esc(o?.title||'Log outcome')}</h2><form id="outcomeOne" class="tool-form"><label>Stage<select name="stage"><option>started</option><option>applied</option><option>contacted</option><option>replied</option><option>interview</option><option>negotiating</option><option>won</option><option>paid</option><option>fulfilled</option><option>follow_up</option><option>lost</option></select></label><label>Notes<textarea name="notes"></textarea></label><label>Amount actually received (optional)<input name="amount" type="number" step="0.01"></label><button class="primary-btn">Save outcome</button></form><div id="outcomeMsg"></div>`);$('#outcomeOne').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);const amount=f.get('amount');try{await api('/api/outcomes',{method:'POST',body:JSON.stringify({opportunity_id:id,stage:f.get('stage'),notes:f.get('notes'),amount:amount?Number(amount):null})});$('#outcomeMsg').innerHTML=notice('Outcome saved.','success');track('outcome_logged',{id,stage:f.get('stage')})}catch(err){$('#outcomeMsg').innerHTML=notice(err.message,'danger')}})
  }

  async function openTracker(){
    if(!state.me){openAccount();return}const d=await api('/api/outcomes');openModalHtml(`<span class="eyebrow">OUTCOME TRACKER</span><h2 id="modalTitle">What actually happened</h2><div class="admin-grid">${Object.entries(d.summary||{}).map(([k,v])=>`<article><strong>${v}</strong><small>${esc(k)}</small></article>`).join('')||'<article><strong>0</strong><small>recorded outcomes</small></article>'}</div><div class="module-stack">${d.outcomes.map(x=>`<div class="module-row"><h4>${esc(x.opportunity_title)}</h4><p><b>${esc(x.stage)}</b> • ${dateLabel(x.occurred_at)}${x.amount!=null?' • '+money(x.amount):''}</p><p>${esc(x.notes||'')}</p></div>`).join('')||notice('No outcomes recorded yet. Use “Log outcome” on an opportunity.')}</div>`)
  }

  async function openPlans(){
    const d=await api('/api/plans');const current=state.me?.plan||'free';const manage=state.me&&current!=='free'?`<div class="notice">Current plan: <b>${esc(current)}</b>${state.me.subscription_status?' • '+esc(state.me.subscription_status):''}<br><button class="ghost-btn" data-billing-portal style="margin-top:9px">Manage / cancel billing</button></div>`:'';openModalHtml(`<span class="eyebrow">MONETIZATION</span><h2 id="modalTitle">Cashh Radar plans</h2><p>Billing uses Stripe-hosted checkout when activated. Subscription cancellation and payment-method management use Stripe's customer portal.</p>${manage}<div class="plan-grid">${Object.entries(d.plans).map(([key,p])=>`<div class="plan-card"><h3>${esc(p.name)}</h3><div class="plan-price">${p.price_monthly?money(p.price_monthly)+'/mo':'Free'}</div><ul>${p.features.map(f=>`<li>${esc(f)}</li>`).join('')}</ul>${key==='free'||key===current?'':`<button class="primary-btn" data-checkout="${key}">Choose ${esc(p.name)}</button>`}</div>`).join('')}</div><div id="billingMsg"></div>`)
  }

  async function openAdmin(){
    if(!(state.me&&state.me.role==='admin')){toast('Admin access required');return}
    const [d,sources,opp,ops,analytics,subs,jobs,providerStats]=await Promise.all([api('/api/admin/dashboard'),api('/api/source-status'),api('/api/admin/opportunities'),api('/api/admin/operations'),api('/api/admin/analytics'),api('/api/admin/submissions'),api('/api/admin/jobs'),api('/api/admin/providers/analytics')]);
    openModalHtml(`<span class="eyebrow">OWNER ADMIN</span><h2 id="modalTitle">Cashh Radar command center</h2>
      <div class="admin-grid">${Object.entries(d.metrics).map(([k,v])=>`<article><strong>${esc(v)}</strong><small>${esc(k.replaceAll('_',' '))}</small></article>`).join('')}<article><strong>${analytics.active_users_7d}</strong><small>active users 7d</small></article><article><strong>${analytics.api_calls_30d}</strong><small>API calls 30d</small></article></div>
      <h3>Operations queues</h3><div class="admin-grid"><article><strong>${ops.stale.length}</strong><small>stale records</small></article><article><strong>${ops.unverified.length}</strong><small>verification queue</small></article><article><strong>${ops.duplicates.length}</strong><small>duplicate groups</small></article><article><strong>${ops.provider_leads.length}</strong><small>provider leads</small></article><article><strong>${subs.submissions.filter(x=>x.status==='pending').length}</strong><small>user submissions</small></article></div>
      <h3>Source controls</h3><div class="module-stack">${sources.sources.map(x=>`<div class="module-row"><h4>${esc(x.name)}</h4><p>${esc(x.status)} • ${esc(x.policy)}</p>${['grants_gov','usajobs','lever_partner'].includes(x.key)?`<button class="mini-btn" data-refresh-source="${esc(x.key)}">Refresh source</button>`:''}</div>`).join('')}</div>
      <h3>User-submitted source intake</h3><div class="module-stack">${subs.submissions.slice(0,20).map(x=>`<div class="module-row"><h4>${esc(x.title)}</h4><p>${esc(x.email)} • ${esc(x.category)} • ${esc(x.status)}</p><a class="source-link" href="${esc(x.source_url)}" target="_blank" rel="noopener">Review source ↗</a>${x.status==='pending'?`<div class="toolbar"><button class="mini-btn" data-submission-decision="approved" data-submission-id="${x.id}">Accept for research</button><button class="mini-btn" data-submission-decision="rejected" data-submission-id="${x.id}">Reject</button></div>`:''}</div>`).join('')||notice('No submissions.')}</div>
      <h3>Opportunity moderation</h3><div class="module-stack">${opp.opportunities.slice(0,20).map(o=>`<div class="module-row"><h4>${esc(o.title)}</h4><p>${esc(o.source_name)} • ${esc(verifyLabel(o))}</p><div class="toolbar">${o.trust!=='demo'?`<button class="mini-btn" data-admin-verify="${esc(o.id)}">Mark verified</button>`:''}<button class="mini-btn" data-admin-block="${esc(o.id)}">Block</button></div></div>`).join('')}</div>
      <h3>Provider lead pipeline</h3><div class="module-stack">${(ops.provider_leads||[]).slice(0,20).map(x=>`<div class="module-row"><h4>${esc(x.provider_name)}</h4><p>${esc(x.email)} • ${esc(x.status)} • ${dateLabel(x.updated_at)}</p><div class="toolbar"><button class="mini-btn" data-lead-status="contacted" data-lead-id="${x.id}">Contacted</button><button class="mini-btn" data-lead-status="qualified" data-lead-id="${x.id}">Qualified</button><button class="mini-btn" data-lead-status="closed_won" data-lead-id="${x.id}">Won</button><button class="mini-btn" data-lead-status="closed_lost" data-lead-id="${x.id}">Lost</button></div></div>`).join('')||notice('No provider leads.')}</div>
      <h3>Background jobs</h3><div class="toolbar"><button class="mini-btn" data-run-job="alerts">Run alerts</button><button class="mini-btn" data-run-job="digests">Run digests</button><button class="mini-btn" data-run-job="maintenance">Run maintenance</button><button class="mini-btn" data-run-job="sources">Refresh scheduled sources</button><button class="mini-btn" data-run-job="webhooks">Deliver webhooks</button><button class="mini-btn" data-run-job="backups">Create verified backup</button></div><div class="module-stack">${(jobs.jobs||[]).slice(0,8).map(j=>`<div class="module-row"><b>${esc(j.job_name)}</b><span>${esc(j.status)} • ${j.duration_ms||0} ms • ${dateLabel(j.finished_at)}</span></div>`).join('')||notice('No background job runs yet.')}</div>
      <h3>30-day analytics</h3><div class="module-stack">${(analytics.events||[]).slice(0,12).map(x=>`<div class="module-row"><b>${esc(x.event_name)}</b><span>${esc(x.count)}</span></div>`).join('')||notice('No analytics yet.')}</div>
      <h3>Recent audit</h3><div class="codebox">${esc((d.audit||[]).slice(0,15).map(a=>`${a.created_at} • ${a.action} • ${a.entity_type}:${a.entity_id||''}`).join('\n')||'No admin actions recorded yet.')}</div><div id="adminMsg"></div>`)
  }


  async function openPulse(){
    if(!state.me){openAccount();return}
    const [p,ss,d]=await Promise.all([api('/api/pulse'),api('/api/saved-searches'),api('/api/digest')]);
    openModalHtml(`<span class="eyebrow">OPPORTUNITY PULSE</span><h2 id="modalTitle">What changed & what matters now</h2><p>${esc(d.summary||'')}</p>
      <div class="admin-grid"><article><strong>${p.newest.length}</strong><small>new/recent</small></article><article><strong>${p.closing_soon.length}</strong><small>closing soon</small></article><article><strong>${p.changes.length}</strong><small>source changes</small></article><article><strong>${p.alerts.length}</strong><small>alert events</small></article></div>
      <h3>Top personalized digest</h3><div class="module-stack">${(d.top_matches||[]).slice(0,6).map(o=>`<div class="module-row"><h4>${esc(o.title)}</h4><p>${o.match}/100 • ${esc(verifyLabel(o))} • ${dateLabel(o.closes_at)}</p><button class="mini-btn" data-detail="${esc(o.id)}">Open intelligence</button></div>`).join('')||notice('No digest matches yet.')}</div>
      <h3>Saved searches</h3><form id="savedSearchForm" class="form-grid"><label>Name<input name="name" required maxlength="120" placeholder="Remote $0 startup"></label><label>Keywords<input name="text" maxlength="500" placeholder="remote customer support"></label><label>Minimum match<input name="min_match" type="number" min="0" max="100" value="70"></label><button class="primary-btn" type="submit">Save search</button></form>
      <div class="module-stack">${(ss.saved_searches||[]).map(x=>`<div class="module-row"><h4>${esc(x.name)}</h4><p>${esc(JSON.stringify(x.query))}</p><button class="mini-btn" data-delete-search="${x.id}">Delete</button></div>`).join('')||notice('No saved searches yet.')}</div><div id="pulseMsg"></div>`);
    $('#savedSearchForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);try{await api('/api/saved-searches',{method:'POST',body:JSON.stringify({name:f.get('name'),text:f.get('text'),min_match:Number(f.get('min_match')||70)})});toast('Saved search created');openPulse()}catch(err){$('#pulseMsg').innerHTML=notice(err.message,'danger')}})
  }

  async function openGrowth(){
    if(!state.me){openAccount();return}
    const [r,p,subs,leads]=await Promise.all([api('/api/referral'),api('/api/providers'),api('/api/submissions'),api('/api/provider-leads')]);
    openModalHtml(`<span class="eyebrow">GROWTH & PARTNERS</span><h2 id="modalTitle">Referral, providers & community sourcing</h2><div class="evidence-box"><h4>Your referral code</h4><p><b>${esc(r.code)}</b></p><div class="codebox">${esc(r.share_url)}</div><p>${esc(r.disclosure)}</p><p>Tracked events: ${esc(JSON.stringify(r.events||{}))}</p></div>
      <h3>Submit a public opportunity source</h3><form id="submissionForm" class="form-grid"><label>Title<input name="title" required></label><label>Public source URL<input name="source_url" type="url" required placeholder="https://..."></label><label>Category<input name="category" value="Other"></label><label>Notes<textarea name="notes"></textarea></label><button class="primary-btn" type="submit">Submit for evidence review</button></form><div class="module-stack">${(subs.submissions||[]).slice(0,10).map(x=>`<div class="module-row"><h4>${esc(x.title)}</h4><p>${esc(x.status)} • ${dateLabel(x.created_at)}</p></div>`).join('')}</div>
      <h3>Approved providers</h3><div class="module-stack">${(p.providers||[]).map(x=>`<div class="module-row"><h4>${esc(x.name)}</h4><p>${esc(x.category)} • ${esc(x.disclosure||'')}</p>${x.website?`<a class="source-link" href="${esc(x.website)}" target="_blank" rel="noopener">Website ↗</a>`:''}<button class="mini-btn" data-provider-request="${x.id}">Request introduction</button></div>`).join('')||notice('No provider partners are active yet. Provider monetization stays off until a partner is explicitly approved.')}</div>
      <h3>Your provider requests</h3><div class="module-stack">${(leads.provider_leads||[]).map(x=>`<div class="module-row"><h4>${esc(x.provider_name)}</h4><p>${esc(x.status)} • ${dateLabel(x.updated_at)}</p>${x.admin_note?`<p>${esc(x.admin_note)}</p>`:''}</div>`).join('')||notice('No provider requests yet.')}</div><div id="growthMsg"></div>`);
    $('#submissionForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);try{const d=await api('/api/submissions',{method:'POST',body:JSON.stringify({title:f.get('title'),source_url:f.get('source_url'),category:f.get('category'),notes:f.get('notes')})});$('#growthMsg').innerHTML=notice(d.message,'success');openGrowth()}catch(err){$('#growthMsg').innerHTML=notice(err.message,'danger')}})
  }

  async function openDeveloper(){
    if(!state.me){openAccount();return}
    const [keys,orgs]=await Promise.all([api('/api/api-keys'),api('/api/organizations')]);
    openModalHtml(`<span class="eyebrow">API • ENTERPRISE • WHITE LABEL</span><h2 id="modalTitle">Developer & organization tools</h2><p>API keys require Pro/Team (or admin). Team workspaces support tenant branding, members, invites, and organization-scoped API credentials.</p>
      <h3>API keys</h3><form id="apiKeyForm" class="form-grid"><label>Name<input name="name" placeholder="Production integration" required></label><label>Organization (optional)<select name="organization_id"><option value="">Personal key</option>${(orgs.organizations||[]).map(o=>`<option value="${o.id}">${esc(o.name)}</option>`).join('')}</select></label><label>Scopes<select name="scope" multiple size="5"><option value="opportunities:read" selected>Opportunities</option><option value="watchlists:read">Watchlists</option><option value="alerts:read">Alerts</option><option value="analytics:read">Analytics</option><option value="usage:read">Usage</option></select></label><button class="primary-btn" type="submit">Create API key</button></form><div id="apiKeyResult"></div><div class="module-stack">${(keys.api_keys||[]).map(k=>`<div class="module-row"><h4>${esc(k.name)}</h4><p>${esc(k.key_prefix)}… • ${k.organization_name?esc(k.organization_name)+' • ':''}${k.revoked_at?'revoked':'active'} • ${k.rate_limit_per_minute||60}/min • last used ${dateLabel(k.last_used_at)}</p>${!k.revoked_at?`<button class="mini-btn" data-revoke-key="${k.id}">Revoke</button>`:''}</div>`).join('')||notice('No API keys yet.')}</div>
      <h3>Organizations / white label</h3><form id="orgForm" class="form-grid"><label>Name<input name="name" required placeholder="My Team"></label><label>Slug<input name="slug" required pattern="[a-z0-9-]+" placeholder="my-team"></label><button class="primary-btn" type="submit">Create Team workspace</button></form><div class="module-stack">${(orgs.organizations||[]).map(o=>`<div class="module-row"><h4>${esc(o.brand_name||o.name)}</h4><p>${esc(o.slug)} • ${esc(o.role)} • ${o.member_count||1} member(s)${o.custom_domain?' • '+esc(o.custom_domain):''}</p><button class="mini-btn" data-org-manage="${o.id}">Manage workspace</button></div>`).join('')||notice('No Team workspaces yet.')}</div><div id="devMsg"></div>`);
    $('#apiKeyForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);try{const oid=f.get('organization_id');const d=await api('/api/api-keys',{method:'POST',body:JSON.stringify({name:f.get('name'),organization_id:oid?Number(oid):null,scopes:[...e.target.elements.scope.selectedOptions].map(x=>x.value)})});$('#apiKeyResult').innerHTML=`<div class="notice success"><b>Copy this key now:</b><div class="codebox">${esc(d.api_key)}</div>${esc(d.warning)}</div>`}catch(err){$('#devMsg').innerHTML=notice(err.message,'danger')}});
    $('#orgForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);try{await api('/api/organizations',{method:'POST',body:JSON.stringify({name:f.get('name'),slug:f.get('slug')})});toast('Workspace created');openDeveloper()}catch(err){$('#devMsg').innerHTML=notice(err.message,'danger')}})
  }

  async function openOrganization(id){
    const [orgs,data,shared,hooks]=await Promise.all([api('/api/organizations'),api(`/api/organizations/${id}/members`),api(`/api/organizations/${id}/watchlist`),api(`/api/organizations/${id}/webhooks`).catch(()=>({webhooks:[]}))]);const org=(orgs.organizations||[]).find(x=>String(x.id)===String(id));if(!org){toast('Workspace unavailable');return}
    openModalHtml(`<span class="eyebrow">TEAM WORKSPACE</span><h2 id="modalTitle">${esc(org.name)}</h2><p>${esc(org.slug)} • ${esc(org.role)} • ${data.members.length} member(s)</p><h3>Shared watchlist</h3><form id="orgWatchForm" class="form-grid"><label>Opportunity<select name="opportunity_id">${state.records.slice(0,100).map(o=>`<option value="${esc(o.id)}">${esc(o.title)}</option>`).join('')}</select></label><button class="primary-btn">Add to Team watchlist</button></form><div class="module-stack">${(shared.opportunities||[]).map(o=>`<div class="module-row"><h4>${esc(o.title)}</h4><button class="mini-btn" data-org-watch-remove="${esc(o.id)}" data-org-id="${id}">Remove</button></div>`).join('')||notice('No shared opportunities yet.')}</div><h3>Members</h3><div class="module-stack">${data.members.map(m=>`<div class="module-row"><h4>${esc(m.email)}</h4><p>${esc(m.role)} • ${esc(m.provision_source||'manual')} • last login ${dateLabel(m.last_login_at)}</p>${m.role!=='owner'&&org.role==='owner'?`<div class="toolbar"><button class="mini-btn" data-member-role="admin" data-org-id="${id}" data-member-id="${m.user_id}">Admin</button><button class="mini-btn" data-member-role="analyst" data-org-id="${id}" data-member-id="${m.user_id}">Analyst</button><button class="mini-btn" data-member-role="member" data-org-id="${id}" data-member-id="${m.user_id}">Member</button><button class="mini-btn" data-member-remove="${m.user_id}" data-org-id="${id}">Remove</button><button class="mini-btn" data-transfer-owner="${m.user_id}" data-org-id="${id}">Transfer ownership</button></div>`:''}</div>`).join('')}</div><h3>Invite member</h3><form id="inviteForm" class="form-grid"><label>Email<input type="email" name="email" required></label><label>Role<select name="role"><option value="member">Member</option><option value="analyst">Analyst</option><option value="admin">Admin</option></select></label><button class="primary-btn">Create invitation</button></form><div id="inviteResult"></div><h3>Branding</h3><form id="brandingForm" class="form-grid"><label>Brand name<input name="brand_name" value="${esc(org.brand_name||'Cashh Radar')}"></label><label>Accent<input name="accent_color" value="${esc(org.accent_color||'#00E5C2')}" pattern="#[0-9A-Fa-f]{6}"></label><label>Logo URL<input name="logo_url" value="${esc(org.logo_url||'')}"></label><label>Custom domain<input name="custom_domain" value="${esc(org.custom_domain||'')}"></label><button class="primary-btn">Save tenant branding</button></form><h3>Signed webhooks</h3><form id="webhookForm" class="form-grid"><label>HTTPS destination<input name="url" type="url" required placeholder="https://example.com/cashh-webhook"></label><button class="primary-btn">Create webhook</button></form><div class="module-stack">${(hooks.webhooks||[]).map(w=>`<div class="module-row"><b>${esc(w.url)}</b><span>${esc((w.events||[]).join(', '))}</span></div>`).join('')||notice('No webhooks yet.')}</div><h3>SCIM provisioning</h3><button class="ghost-btn" data-create-scim="${id}">Create SCIM token</button><div id="scimResult"></div>${org.role==='owner'?`<h3>Danger zone</h3><form id="deleteOrgForm" class="form-grid"><label>Password<input name="password" type="password" required></label><label>Type DELETE<input name="confirmation" required></label><button class="mini-btn">Delete workspace</button></form>`:''}<div id="orgMsg"></div>`);
    $('#orgWatchForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);try{await api(`/api/organizations/${id}/watchlist/${encodeURIComponent(f.get('opportunity_id'))}`,{method:'POST'});toast('Added to Team watchlist');openOrganization(id)}catch(err){$('#orgMsg').innerHTML=notice(err.message,'danger')}});
    $('#inviteForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);try{const d=await api(`/api/organizations/${id}/invites`,{method:'POST',body:JSON.stringify({email:f.get('email'),role:f.get('role')})});$('#inviteResult').innerHTML=`<div class="notice success">Invite created (${esc(d.email_delivery)}).<div class="codebox">${esc(d.invite_url)}</div></div>`}catch(err){$('#inviteResult').innerHTML=notice(err.message,'danger')}});
    $('#brandingForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);try{await api(`/api/organizations/${id}/branding`,{method:'PUT',body:JSON.stringify({brand_name:f.get('brand_name'),accent_color:f.get('accent_color'),logo_url:f.get('logo_url')||null,custom_domain:f.get('custom_domain')||null})});$('#orgMsg').innerHTML=notice('Workspace branding saved.','success')}catch(err){$('#orgMsg').innerHTML=notice(err.message,'danger')}});
    $('#webhookForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);try{const d=await api(`/api/organizations/${id}/webhooks`,{method:'POST',body:JSON.stringify({url:f.get('url'),events:['*']})});$('#orgMsg').innerHTML=notice('Webhook created. Copy signing secret now.','success')+`<div class="codebox">${esc(d.signing_secret)}</div>`}catch(err){$('#orgMsg').innerHTML=notice(err.message,'danger')}});
    if($('#deleteOrgForm'))$('#deleteOrgForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);try{await api(`/api/organizations/${id}`,{method:'DELETE',body:JSON.stringify({password:f.get('password'),confirmation:f.get('confirmation')})});toast('Workspace deleted');openDeveloper()}catch(err){$('#orgMsg').innerHTML=notice(err.message,'danger')}})
  }

  async function openPrivacy(){
    if(!state.me){openAccount();return}const sec=await api('/api/account/security');
    openModalHtml(`<span class="eyebrow">DATA, PRIVACY & SECURITY</span><h2 id="modalTitle">Your account controls</h2><p>Export your data, secure your login, change your password, or permanently delete the account. Read <a class="source-link" href="/privacy" target="_blank">Privacy</a>, <a class="source-link" href="/terms" target="_blank">Terms</a>, and <a class="source-link" href="/disclosures" target="_blank">Disclosures</a>.</p><div class="toolbar"><a class="primary-btn" href="/api/account/export" target="_blank">Export my data</a></div><h3>Email verification</h3><p>${sec.email_verified?'✓ Email verified':'Email not yet verified'}${sec.email_verification_required?' • required for production sign-in':''}</p>${!sec.email_verified?'<button class="ghost-btn" data-verify-email>Send verification email</button>':''}<h3>Two-step login</h3><form id="twoStepSettingsForm" class="form-grid"><label>Password<input name="password" type="password" required></label><label>Setting<select name="enabled"><option value="true" ${sec.two_step_enabled?'selected':''}>Enabled</option><option value="false" ${!sec.two_step_enabled?'selected':''}>Disabled</option></select></label><button class="primary-btn">Save security setting</button></form><p class="opp-sub">Two-step login uses a one-time code sent by email. SMTP must be configured before enabling it in production.</p><h3>Change password</h3><form id="passwordForm" class="form-grid"><label>Current password<input name="current" type="password" required></label><label>New password<input name="next" type="password" minlength="10" required></label><button class="primary-btn" type="submit">Change password</button></form><h3>Delete account</h3><p class="opp-sub">Permanent. Owned Team workspaces must be transferred or deleted first.</p><form id="deleteAccountForm" class="form-grid"><label>Password<input name="password" type="password" required></label><label>Confirmation<input name="confirmation" required placeholder="DELETE"></label><button class="mini-btn" type="submit">Delete permanently</button></form><div id="privacyMsg"></div>`);
    $('#twoStepSettingsForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);try{await api('/api/account/security/two-step',{method:'PUT',body:JSON.stringify({enabled:f.get('enabled')==='true',password:f.get('password')})});$('#privacyMsg').innerHTML=notice('Security setting saved.','success');await loadMe()}catch(err){$('#privacyMsg').innerHTML=notice(err.message,'danger')}});
    $('#passwordForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);try{await api('/api/account/password',{method:'POST',body:JSON.stringify({current_password:f.get('current'),new_password:f.get('next')})});$('#privacyMsg').innerHTML=notice('Password changed.','success')}catch(err){$('#privacyMsg').innerHTML=notice(err.message,'danger')}});
    $('#deleteAccountForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);try{await api('/api/account',{method:'DELETE',body:JSON.stringify({password:f.get('password'),confirmation:f.get('confirmation')})});location.reload()}catch(err){$('#privacyMsg').innerHTML=notice(err.message,'danger')}})
  }

  const titles={home:['Opportunity Radar','Ranked opportunities with evidence, freshness, risk, and execution tools.'],fast:['Fast Money','Records with a modeled short path to first income; unknown timing is not guessed.'],remote:['Remote Income','Remote-first opportunities filtered for digital execution.'],business:['Build a Business','Service and digital-business paths with stronger scalability potential.'],explorer:['Opportunity Explorer','Use filters and scoring dimensions across sourced and illustrative records.'],compare:['Opportunity Battle','Compare top alternatives side by side.'],sources:['Source Monitor','Inspect connector state, refresh history, and source policy guardrails.']};
  function setView(v){state.view=v;$$('.nav-item[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===v));$('#viewTitle').textContent=titles[v][0];$('#viewSubtitle').textContent=titles[v][1];render();track('view_change',{view:v})}

  document.addEventListener('click',async e=>{
    const view=e.target.closest('[data-view]')?.dataset.view;if(view){setView(view);$('#sidebar').classList.remove('open');return}
    const next=e.target.closest('[data-onboard-next]')?.dataset.onboardNext;if(next){const n=Number(next);if(n>=onboardingSteps.length){localStorage.setItem('cashh_onboarded','1');closeModal();}else openOnboarding(n);return}
    const prev=e.target.closest('[data-onboard-prev]')?.dataset.onboardPrev;if(prev!==undefined){openOnboarding(Number(prev));return}
    if(e.target.closest('[data-onboard-skip]')){localStorage.setItem('cashh_onboarded','1');closeModal();return}
    const type=e.target.closest('[data-open]')?.dataset.open;if(type){ if(type==='watchlist')openWatchlist(); else if(type==='advisor')openAdvisor(); else if(type==='roadmap')openRoadmaps(); else if(type==='studio')openStudio(); else if(type==='alerts')openAlerts(); else if(type==='tracker')openTracker(); else if(type==='plans')openPlans(); else if(type==='pulse')openPulse(); else if(type==='growth')openGrowth(); else if(type==='developer')openDeveloper(); else if(type==='privacy')openPrivacy(); else if(type==='admin')openAdmin(); return }
    const ds=e.target.closest('[data-delete-search]')?.dataset.deleteSearch;if(ds){try{await api(`/api/saved-searches/${ds}`,{method:'DELETE'});toast('Saved search deleted');openPulse()}catch(err){toast(err.message)}return}
    const da=e.target.closest('[data-delete-alert]')?.dataset.deleteAlert;if(da){try{await api(`/api/alerts/${da}`,{method:'DELETE'});toast('Alert rule deleted');openAlerts()}catch(err){toast(err.message)}return}
    if(e.target.closest('[data-verify-email]')){try{const d=await api('/api/account/email-verification/request',{method:'POST',body:JSON.stringify({email:state.me.email})});toast(d.message||'Verification email requested')}catch(err){toast(err.message)}return}
    const tw=e.target.closest('[data-transfer-owner]');if(tw){try{await api(`/api/organizations/${tw.dataset.orgId}/owner`,{method:'PUT',body:JSON.stringify({new_owner_user_id:Number(tw.dataset.transferOwner)})});toast('Ownership transferred');openDeveloper()}catch(err){toast(err.message)}return}
    const ow=e.target.closest('[data-org-watch-remove]');if(ow){try{await api(`/api/organizations/${ow.dataset.orgId}/watchlist/${encodeURIComponent(ow.dataset.orgWatchRemove)}`,{method:'DELETE'});toast('Removed from Team watchlist');openOrganization(ow.dataset.orgId)}catch(err){toast(err.message)}return}
    const sc=e.target.closest('[data-create-scim]')?.dataset.createScim;if(sc){try{const d=await api(`/api/organizations/${sc}/scim-tokens`,{method:'POST',body:JSON.stringify({name:'SCIM provisioning'})});$('#scimResult').innerHTML=notice('SCIM token created. Copy it now.','success')+`<div class="codebox">${esc(d.token)}</div>`}catch(err){toast(err.message)}return}
    const rk=e.target.closest('[data-revoke-key]')?.dataset.revokeKey;if(rk){try{await api(`/api/api-keys/${rk}`,{method:'DELETE'});toast('API key revoked');openDeveloper()}catch(err){toast(err.message)}return}
    const om=e.target.closest('[data-org-manage]')?.dataset.orgManage;if(om){openOrganization(om);return}
    const mr=e.target.closest('[data-member-role]');if(mr){try{await api(`/api/organizations/${mr.dataset.orgId}/members/${mr.dataset.memberId}`,{method:'PUT',body:JSON.stringify({role:mr.dataset.memberRole})});toast('Member role updated');openOrganization(mr.dataset.orgId)}catch(err){toast(err.message)}return}
    const rm=e.target.closest('[data-member-remove]');if(rm){try{await api(`/api/organizations/${rm.dataset.orgId}/members/${rm.dataset.memberRemove}`,{method:'DELETE'});toast('Member removed');openOrganization(rm.dataset.orgId)}catch(err){toast(err.message)}return}
    const pr=e.target.closest('[data-provider-request]')?.dataset.providerRequest;if(pr){try{await api('/api/provider-leads',{method:'POST',body:JSON.stringify({provider_id:Number(pr),note:'User requested an introduction from Growth & Partners.'})});toast('Provider request submitted');openGrowth()}catch(err){toast(err.message)}return}
    const ls=e.target.closest('[data-lead-status]');if(ls){try{await api(`/api/admin/provider-leads/${ls.dataset.leadId}`,{method:'PUT',body:JSON.stringify({status:ls.dataset.leadStatus,admin_note:''})});toast('Lead status updated');openAdmin()}catch(err){toast(err.message)}return}
    const job=e.target.closest('[data-run-job]')?.dataset.runJob;if(job){try{const d=await api(`/api/admin/jobs/${job}/run`,{method:'POST'});toast(`${job}: ${d.status}`);openAdmin()}catch(err){toast(err.message)}return}
    const save=e.target.closest('[data-save]')?.dataset.save;if(save){await toggleSave(save);return}
    const detail=e.target.closest('[data-detail]')?.dataset.detail;if(detail){closeModal();openDetail(detail);return}
    const rid=e.target.closest('[data-make-roadmap]')?.dataset.makeRoadmap;if(rid){await makeRoadmap(rid);return}
    const oid=e.target.closest('[data-make-outreach]')?.dataset.makeOutreach;if(oid){await makeOutreach(oid);return}
    const xid=e.target.closest('[data-log-outcome]')?.dataset.logOutcome;if(xid){logOutcome(xid);return}
    const sw=e.target.closest('[data-auth-switch]')?.dataset.authSwitch;if(sw){openAccount(sw);return}
    if(e.target.closest('[data-password-reset]')){openPasswordReset();return}
    const rt=e.target.closest('[data-reset-confirm-token]')?.dataset.resetConfirmToken;if(rt){openPasswordResetConfirm(rt);return}
    if(e.target.closest('[data-account-profile]')){openProfile();return}
    if(e.target.closest('[data-logout]')){try{await api('/api/logout',{method:'POST'});state.me=null;state.csrf='';state.saved.clear();await loadMe();closeModal();render();toast('Signed out.')}catch(err){toast(err.message)}return}
    if(e.target.closest('[data-evaluate-alerts]')){try{const d=await api('/api/alerts/evaluate',{method:'POST'});toast(`${d.created} alert(s) created`);openAlerts()}catch(err){toast(err.message)}return}
    const plan=e.target.closest('[data-checkout]')?.dataset.checkout;if(plan){if(!state.me){openAccount();return}try{const d=await api('/api/billing/checkout',{method:'POST',body:JSON.stringify({plan})});if(d.checkout_url)location.href=d.checkout_url}catch(err){$('#billingMsg').innerHTML=notice(err.message,'danger')}return}
    if(e.target.closest('[data-billing-portal]')){if(!state.me){openAccount();return}try{const d=await api('/api/billing/portal',{method:'POST'});if(d.url)location.href=d.url}catch(err){$('#billingMsg').innerHTML=notice(err.message,'danger')}return}
    const src=e.target.closest('[data-refresh-source]')?.dataset.refreshSource;if(src){try{const d=await api(`/api/admin/sources/${src}/refresh`,{method:'POST'});toast(`Refreshed: ${d.normalized} normalized`);await loadRecords();openAdmin()}catch(err){$('#adminMsg').innerHTML=notice(err.message,'danger')}return}
    const subBtn=e.target.closest('[data-submission-decision]');if(subBtn){try{await api(`/api/admin/submissions/${subBtn.dataset.submissionId}/decision?decision=${encodeURIComponent(subBtn.dataset.submissionDecision)}`,{method:'POST'});toast('Submission reviewed');openAdmin()}catch(err){$('#adminMsg').innerHTML=notice(err.message,'danger')}return}
    const ver=e.target.closest('[data-admin-verify]')?.dataset.adminVerify;if(ver){try{await api(`/api/admin/opportunities/${encodeURIComponent(ver)}/verify`,{method:'POST'});toast('Marked verified');await loadRecords();openAdmin()}catch(err){$('#adminMsg').innerHTML=notice(err.message,'danger')}return}
    const blk=e.target.closest('[data-admin-block]')?.dataset.adminBlock;if(blk){try{await api(`/api/admin/opportunities/${encodeURIComponent(blk)}/block`,{method:'POST'});toast('Opportunity blocked');await loadRecords();openAdmin()}catch(err){$('#adminMsg').innerHTML=notice(err.message,'danger')}return}
  });

  $('#accountBtn').addEventListener('click',()=>openAccount());
  $('#closeDrawer').addEventListener('click',closeDetail);backdrop.addEventListener('click',closeDetail);$('#closeModal').addEventListener('click',closeModal);
  $('#mobileMenuBtn').addEventListener('click',()=>$('#sidebar').classList.toggle('open'));
  $('#filterToggle').addEventListener('click',()=>filters.classList.toggle('hidden'));
  $('#sortSelect').addEventListener('change',e=>{state.sort=e.target.value;render()});
  $('#workFilter').addEventListener('change',e=>{state.work=e.target.value;render()});$('#costFilter').addEventListener('change',e=>{state.cost=e.target.value;render()});$('#experienceFilter').addEventListener('change',e=>{state.exp=e.target.value;render()});$('#trustFilter').addEventListener('change',e=>{state.trust=e.target.value;render()});
  $('#goalBtn').addEventListener('click',()=>openAdvisor($('#goalInput').value));$('#goalInput').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();openAdvisor(e.target.value)}});
  $$('[data-goal]').forEach(b=>b.addEventListener('click',()=>{const map={fast:'I need the fastest realistic path to first income.',remote:'I need remote income and I am open to entry-level work.',lowcost:'I need opportunities with zero or near-zero startup cost.',durable:'I want durable income with lower automation displacement risk.'};openAdvisor(map[b.dataset.goal])}));
  document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeDetail();closeModal()}});

  (async()=>{try{await loadMe();await loadRecords();const qs=new URLSearchParams(location.search);if(qs.get('billing')==='success')toast('Billing completed. Your plan updates after the verified webhook arrives.');if(qs.get('reset_token'))setTimeout(()=>openPasswordResetConfirm(qs.get('reset_token')),100);if(qs.get('verify_email')){try{await api('/api/account/email-verification/confirm',{method:'POST',body:JSON.stringify({token:qs.get('verify_email')})});const u=new URL(location.href);u.searchParams.delete('verify_email');history.replaceState({},'',u.pathname+u.search);toast('Email verified. You can sign in.')}catch(err){toast(`Email verification: ${err.message}`)}}if(qs.get('org_invite')){if(state.me)await maybeAcceptOrganizationInvite();else setTimeout(()=>openAccount('signin'),120)}track('app_open',{path:location.pathname});if(!localStorage.getItem('cashh_onboarded')&&!qs.get('reset_token')&&!qs.get('org_invite'))setTimeout(()=>openOnboarding(0),180)}catch(e){list.innerHTML=notice(`Cashh Radar could not initialize: ${e.message}`,'danger')}})();
})();

if('serviceWorker' in navigator){window.addEventListener('load',()=>navigator.serviceWorker.register('/static/sw.js').catch(()=>{}));}
