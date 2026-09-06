function focusCard(p){
  const type=recommendedScript(p),email=p.email||'',body=effectiveBody(p),subject=effectiveSubject(p);
  const verified=!!(p.verified||p.sentAt||p.status==='SENT'||p.status==='REPLIED'),prepared=!!p.preparedAt;
  const hasEmail=/.+@.+\..+/.test(email),gmailReady=!!loadSettings().clientId;
  const isReply=p.status==='REPLIED',isDue=p.status==='SENT'&&isFollowDue(p);
  let stage=1,nowTitle='Verify this lead',nowText='Open the real listing and confirm it is still active.',nowAction='openVerify',nowLabel='Open listing to verify';
  if(verified&&!hasEmail){stage=2;nowTitle='Use the contact route';nowText='No verified email is saved. Copy the prepared message and open the real listing or DM route.';nowAction=p.url?'sourceContact':'focusEmail';nowLabel=p.url?'Copy message + open contact route':'Add verified email';}
  if(verified&&hasEmail&&!prepared){stage=3;nowTitle=isReply?'Reply now':isDue?`${type==='FU2'?'Final follow-up':'Follow up'} now`:'Draft the email';nowText=gmailReady?'One tap creates a Gmail draft with the PNG card attached. Review it before sending.':'One tap opens your Android email app with To, Subject and Body already filled.';nowAction='primarySend';nowLabel=gmailReady?'Create ready Gmail draft + image':'Open ready email';}
  if(prepared){stage=4;nowTitle='Confirm after you send';nowText='Once you actually press Send in Gmail/email, come back and tap the button below.';nowAction='sentNext';nowLabel='✓ I sent it — next best action';}
  if((isReply||isDue)&&!hasEmail&&p.url){stage=2;nowTitle=isReply?'Reply through the existing contact route':`${type==='FU2'?'Final follow-up':'Follow up'} through the existing route`;nowText='The message is already prepared. Copy it and reopen the original contact route.';nowAction='sourceContact';nowLabel='Copy message + open contact route';}
  return `<article class="panel hero" data-id="${esc(p.id)}">
    <div class="heroTop"><div class="rank">#${esc(p.priority)} of 200 · ${esc(p.id)} · Wave ${esc(p.wave)}</div><span class="badge ${statusClass(p.status)}">${esc(p.status)}</span></div>
    <h2>${esc(p.prospect||'Discovery slot — find a live prospect')}</h2>
    <div class="meta">${esc(p.source)} ${p.comp?`· <span class="pay">${esc(p.comp)}</span>`:''}</div>
    <div class="need"><b>Why they need help:</b><br>${esc(p.need||'Open the source and verify the live need before contacting.')}</div>

    <section class="nowBox" aria-label="Next best action">
      <div class="nowTop"><span class="nowStep">STEP ${stage} OF 4</span><strong>${esc(nowTitle)}</strong></div>
      <p>${esc(nowText)}</p>
      <button class="btn primary big" style="width:100%" data-action="${esc(nowAction)}">${esc(nowLabel)}</button>
      ${isReply?'<div class="priorityFlag">↩ A prospect replied — this is prioritized ahead of new outreach.</div>':''}
      ${isDue?`<div class="priorityFlag">↻ Follow-up due ${followDueDate(p).toLocaleDateString()} — surfaced before new outreach.</div>`:''}
    </section>

    <div class="stepRail" aria-label="Workflow progress"><span class="${stage>1?'done':stage===1?'active':''}">1 Verify</span><span class="${stage>2?'done':stage===2?'active':''}">2 Contact</span><span class="${stage>3?'done':stage===3?'active':''}">3 Draft</span><span class="${stage===4?'active':''}">4 Confirm</span></div>

    <section class="step ${verified?'completeStep':''}">
      <div class="stepHead"><span class="num">1</span><strong>Verify the lead</strong></div>
      <p class="hint">Open the real source and confirm it is still active. Previously contacted prospects count as already verified.</p>
      <div class="sourceRow">${p.url?`<a class="btn orange" href="${esc(p.url)}" target="_blank" rel="noopener">Open source</a>`:`<button class="btn soft" disabled>No source URL</button>`}<button class="btn ${verified?'good':'soft'}" data-action="verify">${verified?'✓ Verified':'Mark verified'}</button></div>
    </section>

    <section class="step ${hasEmail?'completeStep':''}">
      <div class="stepHead"><span class="num">2</span><strong>Contact route</strong></div>
      <p class="hint">If a real email is published, paste it once. If not, use the listing/DM/application route instead.</p>
      <div class="emailWrap"><input id="focusEmail" type="email" autocomplete="email" inputmode="email" value="${esc(email)}" placeholder="verified@email.com"><span class="emailOk">${hasEmail?'✓':''}</span></div>
      ${!hasEmail&&p.url?`<button class="btn soft" style="margin-top:8px;width:100%" data-action="sourceContact">Copy prepared message + open listing / DM</button>`:''}
    </section>

    <section class="step">
      <div class="stepHead"><span class="num">3</span><strong>Message is already written</strong></div>
      <p class="hint">The app automatically recommends the right stage: initial, follow-up, reply qualification, or close.</p>
      <div class="quickbar" role="group" aria-label="Message type">
        <button class="chip ${type==='INIT'?'active':''}" data-script="INIT">Initial</button>
        <button class="chip ${type==='FU1'?'active':''}" data-script="FU1">Follow-up 1</button>
        <button class="chip ${type==='FU2'?'active':''}" data-script="FU2">Follow-up 2</button>
        <button class="chip ${type==='QUALIFY'?'active':''}" data-script="QUALIFY">Qualify reply</button>
        <button class="chip ${type==='CLOSE'?'active':''}" data-script="CLOSE">Close</button>
      </div>
      <div class="messagePreview" id="messagePreview">${esc(body)}</div>
      <button class="btn soft" style="margin-top:7px;width:100%" data-action="toggleEdit">Edit subject / message</button>
      <div class="editBox" id="editBox"><label>Subject<input id="focusSubject" value="${esc(subject)}"></label><label>Message<textarea id="focusMessage">${esc(body)}</textarea></label></div>
    </section>

    <section class="step sendBox">
      <div class="stepHead"><span class="num">4</span><strong>Send, then confirm</strong></div>
      <button class="btn ${hasEmail?'primary':'navy'} big" style="width:100%" data-action="primarySend">${hasEmail?(gmailReady?'Create Gmail draft + image':'Open ready email'):(p.url?'Copy message + open source':'Add verified email')}</button>
      <div class="row" style="margin-top:8px"><button class="btn soft" data-action="share">Share + image</button><button class="btn soft" data-action="previewImage">Save outreach image</button></div>
      <p class="sendNote">${gmailReady?'Gmail attachment mode is ready. The app creates a draft for review; it never presses Send for you.':'Set up Gmail once in ⚙ Settings if you want recipient + subject + body + PNG attachment assembled into one Gmail draft.'}</p>
      <div class="confirm ${prepared?'show':''}"><button class="btn good" data-action="sentNext">✓ I sent it — next best action</button><button class="btn soft" data-action="notSent">Not sent yet</button></div>
    </section>

    <div class="divider"></div>
    <div class="navrow"><button class="btn bad" data-action="skip">Skip / bad fit</button><button class="btn soft" data-action="next">Next without changing status</button></div>
    <p class="mini" style="margin-bottom:0"><b>Safety check:</b> ${esc(p.risk||'Verify identity, scope and pay before sensitive information or substantial work.')}</p>
  </article>`;
}
function renderFocus(){ensureCurrent();const p=merge(data.find(x=>x.id===currentId));$('focusView').innerHTML=focusCard(p);bindFocus(p);}
function bindFocus(p){
  const root=$('focusView'),email=$('focusEmail'),subject=$('focusSubject'),message=$('focusMessage');
  if(email)email.addEventListener('change',()=>save(p.id,{email:email.value.trim()},false));
  root.querySelectorAll('[data-script]').forEach(b=>b.addEventListener('click',()=>{const type=b.dataset.script;const fresh=merge(data.find(x=>x.id===p.id));const body=scripts[type](fresh),subj=subjectForScript(fresh,type);save(p.id,{scriptType:type,message:body,messageScript:type,subject:subj,subjectScript:type},false);renderFocus()}));
  root.querySelectorAll('[data-action]').forEach(b=>b.addEventListener('click',async()=>{
    const a=b.dataset.action;const fresh=()=>merge(data.find(x=>x.id===p.id));
    if(a==='openVerify'){if(p.url){window.open(p.url,'_blank','noopener');toast('Check the listing, then tap Mark verified.');}else toast('No source URL is saved for this row.');return;}
    if(a==='focusEmail'){const e=$('focusEmail');if(e){e.focus();e.scrollIntoView({behavior:'smooth',block:'center'});}return;}
    if(a==='verify'){const next=!fresh().verified;save(p.id,{verified:next},false);toast(next?'Lead marked verified.':'Verification removed.');renderFocus();return;}
    if(a==='sourceContact'){saveDraftFields(p);const d=getDraft(p.id);try{await navigator.clipboard.writeText(d.body);toast('Message copied. Opening the contact route…')}catch{toast('Opening the contact route. Message is ready above.')}if(p.url)window.open(p.url,'_blank','noopener');return;}
    if(a==='toggleEdit'){$('editBox').classList.toggle('open');return;}
    if(a==='next'){currentId=nextWorkable(p.id).id;renderFocus();return;}
    if(a==='skip'){save(p.id,{status:'SKIP',skipAt:new Date().toISOString()},false);currentId=nextWorkable(p.id).id;render();return;}
    if(a==='notSent'){save(p.id,{preparedAt:null},false);renderFocus();return;}
    if(a==='sentNext'){
      saveDraftFields(p);const fp=fresh(),type=recommendedScript(fp);
      save(p.id,{status:'SENT',sentAt:new Date().toISOString(),preparedAt:null,lastContactType:type,scriptType:type},false);
      currentId=nextWorkable(p.id).id;toast('Marked sent. Next best action loaded.');render();return;
    }
    if(a==='share'){saveDraftFields(p);return shareDraft(getDraft(p.id));}
    if(a==='previewImage'){saveDraftFields(p);const f=await makeImage(getDraft(p.id));downloadFile(f);toast('Prospect image saved.');return;}
    if(a==='primarySend'){
      saveDraftFields(p);const d=getDraft(p.id);
      if(!d.email){
        if(d.p.url){try{await navigator.clipboard.writeText(d.body);toast('Message copied. Opening source / DM route…')}catch{toast('Opening source. Your message is ready above.')}window.open(d.p.url,'_blank','noopener');}
        else toast('Add a verified email first.');
        return;
      }
      save(p.id,{preparedAt:new Date().toISOString()},false);
      if(loadSettings().clientId){await createGmailDraft(d)}else openMail(d);
      renderFocus();
    }
  }));
  if(subject)subject.addEventListener('change',()=>{const type=recommendedScript(merge(data.find(x=>x.id===p.id)));save(p.id,{subject:subject.value,subjectScript:type},false)});
  if(message)message.addEventListener('change',()=>{const type=recommendedScript(merge(data.find(x=>x.id===p.id)));save(p.id,{message:message.value,messageScript:type},false);$('messagePreview').textContent=message.value});
}
function saveDraftFields(p){const e=$('focusEmail'),s=$('focusSubject'),m=$('focusMessage'),fresh=merge(data.find(x=>x.id===p.id)),type=recommendedScript(fresh);save(p.id,{email:e?e.value.trim():(fresh.email||''),subject:s?s.value:effectiveSubject(fresh),subjectScript:type,message:m?m.value:effectiveBody(fresh),messageScript:type},false)}
function getDraft(id){const p=merge(data.find(x=>x.id===id));return{p,email:p.email||'',subject:effectiveSubject(p),body:effectiveBody(p)}}
function openMail(d){if(!d.email)return toast('Add a verified email first.');location.href=`mailto:${encodeURIComponent(d.email)}?subject=${encodeURIComponent(d.subject)}&body=${encodeURIComponent(d.body)}`}
function queueCard(p){const due=p.status==='SENT'&&isFollowDue(p),reply=p.status==='REPLIED';return `<article class="qitem ${reply?'priorityItem':due?'dueItem':''}"><div class="qitemTop"><span class="rank">#${esc(p.priority)} · ${esc(p.id)}</span><span class="badge ${statusClass(p.status)}">${reply?'REPLY':due?'FOLLOW-UP DUE':esc(p.status)}</span></div><h3>${esc(p.prospect||'Discovery slot')}</h3><div class="meta">${esc(p.source)}${p.comp?' · '+esc(p.comp):''}</div><div class="qactions"><button class="btn primary" data-open="${esc(p.id)}">${reply?'Reply now':due?'Follow up now':'Work this prospect'}</button>${p.url?`<a class="btn orange" href="${esc(p.url)}" target="_blank" rel="noopener">Source</a>`:''}</div></article>`}
function queueSort(a){return [...a].sort((x,y)=>{const xr=x.status==='REPLIED'?0:(x.status==='SENT'&&isFollowDue(x)?1:2),yr=y.status==='REPLIED'?0:(y.status==='SENT'&&isFollowDue(y)?1:2);return xr-yr||(x.priority||999)-(y.priority||999)})}
function renderQueue(){const a=all();$('queueView').innerHTML=`<div class="panel queueIntro"><b>Priority order:</b> replies first, then follow-ups due, then new outreach.</div><div class="queueToolbar"><input id="queueSearch" placeholder="Search all 200"><select id="queueStatus"><option value="">All statuses</option><option>CONTACT READY</option><option>DISCOVERY SLOT</option><option>SENT</option><option>REPLIED</option><option>WON / PAID</option><option>SKIP</option></select><select id="queueWave"><option value="">All waves</option><option>1</option><option>2</option><option>3</option><option>4</option></select></div><div id="queueList"></div>`;const redraw=()=>{const q=$('queueSearch').value.toLowerCase(),s=$('queueStatus').value,w=$('queueWave').value;const f=queueSort(a.filter(p=>(!q||JSON.stringify(p).toLowerCase().includes(q))&&(!s||p.status===s)&&(!w||String(p.wave)===w)));$('queueList').innerHTML=f.map(queueCard).join('')||'<div class="empty">No matches.</div>';$('queueList').querySelectorAll('[data-open]').forEach(b=>b.addEventListener('click',()=>{currentId=b.dataset.open;switchTab('focus')}));};['queueSearch','queueStatus','queueWave'].forEach(id=>$(id).addEventListener('input',redraw));redraw();}
function followups(){return all().filter(p=>p.status==='SENT'&&p.sentAt&&isFollowDue(p)).sort((a,b)=>followDueDate(a)-followDueDate(b))}
function renderFollow(){const a=followups();$('followView').innerHTML=`<div class="panel"><h2 style="margin-top:0;color:var(--navy)">Follow-ups due</h2><p class="mini">Only prospects you actually marked Sent appear here. Due dates use business days: first follow-up after 2 business days; final follow-up 5 business days after Follow-up 1.</p></div><div style="height:8px"></div>${a.map(p=>{const type=p.lastContactType==='FU1'?'FU2':'FU1';return `<article class="qitem dueItem"><div class="qitemTop"><span class="rank">${esc(p.id)}</span><span class="badge sent">${type==='FU2'?'FINAL FOLLOW-UP':'FOLLOW-UP 1'}</span></div><h3>${esc(p.prospect||p.id)}</h3><div class="meta">Last sent ${new Date(p.sentAt).toLocaleDateString()} · due ${followDueDate(p).toLocaleDateString()}</div><div class="qactions"><button class="btn primary" data-follow="${esc(p.id)}">Write ${type==='FU2'?'final follow-up':'follow-up'}</button>${p.url?`<a class="btn orange" href="${esc(p.url)}" target="_blank" rel="noopener">Source</a>`:''}</div></article>`}).join('')||'<div class="empty">Nothing is due yet.</div>'}`;$('followView').querySelectorAll('[data-follow]').forEach(b=>b.addEventListener('click',()=>{const id=b.dataset.follow,p=merge(data.find(x=>x.id===id)),type=p.lastContactType==='FU1'?'FU2':'FU1';save(id,{scriptType:type,message:scripts[type](p),messageScript:type,subject:subjectForScript(p,type),subjectScript:type},false);currentId=id;switchTab('focus')}));}
function renderStats(){const c=counters(),remaining=200-c.done;$('statsView').innerHTML=`<section class="panel"><h2 style="margin-top:0;color:var(--navy)">Today at a glance</h2><div class="row desktop3"><div class="need"><b>${c.done}</b><br>processed</div><div class="need"><b>${c.sent}</b><br>sent</div><div class="need"><b>${c.replies}</b><br>replies</div><div class="need"><b>${c.due}</b><br>follow-ups due</div><div class="need"><b>${c.won}</b><br>won</div><div class="need"><b>${c.skipped}</b><br>skipped</div><div class="need"><b>${remaining}</b><br>remaining</div></div><div class="divider"></div><button class="btn primary" style="width:100%" id="resumeBtn">Resume next best action</button></section>`;$('resumeBtn').addEventListener('click',()=>{currentId=nextWorkable().id;switchTab('focus')});}
function render(){updateHeader();if(currentTab==='focus')renderFocus();if(currentTab==='queue')renderQueue();if(currentTab==='follow')renderFollow();if(currentTab==='stats')renderStats();}
function switchTab(tab){currentTab=tab;['focus','queue','follow','stats'].forEach(t=>{const view=$(t+'View');view.classList.toggle('open',t===tab);view.style.display=t===tab?'block':'none'});document.querySelectorAll('.bottom [data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));render();window.scrollTo({top:0,behavior:'smooth'});}
