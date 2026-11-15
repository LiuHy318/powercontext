import {build} from 'esbuild';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('../',import.meta.url));
await build({absWorkingDir:root,entryPoints:['src/embedding-worker.mjs'],outfile:'public/embedding-worker.mjs',bundle:true,format:'esm',platform:'browser',target:'es2022',logLevel:'info'});
