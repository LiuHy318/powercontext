import {chromium} from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';
const root=path.resolve(import.meta.dirname,'..');
const md=await fs.readFile(path.join(root,'TECHNICAL_NOTE.md'),'utf8');
const escape=s=>s.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
const inline=s=>escape(s).replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/`([^`]+)`/g,'<code>$1</code>');
let html='',table=false;
for(const block of md.trim().split(/\n\s*\n/)){
 if(block.startsWith('# ')){html+='<h1>'+inline(block.slice(2))+'</h1>';continue;}
 if(block.startsWith('|')){html+='<table>';for(const row of block.split('\n')){if(/^\|[-:| ]+\|$/.test(row))continue;html+='<tr>'+row.slice(1,-1).split('|').map(c=>'<td>'+inline(c.trim())+'</td>').join('')+'</tr>';}html+='</table>';continue;}
 html+='<p>'+inline(block.replaceAll('\n',' '))+'</p>';
}
const document='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>EdgeKB 一页技术说明</title><style>@page{size:A4;margin:11mm}body{font:9pt/1.32 "Microsoft YaHei",sans-serif;color:#172c3a}h1{font-size:15pt;margin:0 0 9px;color:#087e8b}p{margin:7px 0}table{width:100%;border-collapse:collapse;font-size:8.4pt;margin:8px 0}td{border:1px solid #ccd9dd;padding:4px}tr:first-child{background:#e8f3f4;font-weight:bold}code{font:8.3pt ui-monospace,monospace;overflow-wrap:anywhere}strong{color:#123e49}</style>'+html+'</html>';
await fs.writeFile(path.join(root,'TECHNICAL_NOTE.html'),document);
const browser=await chromium.launch({channel:'chrome',headless:true});try{const page=await browser.newPage();await page.setContent(document);await page.pdf({path:path.join(root,'TECHNICAL_NOTE.pdf'),format:'A4',printBackground:true,preferCSSPageSize:true});}finally{await browser.close();}
console.log('Rendered technical note HTML/PDF');
