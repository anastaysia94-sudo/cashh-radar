'use strict';
(()=>{
  const H=window.CRH;
  if(!H||!H.serverBridge)return;
  const bridge=H.serverBridge;
  const priorRenderStats=renderStats;
  const dollars=value=>`$${Number(value||0).toFixed(2)}`;
  const hourly=value=>value==null?'—':`$${Number(value).toFixed(2)}/hr`;
  const percent=value=>value==null?'—':`${Number(value).toFixed(1)}%`;
  const signed=value=>`${Number(value||0)>=0?'+':''}${Number(value||0).toFixed(1)}`;

  function performancePanel(){return document.querySelector('.actualPerformancePanel');}
  function learningPanel(){return document.querySelector('.segmentLearningPanel');}
  function paintLoading(message='Loading your server-synced performance…'){
    const panel=performancePanel();
    if(!panel||!bridge.authenticated)return;
    panel.innerHTML=`<h2 style="margin-top:0;color:var(--navy)">Actual prospect performance</h2><p class="mini">${esc(message)}</p>`;
  }
  async function loadPerformance(){
    if(!bridge.authenticated)return null;
    try{
      const response=await fetch('/api/prospects/performance',{credentials:'same-origin'});
      if(response.status===401){bridge.authenticated=false;return null;}
      if(!response.ok)throw new Error(`HTTP ${response.status}`);
      bridge.serverPerformance=await response.json();
      return bridge.serverPerformance;
    }catch(error){
      console.warn('Cashh Radar performance sync failed',error);
      return null;
    }
  }
  async function loadPerformanceRadar(){
    if(!bridge.authenticated)return null;
    try{
      const response=await fetch('/api/radar/performance-aware?limit=80',{credentials:'same-origin'});
      if(response.status===401){bridge.authenticated=false;return null;}
      if(!response.ok)throw new Error(`HTTP ${response.status}`);
      bridge.performanceRadar=await response.json();
      return bridge.performanceRadar;
    }catch(error){
      console.warn('Cashh Radar learned ranking sync failed',error);
      return null;
    }
  }

  function paintPerformance(performance){
    const panel=performancePanel();
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
  function ensureLearningPanel(){
    let panel=learningPanel();
    if(panel)return panel;
    const performance=performancePanel();
    if(!performance)return null;
    panel=document.createElement('div');
    panel.className='panel segmentLearningPanel';
    panel.style.marginTop='10px';
    performance.insertAdjacentElement('afterend',panel);
    return panel;
  }
  function paintLearning(radar){
    const panel=ensureLearningPanel();
    if(!panel||!bridge.authenticated||!radar)return;
    const segments=(radar.segment_learning||[]).slice(0,8);
    panel.innerHTML=`<h2 style="margin-top:0;color:var(--navy)">What your actual outreach is teaching Radar</h2>
      <p class="mini">Industry adjustments stay at zero until at least 3 prospects were actually sent. They ramp gradually through 10 sent prospects and can move priority by at most ±10 points. Tiny samples do not get to run the company.</p>
      ${segments.length?`<div class="radarMiniList">${segments.map(segment=>`<article><div><strong>${esc(segment.industry)}</strong><span>${segment.sent_count} sent · ${segment.replied_count} replies · ${segment.paid_count} paid · ${dollars(segment.actual_revenue)} actual</span></div><div style="text-align:right"><strong>${signed(segment.score_adjustment)} pts</strong><span>${esc(segment.confidence)}</span></div></article>`).join('')}</div>`:'<p class="mini">No industry has enough sent outreach for a ranking adjustment yet. Radar will keep using fit, deliverability, freshness, lifecycle urgency, and value evidence until the sample is large enough.</p>'}
      <p class="mini">${esc(radar.ranking_note||'')}</p>`;
  }

  renderStats=()=>{
    priorRenderStats();
    if(!bridge.authenticated)return;
    if(bridge.serverPerformance)paintPerformance(bridge.serverPerformance);
    else paintLoading();
    if(bridge.performanceRadar)paintLearning(bridge.performanceRadar);
    Promise.all([loadPerformance(),loadPerformanceRadar()]).then(([performance,radar])=>{
      if(currentTab!=='stats')return;
      if(performance)paintPerformance(performance);
      else if(bridge.authenticated)paintLoading('Server performance could not be loaded. No local placeholder has been substituted.');
      if(radar)paintLearning(radar);
    });
  };

  loadPerformance();
  loadPerformanceRadar();
})();
