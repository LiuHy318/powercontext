import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const result=spawnSync(process.env.PYTHON||'python',[fileURLToPath(new URL('./download_models.py',import.meta.url))],{stdio:'inherit'});
process.exit(result.status??1);
