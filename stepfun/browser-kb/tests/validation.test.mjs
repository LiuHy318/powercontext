import {test} from 'node:test';
import assert from 'node:assert/strict';
import {target,vector,records} from '../lib/validation.mjs';
import {metrics,median} from '../public/core.mjs';
test('collection identity changes with KB and precision, rejects unsafe names',()=>{assert.notEqual(target({kb:'a',precision:'q8'}),target({kb:'b',precision:'q8'}));assert.notEqual(target({kb:'a',precision:'q8'}),target({kb:'a',precision:'fp32'}));assert.throws(()=>target({kb:'a` DROP',precision:'q8'}));});
test('embedding validation rejects bad dimensions, NaN and zero vectors',()=>{assert.throws(()=>vector([1,0]));assert.throws(()=>vector(Array(384).fill(0)));const v=Array(384).fill(0);v[0]=1;assert.equal(vector(v),v);v[3]=NaN;assert.throws(()=>vector(v));});
test('import rejects duplicate identities rather than silently overwriting a batch',()=>{const v=Array(384).fill(0);v[0]=1;assert.throws(()=>records([{id:'a',text:'one',embedding:v},{id:'a',text:'two',embedding:v}]));});
test('quality metrics match hand-worked relevance cases',()=>{assert.deepEqual(metrics(['a','b','c'],['a','b'],3),{recall:1,ndcg:1});assert.equal(metrics(['c','d','e'],['a','b']).recall,0);assert.equal(metrics(['a','x','b'],['a','b']).recall,1);assert.ok(metrics(['a','x','b'],['a','b']).ndcg<1);assert.equal(median([9,1,7,3]),5);});
