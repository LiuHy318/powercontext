"""Download published, pinned ONNX weights only. No embedding inference here."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
config = json.loads((ROOT/'model-config.json').read_text())
files = ['config.json','tokenizer.json','tokenizer_config.json','special_tokens_map.json',*config['files'].values()]
endpoint = os.environ.get('HF_ENDPOINT','https://huggingface.co').rstrip('/')
directory = ROOT/'.runtime/models'/config['id']
directory.mkdir(parents=True,exist_ok=True)
def download(name):
    path = directory/name
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        url = f"{endpoint}/{config['id']}/resolve/{config['revision']}/{name}"
        with requests.get(url,stream=True,timeout=(20,90)) as response:
            response.raise_for_status()
            with path.with_suffix(path.suffix+'.part').open('wb') as f:
                for block in response.iter_content(1024*1024): f.write(block)
        path.with_suffix(path.suffix+'.part').replace(path)
    data = path.read_bytes()
    result = {'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    print(name, len(data), flush=True)
    return result
with ThreadPoolExecutor(max_workers=3) as pool: manifest = list(pool.map(download,files))
report = {'model':config,'source':endpoint,'files':manifest}
(ROOT/'.runtime/model-manifest.json').write_text(json.dumps(report,indent=2)+'\n')
print('Model download and actual file hashes complete',flush=True)
