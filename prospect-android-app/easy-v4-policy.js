'use strict';
(()=>{
  const H=window.CRH;
  if(!H)return;

  const lifecycleStatuses=new Set(['SENT','REPLIED','WON / PAID']);
  const validEmail=value=>/.+@.+\..+/.test(String(value||'').trim());

  data=data.map(p=>{
    if(H.isBusiness(p)||lifecycleStatuses.has(String(p.status)))return p;
    const sourceText=`${p.source||''} ${p.url||''}`.toLowerCase();
    if(sourceText.includes('reddit.com')||sourceText.includes('reddit ')){
      return {
        ...p,
        status:'DO NOT PRIORITIZE — REDDIT DISABLED',
        disabledReason:'Cashh Radar outreach policy excludes Reddit.'
      };
    }
    if(!validEmail(p.email)){
      return {
        ...p,
        status:'DEPRIORITIZE — NO VERIFIED EMAIL',
        disabledReason:'Email-first workflow requires a verified public email before outreach.'
      };
    }
    return p;
  });

  const baseRank=H.rank;
  H.rank=p=>badFit(p)?9:baseRank(p);
  H.outreachPolicy=Object.freeze({emailOnly:true,reddit:false});
})();
