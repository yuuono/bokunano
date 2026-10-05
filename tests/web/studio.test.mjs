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
  assert.match(messages[2].content,/1\. 偶数だけを残す\n2\. 各要素を2倍する\n3\. 値を昇順に並べる\n4\. 現在の要素順を反転する/);
  assert.match(messages[3].content,/変更依頼: 2倍を3倍に変更してください/);
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

test('concrete integers are preserved separately from the trained CNL grammar', () => {
  for (const value of [3, -5, 0, 17]) {
    const plan = validateOperationPlan(`1. 各要素にkを加える\nk=${value}`);
    assert.equal(plan.valid, true);
    assert.equal(plan.kValue, value);
    assert.equal(plan.cnl, '整数リストxsと整数kを受け取り、各要素にkを加えるsolve関数を書いてください。');
  }
  assert.equal(validateOperationPlan('1. 各要素にkを加える').kValue, null);
  for (const suffix of ['k=1.5','k=NaN','k=9007199254740992','k=3\nk=5']) {
    assert.equal(validateOperationPlan(`1. 各要素にkを加える\n${suffix}`).valid, false);
  }
  assert.equal(validateOperationPlan('1. 偶数だけを残す\nk=3').valid, false);
});

test('revision keeps the numeric argument available for later edits', () => {
  const previous = validateOperationPlan('1. 各要素にkを加える\nk=3');
  const messages = buildRevisionMessages('5に変えて',previous.cnl,previous.kValue);
  assert.match(messages[2].content,/各要素にkを加える\nk=3/);
  assert.match(messages[3].content,/変更依頼: 5に変えて/);
});

test('numeric binding changes only the solve default, preserving model-generated logic', async () => {
  const { bindKDefault, parseK } = await import('../../web/cnl.js');
  const raw = 'def solve(xs: list[int], k: int) -> list[int]:\n    return [value + k for value in xs]\n';
  assert.equal(bindKDefault(raw,3), 'def solve(xs: list[int], k: int = 3) -> list[int]:\n    return [value + k for value in xs]\n');
  assert.equal(bindKDefault(raw,null),raw);
  assert.match(bindKDefault(raw,-5), /k: int = -5/);
  assert.equal(parseK(''),null);
  assert.equal(parseK('0'),0);
  assert.throws(()=>parseK('3.5'));
  assert.throws(()=>bindKDefault('def solve(xs):\n    return xs',3));
  assert.throws(()=>bindKDefault(raw,'3): print(1)'));
});

test('visible Boku prompt and encoded input preserve special tokens for both tokenizers', async () => {
  const { readFile } = await import('node:fs/promises');
  const { BokuNanoTokenizer, formatBokuPrompt } = await import('../../web/tokenizer.js');
  const instruction = '整数リストxsと整数kを受け取り、各要素にkを加えるsolve関数を書いてください。';
  const expected = `<|bos|><|task|>\n${instruction}\n<|code|>\n`;
  assert.equal(formatBokuPrompt(instruction), expected);
  for (const name of ['bpe-2048-minfreq5-maxlen24','bpe-2048-minfreq2-maxlen8']) {
    const data = JSON.parse(await readFile(new URL(`../../web/tokenizers/${name}.json`,import.meta.url)));
    const tokenizer = new BokuNanoTokenizer(data);
    const ids = tokenizer.encodePrompt(instruction);
    assert.deepEqual(ids.slice(0,2),[1,4]);
    assert.equal(ids.filter(id=>id===5).length,1);
    assert.equal(tokenizer.decode(ids),`\n${instruction}\n\n`);
    assert.deepEqual(ids,[1,4,...tokenizer.encodeText(`\n${instruction}\n`),5,...tokenizer.encodeText('\n')]);
  }
});

test('both 1M three-epoch models point to verified ONNX files and their training tokenizers', async () => {
  const { readFile } = await import('node:fs/promises');
  const { createHash } = await import('node:crypto');
  const manifest = JSON.parse(await readFile(new URL('../../web/model-manifest.json',import.meta.url)));
  assert.equal(new Set(manifest.models.map(model=>model.id)).size,10);
  for (const [id, directory, tokenizer] of [
    ['1m-3epoch','boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch','bpe-2048-minfreq5-maxlen24'],
    ['1m-short-3epoch','boku_nano_1m_bpe_2048_minfreq2_maxlen8_3epoch','bpe-2048-minfreq2-maxlen8'],
  ]) {
    const model = manifest.models.find(model=>model.id===id);
    const training = JSON.parse(await readFile(new URL(`../../data/models/${directory}/training_manifest.json`,import.meta.url)));
    const verified = JSON.parse(await readFile(new URL(`../../data/models/${directory}/onnx_manifest.json`,import.meta.url)));
    const bytes = await readFile(new URL(`../../web/${model.path}`,import.meta.url));
    assert.equal(training.epochs,3);
    assert.equal(model.source_sha256,training.model_sha256);
    assert.equal(model.parameter_count,1016704);
    assert.equal(model.tokenizer_id,tokenizer);
    assert.equal(manifest.tokenizers[tokenizer].sha256,training.tokenizer_sha256);
    assert.equal(createHash('sha256').update(bytes).digest('hex'),model.sha256);
    assert.equal(model.sha256,verified.onnx.sha256);
    assert.equal(bytes.length,model.size_bytes);
    assert.equal(model.verification.comparisons.length,2);
    assert.ok(model.verification.comparisons.every(item=>item.generated_tokens>0 && item.max_abs_diff<2e-4));
  }
});
