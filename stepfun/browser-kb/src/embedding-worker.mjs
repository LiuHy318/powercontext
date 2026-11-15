import {pipeline,env} from '@huggingface/transformers';
env.allowRemoteModels=false;
env.allowLocalModels=true;
env.localModelPath='/models/';
env.backends.onnx.wasm.wasmPaths='/vendor/ort/';
env.backends.onnx.wasm.numThreads=self.crossOriginIsolated?Math.min(4,self.navigator.hardwareConcurrency||1):1;
let extractor, identity, queue=Promise.resolve();
async function load({precision='auto',forceWasm=false}){
 if(extractor)await extractor.dispose();extractor=null;
 const config=await (await fetch('/model-config.json')).json();
 const start=performance.now();let reason='',backend='wasm',dtype=precision==='auto'?'q8':precision;
 const progress_callback=event=>{if(event.status==='progress')self.postMessage({progress:{file:event.file,loaded:event.loaded,total:event.total}});};
 if(!forceWasm&&precision!=='q8'&&self.navigator.gpu){
  try{
   const adapter=await self.navigator.gpu.requestAdapter();if(!adapter)throw Error('没有可用适配器');
   dtype=precision==='auto'?'fp16':precision;
   if(dtype==='fp16'&&!adapter.features.has('shader-f16'))throw Error('设备不支持 shader-f16');
   extractor=await pipeline('feature-extraction',config.id,{device:'webgpu',dtype,progress_callback});
   await extractor(['local GPU readiness check'],{pooling:'mean',normalize:true});backend='webgpu';
  }catch(error){throw Error('WEBGPU_FALLBACK:'+String(error?.message||error));}
 }else if(!forceWasm&&precision!=='q8'){reason='WebGPU 不可用，自动使用 WASM';}
 if(!extractor)extractor=await pipeline('feature-extraction',config.id,{device:'wasm',dtype,progress_callback});
 identity={model:config.id,revision:config.revision,precision:dtype,backend,reason,loadMs:performance.now()-start,threads:env.backends.onnx.wasm.numThreads};
 return identity;
}
async function execute({action,options,texts,batchSize=8}){
 if(action==='load')return load(options||{});
 if(action!=='embed'||!extractor)throw Error('请先加载本地模型');
 if(!Array.isArray(texts)||texts.length>500||texts.some(t=>typeof t!=='string'||!t.trim()))throw Error('待向量化文本无效');
 const vectors=[],start=performance.now();batchSize=Math.max(1,Math.min(32,Number(batchSize)||8));
 for(let i=0;i<texts.length;i+=batchSize){const result=await extractor(texts.slice(i,i+batchSize),{pooling:'mean',normalize:true});vectors.push(...result.tolist());self.postMessage({completed:Math.min(i+batchSize,texts.length),total:texts.length});}
 return {vectors,embeddingMs:performance.now()-start,identity};
}
self.onmessage=({data})=>{queue=queue.then(async()=>{try{self.postMessage({id:data.id,result:await execute(data)});}catch(error){self.postMessage({id:data.id,error:String(error?.message||error)});}});};
