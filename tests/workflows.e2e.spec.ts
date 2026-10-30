import {expect,test} from '@playwright/test';
const credentials=()=>({email:`flows-${Date.now()}-${Math.random().toString(36).slice(2)}@example.test`,password:'Synthetic-browser-password-2026'});
test('failed sign-out stays visibly signed in until the server confirms revocation',async({page})=>{
 const account=credentials();await page.request.post('/api/auth',{data:{action:'register',...account}});await page.goto('/');
 await expect(page.getByRole('button',{name:'Account settings',exact:true})).toBeVisible();
 await page.route('**/api/auth',async route=>{const request=route.request();if(request.method()==='POST'&&request.postDataJSON()?.action==='logout')return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'SYNTHETIC sign-out transport failure'})});return route.continue();});
 if((page.viewportSize()?.width??1000)<760)await page.getByRole('button',{name:'Open navigation'}).click();
 await page.getByRole('button',{name:/Sign out securely/}).click();
 await expect(page.getByRole('alert').filter({hasText:'SYNTHETIC sign-out transport failure'})).toBeVisible();
 await expect(page.getByRole('button',{name:'Account settings',exact:true})).toBeVisible();
 await page.unroute('**/api/auth');
 // Close the mobile drawer before interacting with the page-level retry banner.
 if((page.viewportSize()?.width??1000)<760)await page.locator('.sidebar-shade').click({position:{x:300,y:30}});
 await page.getByRole('button',{name:'Retry sign-out'}).click();
 await expect(page.getByRole('button',{name:'Sign in',exact:true})).toBeVisible();
});
test('account registration through the interface creates a persistent private workspace',async({page})=>{
 const account=credentials();await page.goto('/#advanced/home');
 await page.getByRole('button',{name:'Create your workspace'}).click();
 await page.getByLabel('Email',{exact:true}).fill(account.email);
 await page.getByLabel('Password',{exact:true}).fill(account.password);
 await page.getByRole('button',{name:'Create private account'}).click();
 await expect(page.getByRole('dialog')).toBeHidden();
 const result=await page.request.get('/api/auth');expect((await result.json()).user.email).toBe(account.email);
 await page.reload();await expect(page.getByRole('button',{name:'Account settings',exact:true})).toBeVisible();
});

test('all research and financial screens fit desktop and iPhone viewports',async({page})=>{
 const account=credentials();expect((await page.request.post('/api/auth',{data:{action:'register',...account}})).ok()).toBeTruthy();
 const errors:string[]=[];page.on('pageerror',error=>errors.push(error.message));
 for(const view of ['contracts','simulations','injuries','models','movement','history','paper','bankroll','intelligence','settings','scanner','games','players','parlay','performance','auditor','comparisons','board','warehouse']){
  await page.goto('/#'+(['bankroll','settings'].includes(view)?view:'advanced/'+view));await expect(page.locator('main h1, main h2').first()).toBeVisible();
  await page.waitForTimeout(150);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1),`overflow in ${view}`).toBe(true);
 }
 expect(errors).toEqual([]);
});

test('encrypted snapshot unlocks actual recorded history offline and rejects an incorrect password',async({page,context})=>{
 const account=credentials();await page.request.post('/api/auth',{data:{action:'register',...account}});
 const deposited=await page.request.post('/api/ledger',{data:{type:'deposit',amount:'123.45',sportsbook:'DraftKings',reference:'SYNTHETIC-OFFLINE-QA'}});expect(deposited.ok()).toBeTruthy();
 await page.goto('/#advanced/settings');await page.getByLabel('Offline snapshot passphrase').fill('Offline-synthetic-password-1742');
 await page.getByRole('checkbox',{name:/I want an encrypted copy/}).check();
 await page.getByRole('button',{name:'Save encrypted snapshot'}).click();
 await expect(page.getByText(/Encrypted historical snapshot saved on this device/)).toBeVisible();
 const ciphertext=await page.evaluate(()=>localStorage.getItem('gridiron-offline-history-v1'));
 expect(ciphertext).toBeTruthy();expect(ciphertext).not.toContain('SYNTHETIC-OFFLINE-QA');expect(ciphertext).not.toContain('DraftKings');
 await page.evaluate(async()=>{await navigator.serviceWorker.register('/sw.js');await navigator.serviceWorker.ready;});
 await page.waitForTimeout(300);await context.setOffline(true);
 await page.goto('/offline-snapshot-test');
 await page.getByLabel('Offline snapshot passphrase').fill('Incorrect-offline-password-000');
 await page.getByRole('button',{name:'Unlock historical snapshot'}).click();
 await expect(page.getByText(/Unable to unlock/)).toBeVisible();
 await page.getByLabel('Offline snapshot passphrase').fill('Offline-synthetic-password-1742');
 await page.getByRole('button',{name:'Unlock historical snapshot'}).click();
 await expect(page.getByRole('heading',{name:'Historical ledger snapshot'})).toBeVisible();
 await expect(page.locator('#history-output')).toContainText('$123.45');
 await expect(page.locator('#history-output')).toContainText('DraftKings');
 const cached=await page.evaluate(async()=>{const values=await Promise.all((await caches.keys()).map(async name=>(await (await caches.open(name)).keys()).map(r=>r.url)));return values.flat();});
 expect(cached.some(url=>new URL(url).pathname.startsWith('/api/'))).toBe(false);
 await context.setOffline(false);
});
