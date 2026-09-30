function ownerMode(){
  const p=new URLSearchParams(location.search); const isOwner=p.get('owner')==='1' || location.hash==='#owner';
  if(!isOwner) return;
  $('ownerPanel').classList.remove('hidden');
  $('ownerBrand').value=config.brand; $('ownerPay').value=config.paymentUrl; $('ownerEmail').value=config.email; $('ownerNote').value=config.note;
  renderOwnerServices(); updateGoalMath();
  $('ownerPanel').scrollIntoView({behavior:'smooth'});
}

function renderOwnerServices(){
  const wrap=$('ownerServices'); wrap.innerHTML='';
  services().forEach(s=>{
    const row=document.createElement('div'); row.className='owner-service-row';
    row.innerHTML=`<div><strong>${s.icon} ${escapeHtml(s.name)}</strong><small>${escapeHtml(s.id)}</small></div><label>Price<input class="owner-price" type="number" min="1" step="1" value="${s.price}" data-id="${s.id}" /></label><label>Checkout URL<input class="owner-service-pay" type="url" value="${escapeHtml(config.paymentUrls?.[s.id]||'')}" data-id="${s.id}" placeholder="optional; falls back to main checkout" /></label>`;
    wrap.appendChild(row);
  });
  wrap.querySelectorAll('.owner-price').forEach(i=>i.addEventListener('input',updateGoalMath));
}

function updateGoalMath(){
  const vals=[...document.querySelectorAll('.owner-price')].map(i=>Number(i.value)).filter(n=>n>0).sort((a,b)=>b-a);
  const top=vals[0]||249; const needed=Math.ceil(1000/top); $('goalMath').textContent=`At ${money(top)}: ${needed} sales = ${money(needed*top)} gross.`;
}

function ownerConfig(){
  const newCfg={brand:compact($('ownerBrand').value||'Same-Day Digital Fix Desk',70),paymentUrl:safeUrl($('ownerPay').value),paymentUrls:{},email:safeEmail($('ownerEmail').value),note:compact($('ownerNote').value,140),prices:{}};
  document.querySelectorAll('.owner-price').forEach(i=>newCfg.prices[i.dataset.id]=Math.max(1,Number(i.value)||1));
  document.querySelectorAll('.owner-service-pay').forEach(i=>newCfg.paymentUrls[i.dataset.id]=safeUrl(i.value));
  return newCfg;
}

function baseCustomerUrl(cfg=ownerConfig()){
  const u=new URL(location.href); u.search=''; u.hash=''; u.searchParams.set('cfg',encodeObj(cfg)); return u;
}

function generateCustomerLink(){
  const u=baseCustomerUrl();
  $('customerLinkBox').textContent=u.toString(); $('customerLinkBox').classList.remove('hidden'); $('copyLinkBtn').classList.remove('hidden'); if(navigator.share)$('shareLinkBtn').classList.remove('hidden');
}

function canonicalCampaignRow(row){
  const lower={}; Object.entries(row||{}).forEach(([k,v])=>lower[String(k).trim().toLowerCase().replace(/[^a-z0-9_]/g,'')]=v);
  const pick=(...keys)=>{ for(const k of keys){ const key=k.toLowerCase().replace(/[^a-z0-9_]/g,''); if(lower[key]!==undefined && String(lower[key]).trim()!=='') return String(lower[key]).trim(); } return ''; };
  const version=pick('version');
  const finalCashhRadar=/^v[56]$/i.test(version) && Boolean(pick('masterrank','versionrank','subject','initialemail'));
  const cashhRadar=Boolean(pick('_accepted','checkdate','evidencenote','normalized_name','normalized_email','masterrank','versionrank'));
  return {
    ...row,
    business_name:pick('business_name','business','name','company'),
    business_type:pick('business_type','industry','category','service_focus'),
    website:pick('website','url','domain'),
    problem:pick('problem','observation','need','opportunity','personalization'),
    evidence:pick('evidence','evidence_note','evidencenote','notes','why_now'),
    source_url:pick('source_url','sourceurl','source','emailsourceurl','email_source_url'),
    service_id:finalCashhRadar ? 'content' : pick('service_id','serviceid','recommended_service'),
    source_email:pick('email','public_email','business_email'),
    source_city:pick('city','location','service_area'),
    source_check_date:pick('checkdate','check_date','source_date'),
    source_accepted:pick('_accepted','accepted'),
    source_version:version,
    _cashh_radar_final:finalCashhRadar,
    _cashh_radar_staging:cashhRadar && !finalCashhRadar
  };
}

function buildLeadPayload(row){
  const r=canonicalCampaignRow(row);
  const serviceId=BASE_SERVICES.some(s=>s.id===r.service_id) ? r.service_id : inferService(`${r.problem||''} ${r.evidence||''}`);
  return {businessName:compact(r.business_name,100),businessType:compact(r.business_type,80),website:safeUrl(r.website||''),problem:compact(r.problem,700),evidence:compact(r.evidence,700),sourceUrl:safeUrl(r.source_url||''),serviceId};
}

function personalizedUrl(row,cfg){
  const u=baseCustomerUrl(cfg); u.searchParams.set('lead',encodeObj(buildLeadPayload(row))); return u.toString();
}

function parseCsv(text){
  const rows=[]; let row=[],field='',quoted=false;
  for(let i=0;i<text.length;i++){
    const ch=text[i];
    if(quoted){ if(ch==='"' && text[i+1]==='"'){field+='"';i++;} else if(ch==='"'){quoted=false;} else field+=ch; }
    else if(ch==='"') quoted=true;
    else if(ch===','){row.push(field);field='';}
    else if(ch==='\n'){row.push(field); rows.push(row); row=[]; field='';}
    else if(ch!=='\r') field+=ch;
  }
  if(field.length || row.length){row.push(field);rows.push(row);}
  if(!rows.length) return [];
  const headers=rows.shift().map(h=>h.trim().toLowerCase());
  return rows.filter(r=>r.some(v=>v.trim())).map(r=>Object.fromEntries(headers.map((h,i)=>[h,(r[i]||'').trim()])));
}

function csvEscape(value){ const s=String(value??''); return /[",\n\r]/.test(s)?`"${s.replace(/"/g,'""')}"`:s; }
function toCsv(rows){ if(!rows.length)return''; const headers=Object.keys(rows[0]); return [headers.join(','),...rows.map(r=>headers.map(h=>csvEscape(r[h])).join(','))].join('\r\n'); }
