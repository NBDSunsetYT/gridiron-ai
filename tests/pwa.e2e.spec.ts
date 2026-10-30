import {test,expect} from '@playwright/test';

test('iPhone installation guidance reports the real app URL, public offline readiness and required metadata',async({page})=>{
 await page.goto('/#settings');
 const install=page.getByRole('region',{name:'Install GRIDIRON AI'});
 await expect(install).toBeVisible();await expect(install.getByText('Tap Share, then Add to Home Screen.')).toBeVisible();
 await expect(install.locator('code')).toHaveText(new URL(page.url()).origin+'/');
 await expect(install.getByText('CACHED',{exact:true})).toBeVisible();
 await expect(page.locator('meta[name="apple-mobile-web-app-capable"]')).toHaveAttribute('content','yes');
 await expect(page.locator('link[rel="apple-touch-icon"]')).toHaveAttribute('sizes','180x180');
 await expect(page.locator('meta[name="viewport"]')).toHaveAttribute('content',/viewport-fit=cover/);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 // Installation remains public. The optional cache-maintenance controls and
 // their forms live in Advanced Mode in the consumer release.
 await page.goto('/#advanced/settings');await expect(install).toBeVisible();
 if((page.viewportSize()?.width??1000)<760)expect(await page.locator('.input').first().evaluate(el=>parseFloat(getComputedStyle(el).fontSize))).toBeGreaterThanOrEqual(16);
 await page.getByRole('button',{name:'Clear app caches',exact:true}).click();await expect(install.getByText('ONLINE REQUIRED',{exact:true})).toBeVisible();await page.reload();await expect(page.getByRole('region',{name:'Install GRIDIRON AI'}).getByText('CACHED',{exact:true})).toBeVisible();
});

test('standalone display is reported from Safari’s web-app flag without claiming a physical install',async({page})=>{
 await page.addInitScript(()=>Object.defineProperty(navigator,'standalone',{get:()=>true,configurable:true}));
 await page.goto('/#settings');const install=page.getByRole('region',{name:'Install GRIDIRON AI'});
 await expect(install.getByText('STANDALONE MODE',{exact:true})).toBeVisible();
 await expect(install.getByRole('status')).toContainText('running in standalone mode');
});
