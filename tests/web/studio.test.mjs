import test from 'node:test';
import assert from 'node:assert/strict';
import { validateCnl, CNL_OPERATIONS, buildNormalizerSystemPrompt, buildNormalizerUserPrompt, buildNormalizerMessages, buildRevisionMessages, numberedSteps, validateOperationPlan } from '../../web/cnl.js';
import { selectToken, temperatureProbabilities, qwenSamplingOptions } from '../../web/sampling.js';

const cnl = parts => `整数リストxsから${parts.join('、')}solve関数を書いてください。`;
const four = cnl(['偶数だけを残し', '各要素を2倍し', '値を昇順に並べ', '現在の要素順を反転する']);
test('four operations are accepted as experimental, five remain rejected', () => {
  assert.equal(CNL_OPERATIONS.length, 24);
  const result = validateCnl(four);
  assert.equal(result.valid, true);
  assert.equal(result.experimental, true);
  assert.deepEqual(result.operations.map(op => op.id), ['filter_even','map_mul_2','order_ascending','order_reverse']);
  assert.equal(validateCnl(cnl(['偶数だけを残す'])).experimental, false);
  assert.equal(validateCnl(cnl(['偶数だけを残し','各要素を2倍し','各要素を3倍し','値を昇順に並べ','現在の要素順を反転する'])).valid, false);
});
test('CNL still checks allowed operations, k prefix, forms, and line count', () => {
  assert.equal(validateCnl(cnl(['合計値を求める'])).valid, false);
  assert.equal(validateCnl(cnl(['各要素にkを加える'])).valid, false);
  assert.equal(validateCnl('整数リストxsと整数kを受け取り、先頭からk個を取るsolve関数を書いてください。').valid, true);
  assert.equal(validateCnl(cnl(['偶数だけを残す','各要素を2倍する'])).valid, false);
  assert.equal(validateCnl(four+'\n説明です。').valid, false);
});
test('retry retains the current request and validation error', () => {
  const retry = buildNormalizerUserPrompt('最後に逆順にして','不正な出力','文法エラー');
  assert.match(retry,/入力: 最後に逆順にして/);
  assert.match(retry,/前回の出力: 不正な出力/);
  assert.match(buildNormalizerSystemPrompt(),/1～4操作/);
  assert.match(buildNormalizerSystemPrompt(),/5操作以上/);
});
test('temperature zero is deterministic greedy even when random would select another candidate', () => {
  assert.equal(selectToken([2,3,1],0,()=>{throw Error('no random for greedy');}),1);
  assert.equal(selectToken([2,2,1],0),0);
  assert.deepEqual(qwenSamplingOptions(0),{do_sample:false});
});
test('normalization supplies the current instruction after the system constraints', () => {
  const messages = buildNormalizerMessages('偶数を残して');
  assert.deepEqual(messages.map(message => message.role), ['system','user']);
  assert.match(messages[1].content,/偶数を残して/);
});
test('revision receives all previous operations in order and the new request', () => {
  const messages = buildRevisionMessages('2倍を3倍に変更してください',four);
  assert.match(messages[1].content,/1\. 偶数だけを残す\n2\. 各要素を2倍する\n3\. 値を昇順に並べる\n4\. 現在の要素順を反転する/);
  assert.match(messages[1].content,/変更依頼: 2倍を3倍に変更してください/);
  assert.throws(()=>buildRevisionMessages('逆順にして','不正なCNL'));
});
test('only a complete numbered list defines an operation count for omission checks', () => {
  assert.deepEqual(numberedSteps('1. 偶数を残す\n2. 3倍する'),['偶数を残す','3倍する']);
  assert.deepEqual(numberedSteps('1. 偶数を残す\n3. 3倍する'),[]);
  assert.deepEqual(numberedSteps('説明\n1. 偶数を残す'),[]);
});
test('temperature probabilities match known values and flatten as T increases', () => {
  const p = temperatureProbabilities([2,1,0],1);
  assert.ok(Math.abs(p[0]-.6652409558)<1e-9);
  assert.ok(Math.abs(p.reduce((a,b)=>a+b,0)-1)<1e-12);
  assert.ok(temperatureProbabilities([2,1,0],.5)[0]>p[0]);
  assert.ok(temperatureProbabilities([2,1,0],2)[0]<p[0]);
  assert.equal(selectToken([2,1,0],1,()=>.95),2);
  assert.equal(selectToken([2,1,0],1,()=>.1),0);
});
test('softmax remains stable for extreme logits and tiny positive T', () => {
  assert.deepEqual([...temperatureProbabilities([10000,10000,-10000],.01)],[.5,.5,0]);
  assert.deepEqual([...temperatureProbabilities([10000,9999],Number.MIN_VALUE)],[1,0]);
  assert.equal(selectToken([-10000,-10001],1,()=>0),0);
});
test('invalid settings fail explicitly and Qwen uses the chosen positive temperature', () => {
  for (const t of [-1,Infinity,NaN,2.1]) assert.throws(()=>selectToken([1,2],t));
  assert.throws(()=>selectToken([],0));
  assert.throws(()=>selectToken([NaN,1],1));
  assert.throws(()=>temperatureProbabilities([1,2],0));
  assert.deepEqual(qwenSamplingOptions(.7),{do_sample:true,temperature:.7,top_k:0,top_p:1});
});

test('Qwen-selected labels serialize without losing order, k, or a fourth operation', () => {
  const result = validateOperationPlan('1. 偶数だけを残す\n2. 各要素を3倍する\n3. 値を昇順に並べる\n4. 現在の要素順を反転する');
  assert.equal(result.valid,true);
  assert.equal(result.experimental,true);
  assert.deepEqual(result.operations.map(op=>op.id),['filter_even','map_mul_3','order_ascending','order_reverse']);
  assert.equal(validateOperationPlan('1. 先頭からk個を取る').usesK,true);
  assert.equal(validateOperationPlan('1. 整数を自由に処理する').valid,false);
  assert.equal(validateOperationPlan('1. 各要素を2倍する\n2. 各要素を2倍する').operations.length,2);
  assert.equal(validateOperationPlan('1. 偶数だけを残す\n2. 各要素を2倍する\n3. 各要素を3倍する\n4. 値を昇順に並べる\n5. 現在の要素順を反転する').valid,false);
});
