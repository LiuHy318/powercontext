import {chromium} from 'playwright';
import {createApp} from '../server.mjs';
import {localStore} from '../lib/store.mjs';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const root=path.resolve(import.meta.dirname,'..'),store=await localStore(path.join(root,'.runtime/refresh-benchmark-db'));
const server=createApp(store).listen(0,'127.0.0.1');await new Promise(r=>server.once('listening',r));
const browser=await chromium.launch({channel:'chrome',headless:true});
try{const page=await browser.newPage();await page.goto('http://127.0.0.1:'+server.address().port);const result=await page.evaluate(async()=>{const {runRefreshBenchmark}=await import('/refresh-benchmark.mjs');return runRefreshBenchmark();});
 for(const q of result.quality){assert.equal(q.baseline.recall,q.bulk.recall);assert.equal(q.baseline.ndcg,q.bulk.ndcg);}
 const reportPath=path.join(root,'.runtime/browser-benchmark.json'),report=JSON.parse(await fs.readFile(reportPath,'utf8'));assert.equal(report.environment.browserVersion,browser.version());report.refreshStrategy=result;await fs.writeFile(reportPath,JSON.stringify(report,null,2));console.log(JSON.stringify({baselineMs:result.medianPerDocumentMs,bulkMs:result.medianBulkMs,speedup:result.speedup,qualityUnchanged:true}));
}finally{await browser.close();await new Promise(r=>server.close(r));await store.close();}
