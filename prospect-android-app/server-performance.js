'use strict';
(()=>{
  const H=window.CRH;
  if(!H||!H.serverBridge)return;
  const bridge=H.serverBridge;
  const priorRenderStats=renderStats;
  const dollars=value=>`$${Number(value||0).toFixed(2)}`;
  const hourly=value=>value==null?'—':`$${Number(value).toFixed(2)}/hr`;
  const percent=value=>value==null?'—':`${Number(value).toFixed(1)}%`;

  async function loadPerformance(){
    if(!bridge.authenticated)return null;
    try{
      const response=await fetch('/api/prospects/performance',{credentials:'same-origin'});
      if(response.status===401){bridge.authenticated=false;return null;}
      if(!response.ok)throw new Error(`HTTP ${response.status}`);
      bridge.performance=await response.json();
      return bridge.performance;
    }catch(error){
      console.warn('Cashh Radar performance sync failed',error);
      return null;
    }
  }

  function paintPerformance(performance){
    const panel=document.querySelector('.actualPerformancePanel');
    if(!panel||!bridge.authenticated||!performance)return;
    panel.innerHTML=`<h2 style="margin-top:0;color:var(--navy)">Server-synced actual prospect performance</h2>
      <p class="mini">This comes from your persisted Cashh Radar prospect state. Proposed $100 offers are not counted as revenue.</p>
      <div class="performanceGrid">
        <div><b>${performance.sent_count}</b><span>Sent</span></div>
        <div><b>${performance.replied_count}</b><span>Replies · ${percent(performance.reply_rate_pct)}</span></div>
        <div><b>${performance.paid_count}</b><span>Paid · ${percent(performance.paid_rate_pct)}</span></div>
        <div><b>${dollars(performance.actual_revenue)}</b><span>Actual paid revenue</span></div>
        <div><b>${performance.tracked_minutes} min</b><span>All tracked prospect work</span></div>
        <div><b>${hourly(performance.realized_portfolio_hourly)}</b><span>Portfolio realized yield</span></div>
      </div>
      <p class="mini">${esc(performance.basis||'Actual paid revenue divided by all tracked prospect work.')}</p>`;
  }

  renderStats=()=>{
    priorRenderStats();
    if(!bridge.authenticated)return;
    if(bridge.performance)paintPerformance(bridge.performance);
    loadPerformance().then(performance=>{
      if(currentTab==='stats'&&performance)paintPerformance(performance);
    });
  };

  loadPerformance();
})();
