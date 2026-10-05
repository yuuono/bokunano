import test from 'node:test';
import assert from 'node:assert/strict';
import { PromptHistory, canRecallPrompt } from '../../web/prompt-history.js';

test('up recalls sent prompts in reverse order and down restores the unsent draft', () => {
  const history = new PromptHistory();
  assert.equal(history.move(-1, 'draft'), null);
  history.add('偶数だけを残す');
  history.add('各要素を2倍する');
  assert.equal(history.move(-1, '入力途中'), '各要素を2倍する');
  assert.equal(history.move(-1, '各要素を2倍する'), '偶数だけを残す');
  assert.equal(history.move(-1, '偶数だけを残す'), null);
  assert.equal(history.move(1, '偶数だけを残す'), '各要素を2倍する');
  assert.equal(history.move(1, '各要素を2倍する'), '入力途中');
  assert.equal(history.move(1, '入力途中'), null);
});

test('edits become a new draft without mutating sent messages; new conversation clears history', () => {
  const history = new PromptHistory();
  history.add('最初の指示');
  history.move(-1, '');
  history.resetDraft('編集した指示');
  assert.equal(history.move(-1, '編集した指示'), '最初の指示');
  assert.equal(history.move(1, '最初の指示'), '編集した指示');
  history.add('編集した指示');
  assert.equal(history.move(-1, ''), '編集した指示');
  history.clear();
  assert.equal(history.move(-1, ''), null);
});

test('multiline prompts and duplicate sends are preserved exactly', () => {
  const history = new PromptHistory();
  const text = '偶数だけを残す\n各要素を2倍する';
  history.add(text);
  history.add(text);
  assert.equal(history.move(-1, ''), text);
  assert.equal(history.move(-1, text), text);
  assert.equal(history.move(1, text), text);
  assert.equal(history.move(1, text), '');
});

test('arrows preserve IME, modified shortcuts, selection and multiline caret navigation', () => {
  const input = {value: 'first\nsecond', selectionStart: 3, selectionEnd: 3};
  assert.equal(canRecallPrompt({key:'ArrowUp'}, input), true);
  assert.equal(canRecallPrompt({key:'ArrowDown'}, input), false);
  const lastLine = {...input, selectionStart: 9, selectionEnd: 9};
  assert.equal(canRecallPrompt({key:'ArrowUp'}, lastLine), false);
  assert.equal(canRecallPrompt({key:'ArrowDown'}, lastLine), true);
  for (const flag of [{isComposing:true}, {keyCode:229}, {shiftKey:true}, {ctrlKey:true}, {metaKey:true}, {altKey:true}]) {
    assert.equal(canRecallPrompt({key:'ArrowUp', ...flag}, input), false);
  }
  assert.equal(canRecallPrompt({key:'ArrowUp'}, {...input, selectionEnd:5}), false);
  assert.equal(canRecallPrompt({key:'Enter'}, input), false);
});
