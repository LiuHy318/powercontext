import {Embedder,api,metrics,median} from './core.mjs';
import {runRefreshBenchmark} from './refresh-benchmark.mjs';
export async function runBenchmark({onProgress=()=>{},render=()=>{}}={}){
 const corpus=await(await fetch('/data/sample.json')).json();const manifest=await api('model-manifest');
 const commonBytes=manifest.files.filter(f=>!f.path.endsWith('.onnx')).reduce((s,f)=>s+f.bytes,0);
 const bytes=Object.fromEntries(Object.entries(manifest.model.files).map(([p,path])=>[p,commonBytes+manifest.files.find(f=>f.path===path).bytes]));
 const report={startedAt:new Date().toISOString(),environment:{userAgent:navigator.userAgent,logicalCores:navigator.hardwareConcurrency,crossOriginIsolated,webgpuExposed:!!navigator.gpu},model:manifest.model,modelFiles:manifest.files,modelBytes:bytes,compressionRatio:{q8:bytes.fp32/bytes.q8,fp16:bytes.fp32/bytes.fp16},dataset:{documents:corpus.documents.length,queries:corpus.queries.length,judgments:corpus.queries},method:{repetitions:3,k:3,quality:'binary relevance Recall@3 and nDCG@3; all rankings from seekdb',timing:'performance.now; E2E includes worker round trip, HTTP retrieval and DOM update + animation frame',firstLoad:'first observed browser fetch/session initialization; cache may be reused if this origin was previously used',source:'same pinned public weights; no cloud inference; no server embeddings'},configurations:[]};
 let embedder;
 try{
 for(const settings of [{precision:'fp32',forceWasm:true,batchSize:1},{precision:'q8',forceWasm:true,batchSize:1},{precision:'q8',forceWasm:true,batchSize:8},{precision:'fp16',forceWasm:false,batchSize:8}]){
  embedder?.worker.terminate();embedder=new Embedder(onProgress);
  onProgress({stage:'加载 '+JSON.stringify(settings)});
  const identity=await embedder.call('load',{options:settings});
  if(settings.precision==='fp16'&&identity.backend!=='webgpu'){report.configurations.push({settings,identity,skipped:true,reason:'本环境未成功启用 WebGPU FP16；不将 WASM 结果记为 WebGPU 实测'});continue;}
  const kb='bench_'+crypto.randomUUID().replaceAll('-','').slice(0,12);const config={kb,settings,identity,imports:[],queries:[]};
  // Warm the compute graph separately; this request is not included in query medians.
  const warm=await embedder.call('embed',{texts:['warmup embedding'],batchSize:1});config.warmupMs=warm.embeddingMs;
  for(let repeat=0;repeat<3;repeat++){
   const t=performance.now();const embedded=await embedder.call('embed',{texts:corpus.documents.map(d=>d.text),batchSize:settings.batchSize});
   const written=await api('import',{kb,precision:identity.precision,records:corpus.documents.map((d,i)=>({...d,embedding:embedded.vectors[i]}))});
   config.imports.push({repeat,embeddingMs:embedded.embeddingMs,writeMs:written.writeMs,refreshMs:written.refreshMs,totalMs:performance.now()-t,documentsPerSecond:corpus.documents.length/(embedded.embeddingMs/1000)});
   for(const query of corpus.queries){const start=performance.now();const embeddedQuery=await embedder.call('embed',{texts:[query.text],batchSize:1});const response=await api('search',{kb,precision:identity.precision,query:query.text,embedding:embeddedQuery.vectors[0],mode:'hybrid',limit:3});render(response);await new Promise(resolve=>requestAnimationFrame(resolve));const e2eMs=performance.now()-start;
    config.queries.push({repeat,query:query.text,ids:response.results.map(r=>r.id),...metrics(response.results.map(r=>r.id),query.relevant,3),embeddingMs:embeddedQuery.embeddingMs,databaseMs:response.databaseMs,e2eMs});
   }
  }
  config.summary={throughputDocsPerSecond:median(config.imports.map(x=>x.documentsPerSecond)),documentEmbeddingMs:median(config.imports.map(x=>x.embeddingMs)),writeMs:median(config.imports.map(x=>x.writeMs)),refreshMs:median(config.imports.map(x=>x.refreshMs)),queryEmbeddingMs:median(config.queries.map(x=>x.embeddingMs)),seekdbMs:median(config.queries.map(x=>x.databaseMs)),e2eMs:median(config.queries.map(x=>x.e2eMs)),recallAt3:config.queries.reduce((s,q)=>s+q.recall,0)/config.queries.length,ndcgAt3:config.queries.reduce((s,q)=>s+q.ndcg,0)/config.queries.length};report.configurations.push(config);onProgress({stage:'完成 '+identity.precision+' / '+identity.backend+' / batch '+settings.batchSize});
 }
 report.refreshStrategy=await runRefreshBenchmark(onProgress);
 return report;
 }finally{embedder?.worker.terminate();}
}
