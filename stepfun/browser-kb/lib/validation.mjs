import model from '../model-config.json' with {type:'json'};
export const DIMENSION = model.dimension;
export function target({kb,precision}) {
 if(typeof kb!=='string'||!/^[a-z0-9_-]{1,30}$/.test(kb)) throw new Error('知识库名称须为 1–30 位英文、数字、下划线或连字符');
 if(!['fp32','fp16','q8'].includes(precision)) throw new Error('无效模型精度');
 return `edgekb_${kb}_${precision}_${model.revision.slice(0,8)}`;
}
export function vector(v) {
 if(!Array.isArray(v)||v.length!==DIMENSION||v.some(x=>typeof x!=='number'||!Number.isFinite(x))) throw new Error(`向量须为 ${DIMENSION} 维有限数值`);
 const norm=v.reduce((s,x)=>s+x*x,0); if(norm<0.5||norm>1.5) throw new Error('需要归一化且非零的浏览器向量');
 return v;
}
export function records(rows) {
 if(!Array.isArray(rows)||!rows.length||rows.length>500) throw new Error('每次请导入 1–500 条分块');
 const ids=new Set();
 return rows.map(row=>{
  if(typeof row.id!=='string'||!/^[a-zA-Z0-9_-]{1,80}$/.test(row.id)||ids.has(row.id))throw new Error('文档 ID 无效或重复');
  ids.add(row.id);
  if(typeof row.text!=='string'||!row.text.trim()||row.text.length>12000)throw new Error('文档分块须为 1–12000 字符');
  return {id:row.id,text:row.text,title:String(row.title||row.id).slice(0,200),embedding:vector(row.embedding)};
 });
}
