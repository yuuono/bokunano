import test from 'node:test';
import assert from 'node:assert/strict';
import { appendOperationToDraft, nearBottom } from '../../web/chat-utils.js';
import { pythonTokens } from '../../web/python-highlight.js';
import { buildConversationMessages, validateOperationPlan } from '../../web/cnl.js';

test('unified chat retains context for free follow-ups but explicit choices start their own plan', () => {
  const previous = validateOperationPlan('各要素にkを加える');
  const followup = buildConversationMessages('kを5に変えて', previous.cnl, 3);
  assert.equal(followup.length, 4);
  assert.match(followup[2].content, /k=3/);
  assert.match(followup[3].content, /今回の依頼: kを5に変えて/);
  assert.match(followup[0].content, /新しい手順として置き換え/);
  const selected = buildConversationMessages('偶数のみを抽出して', previous.cnl, 3, true);
  assert.equal(selected.length, 2);
  assert.doesNotMatch(selected[1].content, /k=3/);
});

const four = '1. 偶数だけを残す\n2. 各要素を2倍する\n3. 値を昇順に並べる\n4. 現在の要素順を反転する';
test('operation selection drafts editable Japanese, retaining duplicates and numbers', () => {
  assert.equal(appendOperationToDraft('', 'map_abs'), 'それぞれの数を絶対値にしてください。');
  assert.equal(appendOperationToDraft('それぞれの数を絶対値にしてください。', 'order_descending'), 'それぞれの数を絶対値にして、大きいものから順番に並べてください。');
  assert.equal(appendOperationToDraft('偶数だけを残してください。', 'filter_even'), '偶数のみを抽出して、偶数のみを抽出してください。');
  assert.equal(appendOperationToDraft('1. 各要素にkを加える\nk=3', 'order_reverse'), 'それぞれの数にkを足して、今の並びを後ろから逆順にしてください。\nk=3');
  assert.equal(appendOperationToDraft('3を足して', 'order_reverse'), '3を足して\nその後、今の並びを後ろから逆順にしてください。');
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

test('known input validates Qwen output without replacing malformed output', async () => {
  const { captureSelection, resolveSelection, validateExpectedPlan } = await import('../../web/chat-utils.js');
  const { CNL_OPERATIONS, operationRequest } = await import('../../web/cnl.js');
  for (const operation of CNL_OPERATIONS) {
    const text = operationRequest([operation]);
    const snapshot = captureSelection(text);
    const expected = resolveSelection(text, snapshot);
    assert.equal(expected.operations[0].id, operation.id);
    for (const badOutput of ['k=整数', '対応できません。', '各要素を三倍する\n各要素の絶対値を取る\n各要素を2倍する']) {
      const checked = validateExpectedPlan(validateOperationPlan(badOutput), expected);
      assert.equal(checked.valid, false);
      assert.equal(checked.cnl, '');
    }
    assert.equal(resolveSelection(text + '最後に逆順にして', snapshot), null);
    assert.equal(resolveSelection(text, null), null);
    const generated = validateOperationPlan(text);
    assert.equal(validateExpectedPlan(generated, expected), generated);
  }
});
