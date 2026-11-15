import {SeekdbClient,Schema,FulltextIndexConfig,VectorIndexConfig} from 'seekdb';
import {target,records,vector,DIMENSION} from './validation.mjs';
import model from '../model-config.json' with {type:'json'};
import {seekdb} from '@oceanbase/seekdb-node';
import {performance} from 'node:perf_hooks';
export class Store {
 constructor(options){this.client=new SeekdbClient(options);this.tail=Promise.resolve();}
 // seekdb hybridSearch uses a connection-local @search_parm. Serialize complete
 // operations so concurrent sessions cannot overwrite that variable or interleave
 // an import's refresh barrier with another query.
 run(fn){const task=this.tail.then(fn);this.tail=task.catch(()=>{});return task;}
 async collection(input,create=false){
  const name=target(input);
  if(create)return this.client.getOrCreateCollection({name,embeddingFunction:null,schema:new Schema({
   fulltextIndex:new FulltextIndexConfig('space'),
   vectorIndex:new VectorIndexConfig({hnsw:{dimension:DIMENSION,distance:'cosine'},embeddingFunction:null})
  })});
  return this.client.getCollection({name,embeddingFunction:null});
 }
 list(){return this.run(async()=> (await this.client.listCollections({withEmbeddingFunction:false})).map(c=>c.name).filter(n=>n.startsWith('edgekb_')));}
 import(input){const rows=records(input.records);target(input);return this.run(async()=>{
  const collection=await this.collection(input,true);const start=performance.now();
  for(let offset=0;offset<rows.length;offset+=64){const batch=rows.slice(offset,offset+64);await collection.upsert({ids:batch.map(r=>r.id),documents:batch.map(r=>r.text),embeddings:batch.map(r=>r.embedding),metadatas:batch.map(r=>({title:r.title,model:model.id,revision:model.revision,precision:input.precision,embeddingLocation:'browser'}))});}
  const written=performance.now();await collection.refresh_index();const refreshed=performance.now();
  return {collection:collection.name,imported:rows.length,count:await collection.count(),refreshed:true,writeMs:written-start,refreshMs:refreshed-written};
 });}
 search(input){target(input);vector(input.embedding);if(typeof input.query!=='string'||!input.query.trim()||input.query.length>1000)throw new Error('查询不能为空且不超过 1000 字符');
  const limit=Number(input.limit||5);if(!Number.isInteger(limit)||limit<1||limit>20)throw new Error('结果数量须为 1–20');
  if(!['hybrid','vector'].includes(input.mode||'hybrid'))throw new Error('检索模式无效');
  return this.run(async()=>{const collection=await this.collection(input);const start=performance.now();
   const result=input.mode==='vector'?await collection.query({queryEmbeddings:input.embedding,nResults:limit,include:['documents','metadatas','distances']}):
    await collection.hybridSearch({query:{whereDocument:{$contains:input.query},nResults:Math.max(20,limit)},knn:{queryEmbeddings:input.embedding,nResults:Math.max(20,limit)},rank:{rrf:{rankWindowSize:Math.max(20,limit),rankConstant:60}},nResults:limit,include:['documents','metadatas','distances']});
   return {collection:collection.name,mode:input.mode||'hybrid',databaseMs:performance.now()-start,engine:'seekdb / DBMS_HYBRID_SEARCH.GET_SQL',results:(result.ids[0]||[]).map((id,i)=>({id,text:result.documents?.[0]?.[i],metadata:result.metadatas?.[0]?.[i],score:result.distances?.[0]?.[i]}))};
  });
 }
 async close(){await this.tail;await this.client.close();this.runtime?.close();}
}
export async function localStore(directory){
 const runtime=await seekdb.open(directory,{parameters:{memory_budget:'2G',mysql_port_mode:'random'}});
 try{const endpoint=runtime.connectionOptions();if(endpoint.transport!=='tcp')throw Error('本地运行库没有返回 TCP 端点，请按 README 使用本地 seekdb server 模式');
 const store=new Store({host:endpoint.host,port:endpoint.port,user:endpoint.user,password:'',database:'test'});store.runtime=runtime;return store;
 }catch(e){runtime.close();throw e;}
}
