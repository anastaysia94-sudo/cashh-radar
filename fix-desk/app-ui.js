function renderLead(){
  if(!lead) return;
  const s=getService(lead.serviceId);
  $('leadBanner').classList.remove('hidden');
  $('leadBusiness').textContent=lead.businessName || 'Your business';
  $('heroEyebrow').textContent='A SHORT, PERSONALIZED DIGITAL FIX REVIEW';
  $('heroTitle').innerHTML=`One practical fix worth considering for <span>${escapeHtml(lead.businessName || 'your business')}.</span>`;
  $('heroSub').textContent=lead.problem || `I matched ${lead.businessName || 'this business'} to a bounded digital fix that can be scoped and purchased without a sales call.`;
  $('heroPrimary').textContent=`Review the ${money(s.price)} recommendation`;
  $('heroPrimary').href='#leadEvidence';
  $('heroCardLabel').textContent='RECOMMENDED PACKAGE';
  $('heroCardTitle').textContent=`${s.icon} ${s.name}`;
  $('heroCardText').textContent=s.summary;
  $('heroMiniGrid').innerHTML=`<div><strong>${money(s.price)}</strong><span>fixed price</span></div><div><strong>${s.deliverables.length}</strong><span>defined deliverables</span></div><div><strong>${s.time}</strong><span>target timing</span></div><div><strong>0</strong><span>required calls</span></div>`;

  $('leadEvidence').classList.remove('hidden');
  $('leadEvidenceTitle').textContent=lead.businessName ? `Why I matched this to ${lead.businessName}` : 'Why this package was selected';
  $('leadProblem').textContent=lead.problem || 'A specific digital issue was identified and matched to the smallest relevant package.';
  $('leadEvidenceText').textContent=lead.evidence || 'No extra evidence note was included. Review the linked website/work item and the written scope before purchasing.';
  if(lead.sourceUrl){ $('leadSource').href=lead.sourceUrl; $('leadSource').classList.remove('hidden'); }
  const rec=$('leadRecommended');
  rec.innerHTML=`<div class="rec-head"><span class="service-icon">${s.icon}</span><div><span class="badge">${escapeHtml(s.tag)}</span><h3>${escapeHtml(s.name)}</h3></div><span class="price-pill">${money(s.price)}</span></div><p>${escapeHtml(s.summary)}</p><ul>${s.deliverables.map(x=>`<li>${escapeHtml(x)}</li>`).join('')}</ul><button id="acceptRecommendation" class="primary wide" type="button">Build the written scope →</button>`;
  $('acceptRecommendation').addEventListener('click',()=>selectAndScope(s.id));
  $('leadReviewBtn').addEventListener('click',()=>selectAndScope(s.id));
  prefillLeadForm(true);
}

function prefillLeadForm(forceService=true){
  if(!lead) return;
  if(!$('businessNameInput').value) $('businessNameInput').value=lead.businessName;
  if(!$('businessType').value) $('businessType').value=lead.businessType || 'small business';
  if(!$('workUrl').value) $('workUrl').value=lead.website;
  if(!$('problemText').value) $('problemText').value=lead.problem;
  if(forceService && !$('serviceSelect').value) $('serviceSelect').value=lead.serviceId;
}

function renderCompare(){
  $('compareTable').innerHTML = `<div class="compare-list">${services().map(s=>`<div class="compare-row"><div><strong>${s.icon} ${escapeHtml(s.name)}</strong><br><small>${escapeHtml(s.tag)}</small></div><strong>${money(s.price)}</strong><small>${escapeHtml(s.time)}</small><small class="compare-desc">${s.deliverables.map(escapeHtml).join(' • ')}</small></div>`).join('')}</div>`;
}

function buildScope(evt){
  evt.preventDefault();
  const service=getService($('serviceSelect').value); if(!service || !$('serviceSelect').value) return;
  currentService=service;
  const businessName=compact($('businessNameInput').value,100); const businessType=compact($('businessType').value,80); const workUrl=safeUrl($('workUrl').value); const problem=compact($('problemText').value,700); const deadline=$('deadline').value;
  $('scopeTitle').textContent = `${service.name}${businessName?` for ${businessName}`:` for a ${businessType}`}`;
  $('scopePrice').textContent = money(service.price);
  const blocks=[
    ['Problem to solve', `<p>${escapeHtml(problem)}</p>`],
    ['What is included', `<ul>${service.deliverables.map(x=>`<li>${escapeHtml(x)}</li>`).join('')}</ul>`],
    ['Timing', `<p>Requested: ${escapeHtml(deadline)}. Final timing is confirmed against capacity before work begins.</p>`],
    ['Evidence / access', `<p>${workUrl ? `Work link: <a href="${escapeHtml(workUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(workUrl)}</a>` : 'No link supplied yet. Any required files, URLs, or access details are requested before work starts.'}</p>`]
  ];
  $('scopeOutput').innerHTML=blocks.map(([h,b])=>`<div class="scope-block"><strong>${h}</strong>${b}</div>`).join('');
  currentScopeText = `${config.brand}\n\nService: ${service.name}\nPrice: ${money(service.price)}\n${businessName?`Business: ${businessName}\n`:''}Business type: ${businessType}\nRequested timing: ${deadline}\n${workUrl?`Work link: ${workUrl}\n`:''}\nProblem:\n${problem}\n\nIncluded:\n- ${service.deliverables.join('\n- ')}\n\nNote: Timing is confirmed before work begins. Deliverables are sold as scoped work, not guaranteed revenue/results.`;
  const subject=encodeURIComponent(`${businessName?`${businessName} — `:''}${service.name} scope request`); const body=encodeURIComponent(currentScopeText);
  $('emailScopeBtn').href = config.email ? `mailto:${config.email}?subject=${subject}&body=${body}` : `mailto:?subject=${subject}&body=${body}`;
  const pay=paymentFor(service.id);
  if(pay){ $('payBtn').href=pay; $('payBtn').textContent=`Continue to checkout — ${money(service.price)}`; $('checkoutNote').textContent=config.note || 'Checkout opens in a new tab. Scope and timing should be confirmed if the payment page does not collect project details.'; }
  else { $('payBtn').removeAttribute('target'); $('payBtn').href=config.email?$('emailScopeBtn').href:'#ownerPanel'; $('payBtn').textContent=config.email?'Send scope to start':'Owner: add checkout link'; $('checkoutNote').textContent='No checkout URL is configured for this package yet.'; }
  $('scopeResult').classList.remove('hidden'); $('scopeResult').scrollIntoView({behavior:'smooth'});
}
