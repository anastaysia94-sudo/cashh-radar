const BASE_SERVICES = [
  {id:'content', icon:'⚡', name:'Business Content Pack', tag:'V5/V6 FINAL OFFER', price:100, time:'confirmed before work begins', summary:'Turn the business’s real services into clear customer-facing content that is ready to post, reuse, and reply with.', deliverables:['10 ready-to-post business posts','custom business graphics','customer follow-up messages','review + customer-message reply templates','stronger calls-to-action']},
  {id:'aeo', icon:'🧭', name:'AI Search Visibility Starter', tag:'HOT 2026 DEMAND', price:149, time:'same-day target', summary:'Turn vague “get me into ChatGPT” anxiety into an honest, deployable starter pack.', deliverables:['AI-readiness checklist','business/entity statement','buyer-question prompt set','schema + FAQ starter','prioritized next fixes']},
  {id:'conversion', icon:'🎯', name:'Website Conversion Rescue', tag:'DIRECT REVENUE', price:149, time:'same-day target', summary:'Fix the page visitors see right before they decide whether to act or disappear forever.', deliverables:['headline + offer rewrite','CTA cleanup','friction audit','trust/proof checklist','mobile conversion notes']},
  {id:'cleanup', icon:'🧹', name:'AI Copy Cleanup', tag:'FASTEST TURNAROUND', price:99, time:'priority turnaround', summary:'Make robotic, repetitive, awkward AI-written copy sound human, specific, and usable.', deliverables:['human-style rewrite','tone cleanup','claim-risk flags','repetition removal','final copy-ready version']},
  {id:'leads', icon:'🔎', name:'Lead Research Mini-Sprint', tag:'SALES READY', price:149, time:'same-day target', summary:'Build a small, evidence-supported prospect set around a clearly defined buyer profile.', deliverables:['qualified prospect batch','source/evidence links','contact-channel notes','priority ranking','outreach angles']},
  {id:'data', icon:'🧼', name:'CRM / Spreadsheet Rescue', tag:'OPERATIONS', price:99, time:'priority turnaround', summary:'Clean the spreadsheet chaos humans somehow keep manufacturing at industrial scale.', deliverables:['dedupe + normalization','column cleanup','status logic','error flags','clean handoff file']},
  {id:'local', icon:'📍', name:'Local Business Quick-Win Pack', tag:'LOCAL GROWTH', price:199, time:'same-day target', summary:'Clarify the highest-impact local visibility and conversion fixes without selling a giant retainer.', deliverables:['local presence audit','Google profile checklist','review friction fixes','homepage clarity edits','30-day priority map']},
  {id:'launch', icon:'🚨', name:'Emergency Launch Bundle', tag:'HIGHEST VALUE', price:249, time:'priority slot', summary:'For a launch that is live or nearly live and has several small digital leaks at once.', deliverables:['landing-page triage','offer + CTA polish','launch checklist','email/social launch copy','analytics + follow-up checklist']}
];

let deferredPrompt = null;
let config = {brand:'Same-Day Digital Fix Desk', paymentUrl:'https://www.paypal.com/invoice/p/#7T6DC9A6WFH3XXCT', paymentUrls:{}, email:'', note:'', prices:{}};
let lead = null;
let currentService = null;
let currentScopeText = '';
let campaignRows = [];

const $ = (id) => document.getElementById(id);
const money = n => `$${Number(n).toFixed(0)}`;
const safeUrl = (value) => { try { const u = new URL(String(value || '').trim()); return /^https?:$/.test(u.protocol) ? u.toString() : ''; } catch { return ''; } };
const safeEmail = (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value || '') ? value.trim() : '';
const compact = (value,max=700) => String(value || '').replace(/[\u0000-\u001f\u007f]/g,' ').replace(/\s+/g,' ').trim().slice(0,max);
const encodeObj = obj => btoa(unescape(encodeURIComponent(JSON.stringify(obj)))).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
const decodeObj = str => { try { const pad='='.repeat((4-str.length%4)%4); return JSON.parse(decodeURIComponent(escape(atob(str.replace(/-/g,'+').replace(/_/g,'/')+pad)))); } catch { return null; } };
const escapeHtml = (str='') => String(str).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));

function loadConfig(){
  const p = new URLSearchParams(location.search);
  const parsed = p.get('cfg') ? decodeObj(p.get('cfg')) : null;
  if (parsed && typeof parsed === 'object') {
    const urls={};
    if(parsed.paymentUrls && typeof parsed.paymentUrls==='object') BASE_SERVICES.forEach(s=>urls[s.id]=safeUrl(parsed.paymentUrls[s.id] || ''));
    config = {
      brand: compact(parsed.brand || config.brand,70),
      paymentUrl: safeUrl(parsed.paymentUrl || ''),
      paymentUrls: urls,
      email: safeEmail(parsed.email || ''),
      note: compact(parsed.note || '',140),
      prices: parsed.prices && typeof parsed.prices === 'object' ? parsed.prices : {}
    };
  }
  $('brandName').textContent = config.brand;
  $('footerBrand').textContent = config.brand;
}

function loadLead(){
  const p=new URLSearchParams(location.search);
  const parsed=p.get('lead') ? decodeObj(p.get('lead')) : null;
  if(!parsed || typeof parsed!=='object') return;
  const serviceId=BASE_SERVICES.some(s=>s.id===parsed.serviceId) ? parsed.serviceId : inferService(`${parsed.problem||''} ${parsed.evidence||''}`);
  lead={
    businessName:compact(parsed.businessName,100), businessType:compact(parsed.businessType,80), website:safeUrl(parsed.website||''),
    problem:compact(parsed.problem,700), evidence:compact(parsed.evidence,700), sourceUrl:safeUrl(parsed.sourceUrl||''), serviceId
  };
  if(!lead.businessName && !lead.problem) lead=null;
}

function services(){
  return BASE_SERVICES.map(s => ({...s, price: Math.max(1,Number(config.prices[s.id] || s.price))}));
}

function getService(id){ return services().find(s=>s.id===id) || services()[0]; }
function paymentFor(id){ return safeUrl(config.paymentUrls?.[id] || '') || config.paymentUrl; }

function inferService(text=''){
  const t=String(text).toLowerCase();
  const rules=[
    ['launch',['launch','going live','prelaunch','pre-launch','release']],
    ['data',['spreadsheet','crm','duplicate','dedupe','data cleanup','csv','excel','sheets']],
    ['leads',['lead list','prospect','outreach list','contacts','lead generation','qualified leads']],
    ['cleanup',['ai copy','chatgpt copy','robotic','humanize','rewrite','awkward copy']],
    ['aeo',['chatgpt','ai search','answer engine','aeo','ai overview','llm','generative search']],
    ['local',['google business','google profile','local seo','reviews','maps','local visibility']],
    ['conversion',['homepage','landing page','cta','conversion','website copy','offer','bounce','checkout']]
  ];
  for(const [id,terms] of rules) if(terms.some(k=>t.includes(k))) return id;
  return 'conversion';
}

function renderServices(){
  const grid = $('serviceGrid'); grid.innerHTML='';
  const select = $('serviceSelect'); select.innerHTML='<option value="">Choose a fix…</option>';
  services().forEach(s => {
    const recommended=lead?.serviceId===s.id;
    const card=document.createElement('article'); card.className=`service-card${recommended?' recommended-service':''}`;
    card.innerHTML=`<div class="service-icon">${s.icon}</div><div>${recommended?'<span class="recommended-flag">RECOMMENDED FOR YOU</span>':''}<span class="badge">${s.tag}</span><h3>${escapeHtml(s.name)}</h3><p>${escapeHtml(s.summary)}</p><ul>${s.deliverables.map(x=>`<li>${escapeHtml(x)}</li>`).join('')}</ul></div><div class="service-footer"><div><div class="service-price">${money(s.price)}</div><div class="service-time">${escapeHtml(s.time)}</div></div><button class="choose-service" data-id="${s.id}">Choose →</button></div>`;
    grid.appendChild(card);
    const opt=document.createElement('option'); opt.value=s.id; opt.textContent=`${s.name} — ${money(s.price)}`; select.appendChild(opt);
  });
  document.querySelectorAll('.choose-service').forEach(btn => btn.addEventListener('click',()=>selectAndScope(btn.dataset.id)));
}

function selectAndScope(id){
  $('serviceSelect').value=id;
  if(lead) prefillLeadForm(false);
  $('scope').scrollIntoView({behavior:'smooth'});
  setTimeout(()=>$('problemText').focus(),350);
}
