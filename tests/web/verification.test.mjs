import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { CNL_OPERATIONS, validateOperationPlan } from '../../web/cnl.js';
import { captureSemanticAst, parseVerificationInputs } from '../../web/semantic-ast.js';

test('all 24 CNL operations map to the dataset AST, preserving order and repetition', () => {
  const atoms = readFileSync(new URL('../../data/semantic_asts/atomic_semantic_asts.jsonl', import.meta.url),'utf8').trim().split('\n').map(line=>JSON.parse(line).semantic_ast);
  CNL_OPERATIONS.forEach((operation, index) => {
    assert.deepEqual(captureSemanticAst(validateOperationPlan(operation.label)), atoms[index]);
  });
  const validation = validateOperationPlan('各要素にkを加える\n偶数だけを残す\n各要素にkを加える\n現在の要素順を反転する');
  const ast = captureSemanticAst(validation);
  assert.deepEqual(ast, {sequence:[atoms[10], atoms[0], atoms[10], atoms[20]]});
  validation.operations.reverse();
  assert.equal(ast.sequence[0].map[0], 'add_k');
  assert.throws(()=>ast.sequence.push(atoms[0]));
  assert.throws(()=>ast.sequence[0].map.push('abs'));
});

test('verification accepts the existing interpreter input domain including empty lists', () => {
  assert.deepEqual(parseVerificationInputs('[-100, 0, 100]', '10'),{xs:[-100,0,100],k:10});
  assert.deepEqual(parseVerificationInputs('[]', '1'),{xs:[],k:1});
  for (const xs of ['x', '{}', '[true]', '[1.5]', '[101]', JSON.stringify(Array(21).fill(1))]) assert.throws(()=>parseVerificationInputs(xs,'3'));
  for (const k of ['', '0', '-1', '11', '3.5']) assert.throws(()=>parseVerificationInputs('[]',k));
});

test('browser reference is an exact copy of the canonical interpreter', () => {
  assert.equal(readFileSync(new URL('../../web/reference_interpreter.py', import.meta.url),'utf8'),readFileSync(new URL('../../reference_interpreter.py', import.meta.url),'utf8'));
});

test('Python verification handles errors, isolation and four operations', () => {
  const result = spawnSync('python3', [new URL('./test_verification_runtime.py', import.meta.url).pathname], {encoding:'utf8'});
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test('the new runtime verifies every previously recorded single-operation code and detects known bad outputs', () => {
  const cases = [];
  for (const model of ['3epoch', '1epoch']) {
    const records = JSON.parse(readFileSync(new URL(`../../docs/results/chat_v10_single_operation_browser_${model}.json`, import.meta.url),'utf8')).results;
    for (const record of records) {
      const operation = CNL_OPERATIONS.find(op=>op.id === record.id);
      cases.push({model, id:record.id, code:record.code, semanticAst:captureSemanticAst(validateOperationPlan(operation.label))});
    }
  }
  const script = `import json, sys
sys.path.insert(0, 'web')
from verification_runtime import verify
cases = json.load(sys.stdin)
for case in cases:
    result = verify(dict(case, xs=[3, -1, 2, 0, -4, 5, 2], k=3))
    expected = 'code_error' if case['model']=='1epoch' and case['id']=='map_negate' else 'mismatch' if case['model']=='1epoch' and case['id']=='map_abs' else 'match'
    assert result['status'] == expected, (case['model'], case['id'], result)
`;
  const result = spawnSync('python3',['-c',script],{cwd:new URL('../..',import.meta.url),input:JSON.stringify(cases),encoding:'utf8'});
  assert.equal(result.status,0,result.stdout+result.stderr);
});
