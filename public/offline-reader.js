/* Optional, encrypted historical snapshot. No API requests or offline writes. */
(()=>{
 'use strict';
 const section=document.getElementById('offline-history'),form=document.getElementById('unlock-form'),message=document.getElementById('unlock-message'),output=document.getElementById('history-output');
 const keyName='gridiron-offline-history-v1';let envelope;
 try{envelope=JSON.parse(localStorage.getItem(keyName)||'null');}catch{}
 if(!envelope||envelope.version!==1)return;
 section.hidden=false;
 const decode=value=>Uint8Array.from(atob(value),c=>c.charCodeAt(0));
 const money=value=>Number.isSafeInteger(value)?new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(value/100):'Unavailable';
 form.addEventListener('submit',async event=>{
  event.preventDefault();message.textContent='Unlocking encrypted history…';const button=form.querySelector('button');button.disabled=true;
  try{
   if(envelope.iterations!==310000||typeof envelope.ciphertext!=='string'||envelope.ciphertext.length>14000000)throw Error('Invalid snapshot');
   const material=await crypto.subtle.importKey('raw',new TextEncoder().encode(document.getElementById('offline-password').value),'PBKDF2',false,['deriveKey']);
   const key=await crypto.subtle.deriveKey({name:'PBKDF2',salt:decode(envelope.salt),iterations:310000,hash:'SHA-256'},material,{name:'AES-GCM',length:256},false,['decrypt']);
   const bytes=await crypto.subtle.decrypt({name:'AES-GCM',iv:decode(envelope.iv)},key,decode(envelope.ciphertext));
   const snapshot=JSON.parse(new TextDecoder().decode(bytes)),ledger=snapshot.ledger;
   if(!ledger||!ledger.summary||!Array.isArray(ledger.transactions))throw Error('Invalid ledger');
   output.replaceChildren();
   const add=(tag,text,parent=output)=>{const el=document.createElement(tag);el.textContent=text;parent.appendChild(el);return el;};
   add('h2','Historical ledger snapshot');add('p','Saved '+new Date(snapshot.savedAt).toLocaleString()+'. These are historical records, not current balances.');
   const list=add('dl','');for(const [name,value] of [['Recorded bankroll',ledger.summary.cashBalanceCents],['Available at snapshot',ledger.summary.availableBalanceCents],['Pending exposure',ledger.summary.pendingExposureCents],['Realized betting P/L',ledger.summary.realizedPlCents],['Total deposits',ledger.summary.totalDepositsCents],['Total withdrawals',ledger.summary.totalWithdrawalsCents]]){add('dt',name,list);add('dd',money(value),list);}
   add('h2','Recent recorded transactions');
   for(const row of ledger.transactions.slice(0,100)){const item=add('div','');item.className='history-row';add('strong',String(row.type).replaceAll('_',' ')+' · '+money(row.amountCents),item);add('p',String(row.sportsbook)+' · '+new Date(row.date).toLocaleString(),item);}
   if(!ledger.transactions.length)add('p','No recorded transactions in this snapshot.');
   message.textContent='Historical copy unlocked. Reconnect to reconcile or change records.';document.getElementById('offline-password').value='';
  }catch{message.textContent='Unable to unlock. Check the passphrase and snapshot integrity.';output.replaceChildren();}
  finally{button.disabled=false;}
 });
 document.getElementById('clear-history').addEventListener('click',()=>{localStorage.removeItem(keyName);output.replaceChildren();section.hidden=true;});
})();
