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
  assert.equal(calls[1].some(message => message.role === 'assistant'), false);
  assert.equal(attempts[0].plan, missing);
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
  assert.equal(examples.length, 12);
  examples.forEach((match, i) => assert.equal(captureSelection(match[1]).ids.length, Math.floor(i / 3) + 1));
});

test('an unreadable phrase does not hide the descending order from Qwen repair feedback', async () => {
  const input = 'それぞれの数を2乗して、大きい順に並べて、最初のk個だけを取り出してください。';
  const bad = '- 各要素を二乗する\n- 値を昇順に並べる\n- 最初のk個だけを取り出る';
  const correct = '各要素を二乗する\n値を降順に並べる\n先頭からk個を取る';
  const { result, calls, attempts } = await run(input, [bad, correct]);
  assert.equal(attempts[0].valid, false);
  assert.match(calls[1].at(-1).content, /各要素を二乗する\n値を降順に並べる\n先頭からk個を取る/);
  assert.doesNotMatch(calls[1].at(-1).content, /取り出る/);
  assert.match(calls[1].at(-1).content, /入力にないkの数値を補わない/);
  assert.equal(result.supported, true);
  assert.equal(result.plan, correct);
  assert.deepEqual(result.operations.map(op => op.id), ['map_square', 'order_descending', 'slice_first_k']);

  // Merely fixing the typo must not accept the original wrong sorting direction.
  for (const second of [bad, '各要素を二乗する\n値を昇順に並べる\n先頭からk個を取る']) {
    const failed = await run(input, [bad, second]);
    assert.equal(failed.calls.length, 2);
    assert.equal(failed.result.supported, false);
    assert.equal(failed.result.cnl, '');
  }
});

test('Qwen approved wording is accepted without replacing its output or retrying', async () => {
  const input = 'それぞれの数を2乗して、大きい順に並べて、最初のk個だけを取り出してください。';
  const output = '値を二乗する\n大きい順に並べる\n最初のk個を取り出す';
  const { result, calls } = await run(input, [output]);
  assert.equal(calls.length, 1);
  assert.equal(result.supported, true);
  assert.equal(result.plan, output);
  assert.deepEqual(result.operations.map(op => op.id), ['map_square', 'order_descending', 'slice_first_k']);
});


test('new requests exclude all previous operations and k even after a four-operation turn', async () => {
  const { validateOperationPlan, buildConversationMessages, usesConversationContext } = await import('../../web/cnl.js');
  const previous = validateOperationPlan('kの倍数だけを残す、各要素を二乗する、先頭から1個おきに取る、現在の要素順を反転する\nk=7');
  for (const input of ['偶数のみ抽出', '各要素に3を足してください。', 'それぞれの数を2倍にしてください。', '整数リストの中央値を求めてください。']) {
    assert.equal(usesConversationContext(input), false);
    const messages = buildConversationMessages(input, previous.cnl, 7);
    assert.equal(messages.length, 2);
    assert.equal(messages[1].content, `入力: ${input}\n出力:`);
    assert.equal(messages.some(m => m.role === 'assistant'), false);
  }
  const calls = [];
  await translateWithRetry({ instruction: '偶数のみ抽出', contextCnl: previous.cnl, contextK: 7,
    generate: async messages => { calls.push(structuredClone(messages)); return '偶数だけを残す'; },
  });
  assert.equal(calls[0].length, 2);
  assert.doesNotMatch(calls[0][1].content, /二乗|k=7/);
});

test('explicit follow-ups retain the previous sequence and numeric argument', async () => {
  const { validateOperationPlan, buildConversationMessages } = await import('../../web/cnl.js');
  const previous = validateOperationPlan('各要素にkを加える');
  for (const input of ['前の処理に逆順を追加して', 'その結果を昇順にして', 'kを5に変えて']) {
    const messages = buildConversationMessages(input, previous.cnl, 3);
    assert.equal(messages.length, 4);
    assert.match(messages[2].content, /各要素にkを加える/);
    assert.match(messages[2].content, /k=3/);
    assert.match(messages[3].content, new RegExp(input));
  }
});
