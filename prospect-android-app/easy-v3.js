(()=>{
  const WELCOME_KEY='ps200-easy-welcome-v3';
  function showWelcome(){
    if(localStorage.getItem(WELCOME_KEY))return;
    const d=document.createElement('dialog');d.className='welcomeCard';
    d.innerHTML=`<h2>Use it like a conveyor belt</h2><p class="tinyNote">You do not need to manage all 200 at once. The app keeps choosing the next best action.</p><div class="welcomeSteps"><div class="welcomeStep"><b>1</b><p><strong>Open + verify.</strong><br>Confirm the real listing is still active.</p></div><div class="welcomeStep"><b>2</b><p><strong>Tap the big action button.</strong><br>Email/Gmail is prepared automatically when a verified email exists; otherwise the message is copied and the source route opens.</p></div><div class="welcomeStep"><b>3</b><p><strong>After you actually send, confirm it.</strong><br>The app moves on and brings the prospect back automatically when follow-up is due.</p></div></div><button class="btn primary" id="welcomeStart" style="width:100%">Start with the next best prospect</button><p class="tinyNote">Replies are prioritized before follow-ups, and follow-ups before new outreach.</p>`;
    document.body.appendChild(d);d.showModal();
    d.querySelector('#welcomeStart').addEventListener('click',()=>{localStorage.setItem(WELCOME_KEY,'1');d.close();d.remove();});
  }
  function enhanceEmailPaste(){
    const wrap=document.querySelector('#focusView .emailWrap');
    if(!wrap||wrap.parentElement.querySelector('.pasteEmailBtn'))return;
    const b=document.createElement('button');b.type='button';b.className='btn soft pasteEmailBtn';b.style.cssText='margin-top:8px;width:100%';b.textContent='Paste email from clipboard';
    b.addEventListener('click',async()=>{
      try{
        const text=await navigator.clipboard.readText();const match=text.match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i);
        if(!match)return toast('No email address found in the clipboard.');
        const input=document.getElementById('focusEmail');if(!input)return;
        input.value=match[0];const p=merge(data.find(x=>x.id===currentId));save(p.id,{email:match[0]},false);toast('Email pasted. Ready to draft.');renderFocus();
      }catch{toast('Clipboard access was blocked. Paste the email into the field manually.');}
    });
    wrap.insertAdjacentElement('afterend',b);
  }
  const observer=new MutationObserver(()=>enhanceEmailPaste());
  const focus=document.getElementById('focusView');if(focus)observer.observe(focus,{childList:true,subtree:true});
  enhanceEmailPaste();
  document.addEventListener('visibilitychange',()=>{
    if(document.visibilityState!=='visible'||currentTab!=='focus'||!currentId)return;
    const p=merge(data.find(x=>x.id===currentId));
    if(p.preparedAt)toast('Back from email? If you sent it, tap “I sent it — next best action.”');
  });
  setTimeout(()=>{const c=counters();if(c.replies)toast(`${c.replies} replied prospect${c.replies===1?'':'s'} waiting — replies are first.`);else if(c.due)toast(`${c.due} follow-up${c.due===1?'':'s'} due — loaded ahead of new outreach.`);showWelcome();},350);
})();
