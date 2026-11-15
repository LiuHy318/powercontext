export class Embedder{
 constructor(progress=()=>{}){this.progress=progress;this.waiters=new Map();this.seq=0;this.boot();}
 boot(){this.worker=new Worker('/embedding-worker.mjs',{type:'module'});this.worker.onmessage=({data})=>{if(!data.id){this.progress(data);return;}const pending=this.waiters.get(data.id);if(!pending)return;this.waiters.delete(data.id);data.error?pending.reject(Error(data.error)):pending.resolve(data.result);};this.worker.onerror=e=>{for(const p of this.waiters.values())p.reject(Error(e.message||'推理 Worker 加载失败，请确认已经运行 npm run build'));this.waiters.clear();};}
 rpc(action,data){return new Promise((resolve,reject)=>{const id=++this.seq;this.waiters.set(id,{resolve,reject});this.worker.postMessage({id,action,...data});});}
 async call(action,data={}){const start=performance.now();try{return await this.rpc(action,data);}catch(error){if(action!=='load'||data.options?.forceWasm||!error.message.startsWith('WEBGPU_FALLBACK:'))throw error;
  // A failed GPU session can poison ORT module state. Start an entirely fresh
  // Worker for CPU fallback instead of reusing the failed inference runtime.
  this.worker.terminate();this.boot();const result=await this.rpc('load',{options:{...data.options,precision:data.options?.precision==='fp32'?'fp32':'q8',forceWasm:true}});result.fallbackSessionLoadMs=result.loadMs;result.loadMs=performance.now()-start;result.reason='WebGPU 初始化或试运行失败，已重建 WASM Worker：'+error.message.slice(16);return result;
 }}
}
export async function api(path,data){const r=await fetch('/api/'+path,data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}:{});const value=await r.json();if(!r.ok)throw Error(value.error||r.statusText);return value;}
export async function textRecords(text,title='手动输入'){
 const chunks=text.split(/\n\s*\n/).flatMap(t=>{const words=t.trim().split(/\s+/);if(!t.trim())return [];const result=[];for(let i=0;i<words.length;i+=120)result.push(words.slice(i,i+120).join(' '));return result;});
 return Promise.all(chunks.map(async(text,i)=>({id:Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(title+'\0'+text)))).map(x=>x.toString(16).padStart(2,'0')).join(''),text,title:title+' #'+(i+1)})));
}
export function metrics(ranked,relevant,k=3){const rel=new Set(relevant);const selected=ranked.slice(0,k);const hits=selected.filter(x=>rel.has(x)).length;const dcg=selected.reduce((s,x,i)=>s+(rel.has(x)?1/Math.log2(i+2):0),0);const ideal=Array.from({length:Math.min(k,rel.size)},(_,i)=>1/Math.log2(i+2)).reduce((a,b)=>a+b,0);return {recall:rel.size?hits/rel.size:0,ndcg:ideal?dcg/ideal:0};}
export function median(values){const a=[...values].sort((a,b)=>a-b),m=Math.floor(a.length/2);return a.length%2?a[m]:(a[m-1]+a[m])/2;}
