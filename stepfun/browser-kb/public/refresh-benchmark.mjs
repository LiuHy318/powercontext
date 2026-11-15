import {Embedder,api,metrics,median} from './core.mjs';
export async function runRefreshBenchmark(onProgress=()=>{}){
 const data=await(await fetch('/data/sample.json')).json(),embedder=new Embedder();
 try{
  const identity=await embedder.call('load',{options:{precision:'q8',forceWasm:true}});
  const vectors=await embedder.call('embed',{texts:data.documents.map(d=>d.text),batchSize:1});
  const records=data.documents.map((d,i)=>({...d,embedding:vectors.vectors[i]}));
  const nonce=crypto.randomUUID().replaceAll('-','').slice(0,10),slow='slow_'+nonce,fast='bulk_'+nonce;
  const result={identity,documents:records.length,repetitions:3,embeddingExcluded:true,baseline:'one upsert request + refresh per document',optimized:'bulk upsert + one refresh per import',samples:[]};
  for(let repeat=0;repeat<3;repeat++){
   onProgress({stage:`索引刷新策略对照 ${repeat+1}/3`});
   const start=performance.now();for(const row of records)await api('import',{kb:slow,precision:'q8',records:[row]});const middle=performance.now();await api('import',{kb:fast,precision:'q8',records});
   result.samples.push({repeat,perDocumentMs:middle-start,bulkMs:performance.now()-middle,baselineRefreshes:records.length,bulkRefreshes:1});
  }
  result.quality=[];
  for(const query of data.queries){const embedded=await embedder.call('embed',{texts:[query.text],batchSize:1});const row={query:query.text};for(const [name,kb] of [['baseline',slow],['bulk',fast]]){const found=await api('search',{kb,precision:'q8',query:query.text,embedding:embedded.vectors[0],limit:3});row[name]={ids:found.results.map(r=>r.id),...metrics(found.results.map(r=>r.id),query.relevant,3)};}result.quality.push(row);}
  result.medianPerDocumentMs=median(result.samples.map(s=>s.perDocumentMs));result.medianBulkMs=median(result.samples.map(s=>s.bulkMs));result.speedup=result.medianPerDocumentMs/result.medianBulkMs;return result;
 }finally{embedder.worker.terminate();}
}
