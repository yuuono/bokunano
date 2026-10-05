import test from 'node:test';
import assert from 'node:assert/strict';
import { appendOperationToDraft, nearBottom } from '../../web/chat-utils.js';
import { pythonTokens } from '../../web/python-highlight.js';

const four = '1. 偶数だけを残す\n2. 各要素を2倍する\n3. 値を昇順に並べる\n4. 現在の要素順を反転する';
test('operation selection drafts editable Japanese, retaining duplicates and numbers', () => {
  assert.equal(appendOperationToDraft('', 'map_abs'), '各要素を絶対値にしてください。');
  assert.equal(appendOperationToDraft('各要素を絶対値にしてください。', 'order_descending'), '各要素を絶対値にして、大きい順に並べてください。');
  assert.equal(appendOperationToDraft('偶数だけを残してください。', 'filter_even'), '偶数だけを残して、偶数だけを残してください。');
  assert.equal(appendOperationToDraft('1. 各要素にkを加える\nk=3', 'order_reverse'), '各要素にkを足して、要素の順番を逆にしてください。\nk=3');
  assert.equal(appendOperationToDraft('3を足して', 'order_reverse'), '3を足して\nその後、要素の順番を逆にしてください。');
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
