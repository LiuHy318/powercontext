import {chromium} from 'playwright';
import {createApp} from '../server.mjs';
import {localStore} from '../lib/store.mjs';
import path from 'node:path';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
const root=path.resolve(import.meta.dirname,'..'),store=await localStore(path.join(root,'.runtime/ui-db'));
const server=createApp(store).listen(0,'127.0.0.1');await new Promise(r=>server.once('listening',r));const browser=await chromium.launch({channel:'chrome',headless:true});
try{const page=await browser.newPage({viewport:{width:1365,height:900}});await page.goto('http://127.0.0.1:'+server.address().port);await page.click('#load');await page.waitForFunction(()=>!!window.edgekb?.identity);const identity=await page.evaluate(()=>window.edgekb.identity);await page.click('#sample');await page.waitForFunction(()=>document.querySelector('#timing').textContent.includes('共 16 条'));
 await page.fill('#query','How do indexes accelerate SQL queries?');await page.click('#query-form button');await page.waitForSelector('.result');assert.match(await page.locator('#results').innerText(),/Database indexes/);
 await fs.mkdir(path.join(root,'.runtime/screenshots'),{recursive:true});await page.screenshot({path:path.join(root,'.runtime/screenshots/desktop.png')});
 await page.setViewportSize({width:390,height:844});const width=await page.evaluate(()=>({viewport:innerWidth,width:document.documentElement.scrollWidth}));assert.ok(width.width<=width.viewport);await page.screenshot({path:path.join(root,'.runtime/screenshots/mobile.png'),fullPage:true});
 await page.fill('#kb','other');assert.equal(await page.locator('.result').count(),0);await page.fill('#text','Tardigrades can survive extreme environments.');await page.click('#import');await page.waitForFunction(()=>document.querySelector('#timing').textContent.includes('共 1 条'));
 await page.selectOption('#collections',{label:'notes · '+identity.precision.toUpperCase()});await page.fill('#query','database indexes');await page.click('#query-form button');await page.waitForSelector('.result');assert.match(await page.locator('#results').innerText(),/Database indexes/);assert.doesNotMatch(await page.locator('#results').innerText(),/Tardigrades/);
 const result={browser:browser.version(),identity,mobile:width,importAndQuery:true,clearStaleResults:true,collectionSwitch:true};await fs.writeFile(path.join(root,'.runtime/ui-smoke.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{await browser.close();await new Promise(r=>server.close(r));await store.close();}
