'use strict';
window.P500_READY=(async()=>{
  const b64=String(window.P500_GZ||'');
  if(!b64) throw new Error('The 500-prospect data bundle did not load.');
  if(typeof DecompressionStream!=='function') throw new Error('This browser is too old to open the compressed prospect dataset. Use current Chrome or Edge.');
  const raw=atob(b64), bytes=new Uint8Array(raw.length);
  for(let i=0;i<raw.length;i++) bytes[i]=raw.charCodeAt(i);
  const stream=new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
  const payload=JSON.parse(await new Response(stream).text());
  const fields=payload.fields||[], rows=payload.rows||[];
  window.P500=rows.map(row=>Object.fromEntries(fields.map((f,i)=>[f,row[i]])));
  if(window.P500.length!==500) throw new Error(`Expected 500 source-backed prospects; loaded ${window.P500.length}.`);
  const emails=new Set(window.P500.map(x=>String(x.e||'').toLowerCase()));
  if(emails.size!==500) throw new Error('Prospect data integrity check failed: public emails are not unique.');
  return window.P500;
})();
