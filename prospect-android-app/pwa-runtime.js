'use strict';
(()=>{
  let deferredPrompt=null;
  let toastTimer=null;

  const installed=()=>window.matchMedia('(display-mode: standalone)').matches||window.navigator.standalone===true;
  const installButton=()=>document.getElementById('installBtn');
  const notify=message=>{
    const el=document.getElementById('toast');
    if(!el)return;
    el.textContent=message;
    el.classList.add('on');
    clearTimeout(toastTimer);
    toastTimer=setTimeout(()=>el.classList.remove('on'),2600);
  };
  const refreshInstallButton=()=>{
    const button=installButton();
    if(!button)return;
    if(installed()){
      button.textContent='✓ Cashh Radar installed';
      button.disabled=true;
      return;
    }
    button.disabled=false;
    button.textContent=deferredPrompt?'Install Cashh Radar':'Install / Add to Home Screen';
  };

  async function installApp(){
    if(installed()){
      notify('Cashh Radar is already installed on this device.');
      return;
    }
    if(!deferredPrompt){
      notify('Use your browser menu → Install app / Add to Home screen.');
      return;
    }
    deferredPrompt.prompt();
    const choice=await deferredPrompt.userChoice;
    deferredPrompt=null;
    refreshInstallButton();
    notify(choice?.outcome==='accepted'?'Cashh Radar install accepted.':'Install dismissed. You can install later from Settings.');
  }

  async function registerServiceWorker(){
    if(!('serviceWorker' in navigator))return;
    try{
      const registration=await navigator.serviceWorker.register('./sw.js',{scope:'./',updateViaCache:'none'});
      registration.update().catch(()=>{});
      registration.addEventListener('updatefound',()=>{
        const worker=registration.installing;
        if(!worker)return;
        worker.addEventListener('statechange',()=>{
          if(worker.state==='installed'&&navigator.serviceWorker.controller){
            notify('A Cashh Radar update is ready. Reload once to use it.');
          }
        });
      });
    }catch(error){
      console.error('Cashh Radar service worker registration failed',error);
      notify('Offline install is unavailable in this browser session.');
    }
  }

  function bind(){
    const button=installButton();
    if(button&&!button.dataset.pwaBound){
      button.dataset.pwaBound='1';
      button.addEventListener('click',installApp);
    }
    refreshInstallButton();
    registerServiceWorker();
  }

  window.addEventListener('beforeinstallprompt',event=>{
    event.preventDefault();
    deferredPrompt=event;
    refreshInstallButton();
  });
  window.addEventListener('appinstalled',()=>{
    deferredPrompt=null;
    refreshInstallButton();
    notify('Cashh Radar installed.');
  });

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',bind,{once:true});
  else bind();
})();
