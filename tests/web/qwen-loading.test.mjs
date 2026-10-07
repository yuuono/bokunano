import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { qwenRuntimeFailure } from '../../web/qwen-errors.js';

test('1.7B downloads both the external graph and weights with pinned provenance', () => {
  const catalog = JSON.parse(readFileSync(new URL('../../web/qwen-manifest.json', import.meta.url)));
  const model = catalog.models.find(model => model.label === 'Qwen3-1.7B');
  assert.equal(model.dtype, 'q4f16');
  assert.equal(model.model_file, 'onnx/model_q4f16.onnx');
  assert.ok(model.model_file_size_bytes < 1024 * 1024, 'keep embedded weights out of the protobuf graph');
  assert.equal(model.external_data_files.length, 1);
  assert.equal(model.external_data_files[0].path, model.model_file + '_data');
  assert.equal(model.download_size_bytes, model.model_file_size_bytes + model.external_data_files[0].size_bytes);
  assert.match(model.revision, /^[a-f0-9]{40}$/);
  assert.match(model.external_data_files[0].sha256, /^[a-f0-9]{64}$/);
  assert.equal(model.source_model.model_id, 'onnx-community/Qwen3-1.7B-ONNX');
  assert.equal(catalog.default_model_id, catalog.models[0].model_id);
});

test('loading and memory failures do not blame the instruction', () => {
  const memory = qwenRuntimeFailure("Can't create a session. ERROR_CODE: 6, ERROR_MESSAGE: std::bad_alloc", 'loading', 'Qwen3-1.7B');
  assert.match(memory, /Qwen3-1.7B.*メモリ/);
  assert.doesNotMatch(memory, /指示を見直/);
  assert.match(qwenRuntimeFailure('Failed to fetch', 'loading'), /読み込めません/);
  assert.match(qwenRuntimeFailure('device lost', 'generation'), /実行中/);
});
