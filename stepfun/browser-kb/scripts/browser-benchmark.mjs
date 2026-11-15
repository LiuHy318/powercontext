import {chromium} from 'playwright';
import {createApp} from '../server.mjs';
import {localStore} from '../lib/store.mjs';
import path from 'node:path';
import fs from 'node:fs/promises';
import os from 'node:os';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const store=await localStore(path.join(root,'.runtime/benchmark-db'));
const server=createApp(store).listen(0,'127.0.0.1');await new Promise(r=>server.once('listening',r));
const browser=await chromium.launch({channel:process.env.BROWSER_CHANNEL||'chrome',headless:true});
const context=await browser.newContext({viewport:{width:1365,height:900}});
const forbidden=[];const hosts=new Set();
await context.route('**/*',route=>{const url=new URL(route.request().url());hosts.add(url.hostname);if(!['127.0.0.1','localhost'].includes(url.hostname)){forbidden.push(url.origin);return route.abort();}return route.continue();});
const page=await context.newPage();page.on('console',m=>{if(['error','warning','info'].includes(m.type()))console.log('browser',m.type(),m.text().slice(0,180));});
page.on('pageerror',e=>console.log('PAGE ERROR',e.message));
try{
 await page.goto('http://127.0.0.1:'+server.address().port);await page.waitForFunction(()=>!!window.edgekb);
 const report=await page.evaluate(()=>window.edgekb.runBenchmark({onProgress:p=>{if(p.stage)console.info(p.stage);}}));
 report.environment.browserVersion=browser.version();report.environment.cpu=os.cpus()[0].model;report.environment.platform=os.platform()+' '+os.release();report.environment.seekdb='1.4.0 local server via @oceanbase/seekdb-node, memory_budget=2G, random TCP';report.browserRequests={hosts:[...hosts],blockedExternalRequests:forbidden};
 assert.equal(forbidden.length,0,'No remote browser inference or model downloads allowed');
 assert.equal(report.configurations.filter(c=>!c.skipped).length>=3,true);
 for(const c of report.configurations.filter(c=>!c.skipped)){assert.equal(c.queries.length,18);assert.ok(c.summary.recallAt3>=0.8,'Quality regression: '+JSON.stringify(c.summary));}
 const fp32=report.configurations[0].summary,q8=report.configurations[1].summary;
 report.comparisons={q8RecallDelta:q8.recallAt3-fp32.recallAt3,q8NdcgDelta:q8.ndcgAt3-fp32.ndcgAt3,batch8Speedup:report.configurations[2].summary.throughputDocsPerSecond/q8.throughputDocsPerSecond};
 // Exercise the same actual page's import/query workflow and switching after the benchmark.
 await page.selectOption('#precision','q8');await page.click('#load');await page.waitForFunction(()=>window.edgekb.identity?.precision==='q8',{timeout:120000});
 await page.fill('#kb','ui_'+Date.now().toString(36));await page.click('#sample');await page.waitForFunction(()=>document.querySelector('#timing').textContent.includes('共 16 条'));
 await page.fill('#query','How do database indexes speed up queries?');await page.click('#query-form button');await page.waitForSelector('.result');
 assert.match(await page.locator('#results').innerText(),/index|SQL/i);
 await fs.mkdir(path.join(root,'.runtime/screenshots'),{recursive:true});await page.screenshot({path:path.join(root,'.runtime/screenshots/desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});const width=await page.evaluate(()=>({viewport:innerWidth,width:document.documentElement.scrollWidth}));assert.ok(width.width<=width.viewport,'Mobile horizontal overflow');await page.screenshot({path:path.join(root,'.runtime/screenshots/mobile.png'),fullPage:true});report.ui={importQuery:true,mobile:width};
 await fs.writeFile(path.join(root,'.runtime/browser-benchmark.json'),JSON.stringify(report,null,2));
 console.log(JSON.stringify({comparisons:report.comparisons,compression:report.compressionRatio,configurations:report.configurations.map(c=>({settings:c.settings,backend:c.identity.backend,skipped:c.skipped,summary:c.summary})),ui:report.ui},null,2));
}finally{await browser.close();await new Promise(r=>server.close(r));await store.close();}
