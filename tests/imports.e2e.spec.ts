import {expect,test} from '@playwright/test';
async function signIn(page:any){await page.request.post('/api/backend',{data:{backend:'sqlite'}});const r=await page.request.post('/api/auth',{data:{action:'register',email:`import-${Date.now()}-${Math.random().toString(36).slice(2)}@example.test`,password:'Synthetic-import-ui-password-2026'}});expect(r.ok()).toBeTruthy();}
test('financial calendar uses actual settlements and separates contributions',async({page})=>{
 await signIn(page);expect((await page.request.post('/api/ledger',{data:{type:'deposit',amount:'500.00',sportsbook:'DraftKings'}})).ok()).toBeTruthy();const bet=await (await page.request.post('/api/bets',{data:{action:'place',sportsbook:'DraftKings',event:'SYNTHETIC QA',market:'total',selection:'SYNTHETIC selection',odds:100,stake:'100.00'}})).json();expect((await page.request.post('/api/bets',{data:{action:'settle',id:bet.id,result:'won',payout:'175.00'}})).ok()).toBeTruthy();
 await page.goto('/#bankroll');await page.getByRole('button',{name:'P/L Calendar',exact:true}).click();await expect(page.getByRole('heading',{name:'Realized P/L calendar'})).toBeVisible();await expect(page.locator('.financial-report')).toContainText('$75.00');await expect(page.locator('.financial-report')).toContainText('$500.00');expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});
test('binary contract CSV needs explicit verification and exact retries do not duplicate quotes',async({page})=>{
 await signIn(page);await page.goto('/#contracts');await page.getByRole('button',{name:'Import CSV / screenshot'}).click();
 const now=new Date().toISOString(),future=new Date(Date.now()+7*86400000).toISOString();
 const header=['contractId','eventId','event','question','threshold','operator','eventStart','settlementRule','rulesUrl','yesAskCents','noAskCents','quotedAt','sourceUrl','entryFeeCents','winFeeCents','feeSource'];
 const values=['SYNTHETIC-UI-CONTRACT','SYNTHETIC-EVENT','SYNTHETIC A at H','SYNTHETIC yards over 64.5?',64.5,'gt',future,'SYNTHETIC test rules over64.5YES otherwiseNO','https://example.test/rules','52.25','49',now,'https://example.test/quote','1','0','SYNTHETIC test fee terms'];
 const csv=header.join(',')+'\n'+values.map(v=>`"${String(v).replaceAll('"','""')}"`).join(',')+'\n';
 await page.getByLabel('Upload contract CSV').setInputFiles({name:'SYNTHETIC-contract.csv',mimeType:'text/csv',buffer:Buffer.from(csv)});
 await expect(page.getByRole('button',{name:'Archive reviewed quotes'})).toBeDisabled();await page.getByLabel('I verified every imported contract field').check();await page.getByRole('button',{name:'Archive reviewed quotes'}).click();await expect(page.getByText('1 reviewed contract quotes archived.')).toBeVisible();
 await page.getByLabel('Upload contract CSV').setInputFiles({name:'SYNTHETIC-contract.csv',mimeType:'text/csv',buffer:Buffer.from(csv)});await page.getByLabel('I verified every imported contract field').check();await page.getByRole('button',{name:'Archive reviewed quotes'}).click();await expect(page.getByText(/already archived; no duplicate quotes/)).toBeVisible();
 const saved=await (await page.request.get('/api/contracts')).json();expect(saved.quotes).toHaveLength(1);expect(saved.quotes[0].yesAskCents).toBe('52.25');
});
test('bundled OCR reads a synthetic screenshot locally and never auto-verifies extracted market fields',async({page})=>{
 test.setTimeout(120000);await signIn(page);await page.goto('/#contracts');await page.getByRole('button',{name:'Import CSV / screenshot'}).click();await page.getByRole('button',{name:'Screenshot OCR'}).click();
 const data=await page.evaluate(()=>{const canvas=document.createElement('canvas');canvas.width=1500;canvas.height=650;const c=canvas.getContext('2d')!;c.fillStyle='white';c.fillRect(0,0,1500,650);c.fillStyle='black';c.font='bold 64px Arial';['SYNTHETIC OCR TEST ONLY','Contract ID: SYNTHETIC123','YES: 52 cents','NO: 49 cents','Threshold: 64.5'].forEach((line,i)=>c.fillText(line,50,90+i*110));return canvas.toDataURL('image/png').split(',')[1];});
 const posts:string[]=[];page.on('request',r=>{if(r.method()==='POST')posts.push(r.url());});
 await page.getByLabel('Upload contract screenshot').setInputFiles({name:'SYNTHETIC-ocr.png',mimeType:'image/png',buffer:Buffer.from(data,'base64')});
 await expect(page.getByLabel('OCR extracted text')).toHaveValue(/SYNTHETIC/,{timeout:100000});await expect(page.getByRole('button',{name:'Archive reviewed quotes'})).toBeDisabled();expect(posts.some(url=>url.includes('/api/contracts/import'))).toBe(false);await expect(page.getByLabel('Reviewed contract records JSON')).toHaveValue(/SYNTHETIC123/);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});
