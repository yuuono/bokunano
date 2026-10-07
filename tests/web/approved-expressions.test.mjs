import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { APPROVED_OPERATION_EXPRESSIONS, APPROVED_EXPRESSION_METADATA } from '../../web/approved-expressions.js';
import { validateOperationPlan } from '../../web/cnl.js';
import { captureSelection, resolveSelection, validateExpectedPlan } from '../../web/chat-utils.js';

test('every released approved final/connective form resolves to its operation', () => {
  const source = readFileSync(new URL('../../' + APPROVED_EXPRESSION_METADATA.source, import.meta.url));
  assert.equal(createHash('sha256').update(source).digest('hex'), APPROVED_EXPRESSION_METADATA.source_sha256);
  assert.equal(APPROVED_EXPRESSION_METADATA.approved_records, 545);
  let count = 0;
  for (const [id, phrases] of Object.entries(APPROVED_OPERATION_EXPRESSIONS)) {
    for (const phrase of phrases) {
      const result = validateOperationPlan(phrase);
      assert.equal(result.valid, true, phrase);
      assert.deepEqual(result.operations.map(op => op.id), [id], phrase);
      count++;
    }
  }
  assert.equal(count, 1083);
});

test('approved synonyms retain meaning, ordering and numeric bindings without fuzzy guesses', () => {
  // Use actual approved variants selected independently from the human-reviewed release.
  const good = validateOperationPlan('各要素を二乗する\n大きい順に並べる\n最初のk個を取り出す');
  assert.equal(good.valid, true);
  assert.deepEqual(good.operations.map(op => op.id), ['map_square', 'order_descending', 'slice_first_k']);
  const expected = resolveSelection('各要素を二乗する、値を降順に並べる、先頭からk個を取る', captureSelection('各要素を二乗する、値を降順に並べる、先頭からk個を取る'));
  assert.equal(validateExpectedPlan(validateOperationPlan('各要素を二乗する\n小さい順に並べる\n最初のk個を取り出す'), expected).valid, false);
  assert.equal(validateOperationPlan('最初の3個を取り出す').kValue, 3);
  for (const bad of ['最初のk個だけを取り出る', '偶数を残さない', '中央値を求める']) {
    assert.equal(validateOperationPlan(bad).valid, false, bad);
  }
});
