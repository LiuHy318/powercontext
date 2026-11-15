import {chromium} from 'playwright';
import express from 'express';
import path from 'node:path';
import fs from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const app=express();app.use((req,res,next)=>{res.set({'Cross-Origin-Opener-Policy':'same-origin','Cross-Origin-Embedder-Policy':'require-corp'});next();});
app.get('/',(_,res)=>res.type('html').send('<title>Isolated browser inference test</title>'));
app.get('/model-config.json',(_,res)=>res.sendFile(path.join(root,'model-config.json')));
app.use('/models',express.static(path.join(root,'.runtime/models')));
app.use('/vendor/transformers',express.static(path.join(root,'node_modules/@huggingface/transformers/dist')));
app.use('/vendor/ort',express.static(path.join(root,'node_modules/onnxruntime-web/dist')));
app.use(express.static(path.join(root,'public')));
const server=app.listen(0,'127.0.0.1');await new Promise(r=>server.once('listening',r));
const browser=await chromium.launch({headless:true});
const page=await browser.newPage();page.on('console',m=>console.log('browser:',m.type(),m.text().slice(0,400)));page.on('pageerror',e=>console.log('pageerror',e.message));
page.on('requestfailed',r=>console.log('requestfailed',r.url(),r.failure()?.errorText));
page.on('response',r=>{if(r.status()>=400)console.log('response',r.status(),r.url());});
const report={kind:'actual browser embedding component test; no database or retrieval quality is claimed',browser:browser.version(),runs:[]};
try{
 await page.goto('http://127.0.0.1:'+server.address().port);
 console.log('import diagnostic',await page.evaluate(async()=>{try{const m=await import('/embedding-worker.mjs');return 'worker module imported in page';}catch(e){return String(e)+' '+e.stack;}}));
 for(const precision of ['fp32','q8','fp16']){
  console.log('Testing',precision);
  const r=await page.evaluate(async precision=>{const {Embedder}=await import('/core.mjs');const embedder=new Embedder(p=>console.log(JSON.stringify(p)));try{const identity=await embedder.call('load',{options:{precision,forceWasm:precision!=='fp16'}});const embedded=await embedder.call('embed',{texts:['Database indexes accelerate SQL queries.','Bananas and apples are fruit.'],batchSize:2});return {identity,dimension:embedded.vectors[0].length,norm:embedded.vectors[0].reduce((s,x)=>s+x*x,0),embeddingMs:embedded.embeddingMs};}finally{embedder.worker.terminate();}},precision);
  if(r.dimension!==384||Math.abs(r.norm-1)>.01)throw Error('Invalid real embedding');report.runs.push(r);console.log(JSON.stringify(r));
 }
 await fs.mkdir(path.join(root,'.runtime'),{recursive:true});await fs.writeFile(path.join(root,'.runtime/browser-inference.json'),JSON.stringify(report,null,2));
}finally{await browser.close();server.close();}
