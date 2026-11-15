import express from 'express';
import path from 'node:path';
import fs from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {Store,localStore} from './lib/store.mjs';
const root=path.dirname(fileURLToPath(import.meta.url));
process.env.SEEKDB_BINDINGS_CACHE_DIR??=path.join(root,'.runtime/native');
export function createApp(store){
 const app=express();app.disable('x-powered-by');
 app.use((req,res,next)=>{res.set({'Cross-Origin-Opener-Policy':'same-origin','Cross-Origin-Embedder-Policy':'require-corp'});next();});
 app.use(express.json({limit:'20mb'}));
 const endpoint=(fn)=>async(req,res,next)=>{try{res.json(await fn(req));}catch(e){next(e);}};
 app.get('/api/health',endpoint(async()=>({database:'seekdb',collections:(await store.list()).length,inference:'browser-only'})));
 app.get('/api/collections',endpoint(()=>store.list()));
 app.post('/api/import',endpoint(req=>store.import(req.body)));
 app.post('/api/search',endpoint(req=>store.search(req.body)));
 app.get('/api/model-manifest',endpoint(async()=>JSON.parse(await fs.readFile(path.join(root,'.runtime/model-manifest.json'),'utf8'))));
 app.use('/models',express.static(path.join(root,'.runtime/models')));
 app.use('/vendor/transformers',express.static(path.join(root,'node_modules/@huggingface/transformers/dist')));
 app.use('/vendor/ort',express.static(path.join(root,'node_modules/onnxruntime-web/dist')));
 app.get('/model-config.json',(_,res)=>res.sendFile(path.join(root,'model-config.json')));
 app.use('/data',express.static(path.join(root,'data')));
 app.use(express.static(path.join(root,'public')));
 app.use((err,req,res,next)=>{console.error(err.message);res.status(err.status||(/无效|须|不能为空|需要|每次/.test(err.message)?400:503)).json({error:err.message});});
 return app;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const store=process.env.SEEKDB_HOST?new Store({host:process.env.SEEKDB_HOST,port:Number(process.env.SEEKDB_PORT||2881),user:process.env.SEEKDB_USER||'root',password:process.env.SEEKDB_PASSWORD||'',database:process.env.SEEKDB_DATABASE||'test'}):await localStore(path.resolve(process.env.SEEKDB_PATH||path.join(root,'.runtime/seekdb')));
 await store.list();
 const server=createApp(store).listen(Number(process.env.PORT||8027),'127.0.0.1',()=>console.log('EdgeKB http://127.0.0.1:'+(process.env.PORT||8027)));
 for(const sig of ['SIGINT','SIGTERM'])process.on(sig,()=>server.close(async()=>{await store.close();process.exit(0);}));
}
