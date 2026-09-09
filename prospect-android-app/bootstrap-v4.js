'use strict';
(async()=>{
  const rows=await window.P500_READY;
  const legacy=[...(window.PROSPECT_SEED||[])];
  const PAYPAL='https://www.paypal.com/invoice/p/#7T6DC9A6WFH3XXCT';
  const business=rows.map(x=>({
    id:x.id,
    campaign:'SCC500-2026-09-08',
    campaignType:'business_outreach',
    wave:Number(x.q)||1,
    priority:Number(x.r)||999,
    fit:Number(x.h)||'',
    deliverability:Number(x.v)||'',
    status:'CONTACT READY',
    source:'Source-backed public business record',
    prospect:x.b||'',
    city:x.c||'',
    industry:x.i||'',
    serviceFocus:x.s||'',
    publicSignal:x.g||'',
    comp:'$100 one-time content package',
    need:[x.s,x.g].filter(Boolean).join(': '),
    url:x.u||x.w||'',
    website:x.w||'',
    email:x.e||'',
    verificationTier:x.t||'',
    verifiedAt:x.d||'2026-09-08',
    offerPrice:100,
    paypal:PAYPAL,
    requiresPostal:true,
    verified:true
  }));
  window.PROSPECT_TARGET_TOTAL=700;
  window.PROSPECT_DATA_UPDATED='2026-09-08';
  window.PROSPECT_SEED=[...business,...legacy];
  const scripts=['easy-core.js','easy-v4-core.js','easy-ui.js','easy-send.js','easy-v3.js','easy-v4-ui.js','easy-v4-image.js'];
  for(const src of scripts){
    await new Promise((resolve,reject)=>{
      const s=document.createElement('script');s.src=src;s.onload=resolve;s.onerror=()=>reject(new Error(`Could not load ${src}`));document.body.appendChild(s);
    });
  }
})().catch(err=>{
  console.error(err);
  const root=document.getElementById('focusView')||document.body;
  root.innerHTML=`<section class="panel"><h2>Prospect data could not load</h2><p>${String(err.message||err)}</p><p>Reload in a current Chrome or Edge browser.</p></section>`;
});
