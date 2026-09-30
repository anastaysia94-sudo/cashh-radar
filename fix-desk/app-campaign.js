function generateCampaign(){
  const raw=$('campaignCsv').value.trim();
  if(!raw){$('campaignStatus').textContent='Paste or import a CSV first.'; return;}
  let rows;
  try{rows=parseCsv(raw);}catch{ $('campaignStatus').textContent='Could not parse the CSV.'; return; }
  const cfg=ownerConfig();
  campaignRows=rows.map((raw,idx)=>{
    const r=canonicalCampaignRow(raw); const payload=buildLeadPayload(r); const s=getService(payload.serviceId); const url=personalizedUrl(r,cfg);
    const business=payload.businessName || `Prospect ${idx+1}`;
    const issue=payload.problem || 'a specific digital issue worth fixing';
    const gate=r._cashh_radar_final ? 'FINAL_V5_V6 — INDIVIDUAL REVIEW + SEND ALLOWED' : (r._cashh_radar_staging ? 'STAGING_ONLY — DO NOT SEND UNTIL FINAL V5/V6 GATE' : 'OWNER_REVIEW_REQUIRED');
    return {...raw,business_name:r.business_name,business_type:r.business_type,website:r.website,problem:r.problem,evidence:r.evidence,source_url:r.source_url,service_id:payload.serviceId,recommended_package:s.name,recommended_price:s.price,customer_url:url,campaign_gate:gate,suggested_subject:`Quick idea for ${business}: ${s.name}`,suggested_email_status:r._cashh_radar_final?'FINAL_REVIEW_READY':(r._cashh_radar_staging?'DRAFT_REVIEW_ONLY':'REVIEW_BEFORE_SEND'),suggested_email:`Hi ${business},\n\nI noticed ${issue}. I put together a short page showing the specific ${s.name} scope I would use, what is included, and the fixed price (${money(s.price)}):\n${url}\n\nNo call is required. The page shows the scope before checkout, and I do not promise guaranteed revenue or rankings.\n\nBest,\n${cfg.brand}`};
  });
  const staging=campaignRows.filter(r=>String(r.campaign_gate).startsWith('STAGING_ONLY')).length;
  const finalReady=campaignRows.filter(r=>String(r.campaign_gate).startsWith('FINAL_V5_V6')).length;
  $('campaignStatus').textContent=`Generated ${campaignRows.length} personalized link${campaignRows.length===1?'':'s'}. ${finalReady?`${finalReady} verified final V5/V6 row${finalReady===1?' is':'s are'} marked review/send-ready. `:''}${staging?`${staging} Cashh Radar staging row${staging===1?' is':'s are'} marked draft-only until the final V5/V6 gate. `:''}Nothing was uploaded; processing happened locally in your browser.`;
  $('downloadCampaignBtn').classList.toggle('hidden',!campaignRows.length);
  $('campaignPreview').innerHTML=campaignRows.slice(0,5).map(r=>`<div class="campaign-row"><div><strong>${escapeHtml(r.business_name||'Unnamed prospect')}</strong><small>${escapeHtml(r.recommended_package)} • ${money(r.recommended_price)}</small></div><button class="ghost preview-copy" type="button" data-url="${escapeHtml(r.customer_url)}">Copy link</button></div>`).join('') + (campaignRows.length>5?`<p class="tiny muted">Previewing 5 of ${campaignRows.length}. Download the enriched CSV for all rows.</p>`:'');
  document.querySelectorAll('.preview-copy').forEach(b=>b.addEventListener('click',()=>copyText(b.dataset.url,b)));
}

function downloadCampaign(){
  if(!campaignRows.length) return;
  const blob=new Blob([toCsv(campaignRows)],{type:'text/csv;charset=utf-8'}); const url=URL.createObjectURL(blob); const a=document.createElement('a'); a.href=url; a.download='fix-desk-personalized-prospects.csv'; document.body.appendChild(a); a.click(); a.remove(); setTimeout(()=>URL.revokeObjectURL(url),1000);
}

async function copyText(text, btn){
  try{await navigator.clipboard.writeText(text); const old=btn.textContent; btn.textContent='Copied ✓'; setTimeout(()=>btn.textContent=old,1400);}catch{alert('Copy failed. Select the text manually.');}
}

window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();deferredPrompt=e;$('installBtn').classList.remove('hidden')});
$('installBtn').addEventListener('click',async()=>{if(!deferredPrompt)return;deferredPrompt.prompt();await deferredPrompt.userChoice;deferredPrompt=null;$('installBtn').classList.add('hidden')});
$('startScopeBtn').addEventListener('click',()=>$('scope').scrollIntoView({behavior:'smooth'}));
$('scopeForm').addEventListener('submit',buildScope);
$('copyScopeBtn').addEventListener('click',()=>copyText(currentScopeText,$('copyScopeBtn')));
$('compareBtn').addEventListener('click',()=>{$('compareDialog').showModal()});
$('closeCompare').addEventListener('click',()=> $('compareDialog').close());
$('generateLinkBtn').addEventListener('click',generateCustomerLink);
$('copyLinkBtn').addEventListener('click',()=>copyText($('customerLinkBox').textContent,$('copyLinkBtn')));
$('shareLinkBtn').addEventListener('click',()=>navigator.share?.({title:$('ownerBrand').value||config.brand,text:'Choose a fixed-price digital fix and build your scope.',url:$('customerLinkBox').textContent}));
$('loadSampleBtn').addEventListener('click',()=>{$('campaignCsv').value='business_name,business_type,website,problem,evidence,source_url,service_id\nExample Co,local retailer,https://example.com,Homepage offer is hard to understand,Homepage hero leads with generic copy instead of a concrete customer outcome,https://example.com,conversion';});
$('clearCampaignBtn').addEventListener('click',()=>{$('campaignCsv').value='';$('campaignPreview').innerHTML='';$('campaignStatus').textContent='';campaignRows=[];$('downloadCampaignBtn').classList.add('hidden');});
$('campaignFile').addEventListener('change',async e=>{const f=e.target.files?.[0]; if(!f)return; $('campaignCsv').value=await f.text(); $('campaignStatus').textContent=`Loaded ${f.name}. Review it, then generate links.`;});
$('generateCampaignBtn').addEventListener('click',generateCampaign);
$('downloadCampaignBtn').addEventListener('click',downloadCampaign);

loadConfig(); loadLead(); renderServices(); renderCompare(); renderLead(); ownerMode();
if('serviceWorker' in navigator) navigator.serviceWorker.register('./sw.js').catch(()=>{});
