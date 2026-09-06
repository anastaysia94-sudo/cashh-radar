'use strict';
const DATA_KEY='ps200-mobile-v1', SETTINGS_KEY='ps200-settings-v1', UI_KEY='ps200-easy-ui-v2';
const pools=[['Craigslist Bay Area Gigs','https://www.craigslist.org/search/area/sfbay?cat=ggg'],['Reddit r/forhire new','https://www.reddit.com/r/forhire/new/'],['We Work Remotely','https://weworkremotely.com/'],['Remote.co','https://remote.co/remote-jobs/'],['LinkedIn Jobs','https://www.linkedin.com/jobs/']];
let data=[...(window.PROSPECT_SEED||[])];
for(let i=data.length+1;i<=200;i++){const p=pools[(i-data.length-1)%pools.length];data.push({id:'SLOT-'+String(i).padStart(3,'0'),wave:1+Math.floor((i-1)/50),priority:i,fit:'',status:'DISCOVERY SLOT',source:p[0],prospect:'',comp:'',need:'Find one live, verified prospect from this source. Do not invent one.',url:p[1],email:''});}
let currentId=null,currentTab='focus',installPrompt=null,oauthToken=null,oauthExpires=0;
const $=id=>document.getElementById(id);
const loadState=()=>{try{return JSON.parse(localStorage.getItem(DATA_KEY)||'{}')}catch{return {}}};
const loadSettings=()=>{try{return JSON.parse(localStorage.getItem(SETTINGS_KEY)||'{}')}catch{return {}}};
const saveSettingsObj=o=>localStorage.setItem(SETTINGS_KEY,JSON.stringify(o));
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const toast=m=>{const e=$('toast');e.textContent=m;e.classList.add('on');clearTimeout(toast.t);toast.t=setTimeout(()=>e.classList.remove('on'),2300)};
function merge(p){return {...p,...(loadState()[p.id]||{})}}
function save(id,patch,rerender=true){const s=loadState();s[id]={...(s[id]||{}),...patch,updatedAt:new Date().toISOString()};localStorage.setItem(DATA_KEY,JSON.stringify(s));if(rerender)render();}
function defaultSubject(p){return `Quick fit for ${p.prospect||p.id}`}
function initial(p){return `Hi — I read your post about ${p.prospect||'the opportunity'}. I noticed you specifically need ${p.need||'the work you described'}. I can help remotely with organized research, clear written communication, spreadsheets/CRM, admin support, content, and dependable follow-through where relevant. I’d rather be useful than send a generic pitch. If this is still open, could you confirm the current scope, expected hours/deliverables, and payment process? I’m ready to continue through your normal application process.`}
function follow1(p){return `Hi — following up once in case you’re still reviewing people for ${p.prospect||'this opportunity'}. I’m still interested and can help with ${p.need||'the work described'}. If it’s already filled, no problem — I won’t keep messaging.`}
function follow2(p){return `Hi — one last quick follow-up on ${p.prospect||'this opportunity'}. If you’re still looking, I can send a concise first-step plan. If you’ve already chosen someone, I’ll close this out on my side.`}
function qualify(){return `Thanks for getting back to me. Before I start, can we confirm the exact deliverables/tasks, expected hours or deadline, rate or fixed payment, payment timing/method, and where you want the work delivered or tracked?`}
function closeMsg(){return `Great — here’s what I have us agreeing to: [DELIVERABLES], due [DATE/TIME], for [RATE/PRICE], paid via [METHOD] on [MILESTONE/TIMING]. If that matches your understanding, confirm and I’ll begin.`}
const scripts={INIT:initial,FU1:follow1,FU2:follow2,QUALIFY:qualify,CLOSE:closeMsg};
function effectiveBody(p){return p.message||initial(p)}
function effectiveSubject(p){return p.subject||defaultSubject(p)}
function statusClass(s){s=String(s);if(s==='SENT')return 'sent';if(s==='REPLIED')return 'replied';if(s==='WON / PAID')return 'won';if(s.includes('DO NOT')||s.includes('RISK'))return 'risk';return ''}
function terminal(p){return ['SENT','REPLIED','WON / PAID','SKIP'].includes(p.status)}
function badFit(p){const s=String(p.status);return s.includes('DO NOT PRIORITIZE')||s.includes('ARCHIVE')||s.includes('DEPRIORITIZE')}
function workable(p){return !terminal(p)&&!badFit(p)}
function all(){return data.map(merge)}
function nextWorkable(afterId){const a=all();let start=afterId?Math.max(0,a.findIndex(p=>p.id===afterId)+1):0;for(let n=0;n<a.length;n++){const p=a[(start+n)%a.length];if(workable(p))return p}return a[0]}
function ensureCurrent(){const a=all();const existing=currentId&&a.find(p=>p.id===currentId);if(!existing||terminal(existing)||badFit(existing))currentId=(nextWorkable(currentId)||a[0]).id;}
function counters(){const a=all();return{sent:a.filter(p=>p.status==='SENT').length,replies:a.filter(p=>p.status==='REPLIED').length,won:a.filter(p=>p.status==='WON / PAID').length,skipped:a.filter(p=>p.status==='SKIP').length,done:a.filter(p=>terminal(p)).length}}
function updateHeader(){const c=counters();$('doneCount').textContent=c.done;$('sentCount').textContent=c.sent;$('replyCount').textContent=c.replies;$('wonCount').textContent=c.won;$('progressBar').style.width=Math.min(100,c.done/200*100)+'%';}
