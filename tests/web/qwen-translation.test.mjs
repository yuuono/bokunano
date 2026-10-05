import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { translateWithRetry } from '../../web/qwen-translation.js';
import { captureSelection } from '../../web/chat-utils.js';

const instruction = '偶数だけを残して、各要素を2倍して、小さい順に並べてください。';
const good = '偶数だけを残す\n各要素を2倍する\n値を昇順に並べる';
const missing = '偶数だけを残す\n値を昇順に並べる';
async function run(input, outputs, selection = captureSelection(input)) {
  const calls = [], attempts = [];
  const result = await translateWithRetry({ instruction: input, selection,
    generate: async (messages, attempt) => {
      calls.push(structuredClone(messages));
      return outputs[attempt - 1];
    }, onAttempt: detail => attempts.push(detail),
  });
  return { result, calls, attempts };
}

test('omitted multiply step triggers a second actual generation with failure feedback', async () => {
  const { result, calls, attempts } = await run(instruction, [missing, good]);
  assert.equal(calls.length, 2);
  assert.equal(attempts[0].valid, false);
  assert.match(attempts[0].error, /欠落/);
  assert.equal(calls[1].at(-2).content, missing);
  assert.match(calls[1].at(-1).content, /各要素を2倍する/);
  assert.equal(result.supported, true);
  assert.equal(result.attempts, 2);
  assert.equal(result.plan, good);
  assert.equal(result.operations.length, 3);
});

test('two failures never return expected CNL as a successful model result', async () => {
  for (const bad of [missing, '対応できません。', 'k=整数', '各要素を2倍する\n偶数だけを残す\n値を昇順に並べる']) {
    const { result, calls, attempts } = await run(instruction, [bad, bad]);
    assert.equal(calls.length, 2);
    assert.deepEqual(attempts.map(x => x.valid), [false, false]);
    assert.equal(result.supported, false);
    assert.equal(result.cnl, '');
    assert.equal(result.plan, bad);
    assert.equal(result.operations, undefined);
  }
});

test('numeric omission or alteration retries instead of silently binding input k', async () => {
  for (const bad of ['各要素にkを加える', '各要素にkを加える\nk=5']) {
    const { result, attempts } = await run('各要素に3を足してください。', [bad, '各要素にkを加える\nk=3']);
    assert.equal(attempts[0].valid, false);
    assert.match(attempts[0].error, /k=3/);
    assert.equal(result.kValue, 3);
    assert.equal(result.attempts, 2);
  }
  const { result } = await run('kの倍数だけを残す', ['kの倍数だけを残す\nk=2', 'kの倍数だけを残す\nk=2']);
  assert.equal(result.supported, false);
});

test('duplicate operation counts are checked and successful first output returns immediately', async () => {
  const { result, attempts } = await run('各要素を2倍する、各要素を2倍する', ['各要素を2倍する', '各要素を2倍する\n各要素を2倍する']);
  assert.equal(attempts[0].valid, false);
  assert.equal(result.operations.length, 2);
  const goodFirst = await run(instruction, [good]);
  assert.equal(goodFirst.calls.length, 1);
  assert.equal(goodFirst.result.attempts, 1);
});

test('free text also retries invalid or unsupported output without injecting a known plan', async () => {
  const { result, calls } = await run('偶数を選んでほしい', ['対応できません。', '偶数だけを残す'], null);
  assert.equal(calls.length, 2);
  assert.equal(result.supported, true);
  assert.equal(result.plan, '偶数だけを残す');
});

test('all displayed examples have independent expected operation sequences for validation', () => {
  const html = readFileSync(new URL('../../web/index.html', import.meta.url), 'utf8');
  const examples = [...html.matchAll(/<dd data-example-instruction>(.*?)<\/dd>/g)];
  assert.equal(examples.length, 4);
  examples.forEach((match, i) => assert.equal(captureSelection(match[1]).ids.length, i + 1));
});
