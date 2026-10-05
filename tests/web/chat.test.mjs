import test from 'node:test';
import assert from 'node:assert/strict';
import { explicitOperationPlan, appendOperationToDraft, nearBottom } from '../../web/chat-utils.js';
import { pythonTokens } from '../../web/python-highlight.js';

const four = '1. 偶数だけを残す\n2. 各要素を2倍する\n3. 値を昇順に並べる\n4. 現在の要素順を反転する';
test('explicit four-operation input preserves every step without a Qwen round trip', () => {
  const result = explicitOperationPlan(four);
  assert.equal(result.valid, true);
  assert.equal(result.experimental, true);
  assert.deepEqual(result.operations.map(op => op.id), ['filter_even','map_mul_2','order_ascending','order_reverse']);
  assert.equal(explicitOperationPlan(four + '\n5. 偶数だけを残す').valid, false);
  assert.equal(explicitOperationPlan('1. 自由に処理する'), null);
  assert.equal(explicitOperationPlan('各要素に3を足して'), null);
  assert.equal(explicitOperationPlan(four, true), null);
  assert.equal(explicitOperationPlan('1. 各要素にkを加える\nk=-3').kValue, -3);
});
test('operation insertion retains duplicates, numbers and free text, with a four-step limit', () => {
  assert.equal(appendOperationToDraft('', 'filter_even'), '1. 偶数だけを残す');
  assert.equal(appendOperationToDraft('1. 偶数だけを残す', 'filter_even'), '1. 偶数だけを残す\n2. 偶数だけを残す');
  assert.equal(appendOperationToDraft('1. 各要素にkを加える\nk=3', 'order_reverse'), '1. 各要素にkを加える\n2. 現在の要素順を反転する\nk=3');
  assert.equal(appendOperationToDraft('3を足して', 'order_reverse'), '3を足して\n現在の要素順を反転する');
  assert.throws(() => appendOperationToDraft(four, 'order_reverse'), /4つまで/);
  assert.throws(() => appendOperationToDraft('', 'not_an_operation'));
});
test('auto-scroll follows the end without pulling a reader away from older messages', () => {
  assert.equal(nearBottom({scrollHeight:1200,clientHeight:500,scrollTop:700}), true);
  assert.equal(nearBottom({scrollHeight:1200,clientHeight:500,scrollTop:650}), true);
  assert.equal(nearBottom({scrollHeight:1200,clientHeight:500,scrollTop:200}), false);
  assert.equal(nearBottom({scrollHeight:500,clientHeight:500,scrollTop:0}), true);
});
test('Python highlighting preserves exact code, indentation and HTML-like strings', () => {
  const code = 'def solve(xs: list[int], k: int = 3) -> list[int]:\n    # return 42\n    note = "<img src=x onerror=alert(1)>"\n    return [x + k for x in xs]\n';
  const tokens = pythonTokens(code);
  assert.equal(tokens.map(t => t.text).join(''), code);
  assert.ok(tokens.some(t => t.kind==='function' && t.text==='solve'));
  assert.ok(tokens.some(t => t.kind==='number' && t.text==='3'));
  assert.ok(tokens.some(t => t.kind==='string' && t.text.includes('<img')));
  assert.ok(tokens.some(t => t.kind==='comment' && t.text==='# return 42'));
  for (const partial of ['def ', '"unfinished', "'''multi\nline", 'x = 1e-3', 'value123 = -42']) {
    assert.equal(pythonTokens(partial).map(t => t.text).join(''), partial);
  }
});
