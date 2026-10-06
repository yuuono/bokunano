"""Evaluate official Qwen3-4B-AWQ weights expanded to FP16 on Apple MPS.

No requantization or replacement with the original unquantized model. AWQ GEMM
packing follows AutoAWQ awq/utils/packing_utils.py (AWQ_REVERSE_ORDER).
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import gc
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import time

ROOT = Path(__file__).resolve().parents[2]
MODEL_ID = 'Qwen/Qwen3-4B-AWQ'
REVISION = '74d4bd2bd4bff9cafc9345221320bffb08b406a3'
REVERSE = [0, 4, 1, 5, 2, 6, 3, 7]


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda: f.read(8 * 1024 * 1024), b''):
            digest.update(data)
    return digest.hexdigest()


def unpack(packed):
    import torch
    shifts = torch.arange(0, 32, 4, dtype=torch.int32)
    values = ((packed.unsqueeze(-1) >> shifts) & 15)
    return values[:, :, REVERSE].reshape(packed.shape[0], -1)


def dequantize(qweight, qzeros, scales, group_size=128):
    """Return the PyTorch Linear [out_features, in_features] weight."""
    weights = unpack(qweight)
    zeros = unpack(qzeros).repeat_interleave(group_size, dim=0)
    assert weights.shape == zeros.shape
    return ((weights - zeros) * scales.repeat_interleave(group_size, dim=0)).T.contiguous()


def validate_decoder():
    """Independent scalar packing/decoding exercises all 16 codes and groups."""
    import torch
    group = 128
    ints = (torch.arange(256 * 16).reshape(256, 16) * 7 + 3) % 16
    zeros = torch.tensor([[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
                          [15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0]])
    scales = torch.arange(1, 33).reshape(2, 16).half() / 64
    order = [0, 2, 4, 6, 1, 3, 5, 7]
    def pack(values):
        words = []
        for row in values.tolist():
            packed_row = []
            for j in range(0, len(row), 8):
                word = sum(row[j + order[k]] << (4 * k) for k in range(8))
                packed_row.append(word if word < 2**31 else word - 2**32)
            words.append(packed_row)
        return torch.tensor(words, dtype=torch.int32)
    actual = dequantize(pack(ints), pack(zeros), scales, group)
    expected = ((ints - zeros.repeat_interleave(group, 0)) * scales.repeat_interleave(group, 0)).T
    assert torch.equal(actual, expected)
    return {'synthetic_all_nibbles_groups_signed_words': 'exact_match'}


def load_model(model_path):
    import torch
    from accelerate import init_empty_weights
    from safetensors.torch import load_file
    from transformers import Qwen3Config, Qwen3ForCausalLM
    config = json.loads((model_path / 'config.json').read_text())
    quant = config.pop('quantization_config')
    assert quant['bits'] == 4 and quant['group_size'] == 128 and quant['version'].lower() == 'gemm' and quant['zero_point']
    assert config['tie_word_embeddings']
    state = load_file(model_path / 'model.safetensors', device='cpu')
    prefixes = sorted(k.removesuffix('.qweight') for k in state if k.endswith('.qweight'))
    assert len(prefixes) == config['num_hidden_layers'] * 7 == 252
    for i, prefix in enumerate(prefixes):
        qw = state.pop(prefix + '.qweight'); qz = state.pop(prefix + '.qzeros'); scales = state.pop(prefix + '.scales')
        weight = dequantize(qw, qz, scales)
        # Compare selected actual checkpoint entries against scalar bit decoding.
        for row, col in [(0, 0), (127, 7), (128, 8), (qw.shape[0]-1, weight.shape[0]-1)]:
            shift = REVERSE[col % 8] * 4
            integer = (int(qw[row, col // 8]) >> shift) & 15
            zero = (int(qz[row // 128, col // 8]) >> shift) & 15
            expected = torch.tensor(integer-zero, dtype=torch.float16) * scales[row // 128, col]
            assert torch.equal(weight[col, row], expected)
        state[prefix + '.weight'] = weight
        if (i+1) % 42 == 0:
            print(f'Expanded AWQ linear layers {i+1}/{len(prefixes)}', flush=True)
    assert not any(k.endswith(('.qweight', '.qzeros', '.scales')) for k in state)
    runtime_config = Qwen3Config(**config)
    runtime_config._attn_implementation = 'eager'
    with init_empty_weights():
        model = Qwen3ForCausalLM(runtime_config)
    if 'lm_head.weight' not in state:
        state['lm_head.weight'] = state['model.embed_tokens.weight']
    model.load_state_dict(state, strict=True, assign=True)
    model.tie_weights()
    del state
    gc.collect()
    model = model.to(device='mps', dtype=torch.float16).eval()
    return model, {'quantized_linear_layers': len(prefixes), 'scalar_checkpoint_checks': 4 * len(prefixes),
                   'load_state_dict': 'strict', 'runtime_dtype': 'float16', 'original_quantization': quant}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-path', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    import torch
    from transformers import AutoTokenizer, GenerationConfig
    assert torch.backends.mps.is_available(), 'Apple MPS is required'
    args.run.mkdir(parents=True, exist_ok=True)
    output = args.run / 'raw_inference.jsonl'
    if output.exists():
        raise ValueError('Use a fresh run directory; do not overwrite or select regenerated answers')
    question_path = ROOT / 'data/benchmarks/browser_100/dev50.jsonl'
    questions = [json.loads(s) for s in question_path.read_text().splitlines()]
    prior_path = ROOT / 'data/benchmarks/browser_100/runs/dev50-20261005/raw_inference.jsonl'
    prior = {r['question_id']: r for r in map(json.loads, prior_path.read_text().splitlines())
             if r['kind'] == 'inference' and r['model'] == 'qwen' and r['condition'] == 'A'}
    tokenizer = AutoTokenizer.from_pretrained(args.model_path, local_files_only=True, trust_remote_code=False)
    prompts = []
    for q in questions:
        old = prior[q['question_id']]
        assert old['messages'][-1]['content'] == q['instruction_ja']
        prompt = tokenizer.apply_chat_template(old['messages'], tokenize=False, add_generation_prompt=True, enable_thinking=False)
        assert prompt == old['prompt'], 'Prompt template differs from the original Qwen comparison'
        prompts.append((q, old['messages'], prompt))
    config = {'run_id': args.run.name, 'model_id': MODEL_ID, 'revision': REVISION, 'model': 'qwen3-4b-awq',
              'conditions': ['A'], 'question_count': 50, 'questions_sha256': sha(question_path),
              'backend': 'pytorch-mps', 'weight_loading': 'AWQ GEMM unpacked/dequantized to FP16; no requantization',
              'temperature': 0, 'do_sample': False, 'repetition_penalty': 1, 'max_new_tokens': 512,
              'enable_thinking': False, 'history': False, 'attention_implementation': 'eager',
              'prompt_matches_original_qwen': True, 'versions': {p: importlib.metadata.version(p) for p in ['torch', 'transformers', 'accelerate', 'safetensors', 'tokenizers']}}
    (args.run / 'config.json').write_text(json.dumps(config, ensure_ascii=False, indent=2)+'\n')
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in [Path(__file__).resolve(), question_path, ROOT/'scripts/model/score_browser_100_benchmark.py', ROOT/'reference_interpreter.py', ROOT/'generated_code_verifier.py']}
    hashes.update({f'model/{p.name}': sha(p) for p in sorted(args.model_path.iterdir()) if p.is_file()})
    (args.run / 'source_hashes.json').write_text(json.dumps(hashes, indent=2)+'\n')
    validation = validate_decoder()
    model, checks = load_model(args.model_path)
    validation.update(checks)
    assert model.config._attn_implementation == 'eager'
    (args.run / 'loading_validation.json').write_text(json.dumps(validation, indent=2)+'\n')
    generation = GenerationConfig.from_pretrained(args.model_path, local_files_only=True)
    generation.do_sample = False; generation.temperature = None; generation.top_p = None; generation.top_k = None
    generation.max_new_tokens = 512; generation.repetition_penalty = 1
    def record(data):
        with output.open('a') as f:
            f.write(json.dumps({'run_id': args.run.name, **data}, ensure_ascii=False)+'\n')
            f.flush()
    record({'kind': 'environment', 'started_at': datetime.now(timezone.utc).isoformat(),
            'platform': platform.platform(), 'machine': platform.machine(), 'backend': 'pytorch-mps',
            'mps_recommended_max_memory': torch.mps.recommended_max_memory(), 'config': config,
            'generation_config': generation.to_dict()})
    for index, (q, messages, prompt) in enumerate(prompts, 1):
        encoded = tokenizer(prompt, return_tensors='pt', add_special_tokens=False).to('mps')
        torch.mps.synchronize(); started = time.perf_counter()
        with torch.inference_mode():
            ids = model.generate(**encoded, generation_config=generation)
        torch.mps.synchronize()
        elapsed = time.perf_counter()-started
        output_ids = ids[0, encoded['input_ids'].shape[1]:].tolist()
        eos = generation.eos_token_id
        eos = [eos] if isinstance(eos, int) else eos
        termination = 'eos' if output_ids and output_ids[-1] in eos else 'max_new_tokens'
        raw = tokenizer.decode(output_ids, skip_special_tokens=True)
        record({'kind': 'inference', 'question_id': q['question_id'], 'category_id': q['category_id'],
                'model': 'qwen3-4b-awq', 'model_id': MODEL_ID, 'condition': 'A', 'instruction': q['instruction_ja'],
                'messages': messages, 'prompt': prompt, 'prompt_ids': encoded['input_ids'][0].tolist(),
                'output_ids': output_ids, 'raw_output': raw, 'termination': termination,
                'elapsed_seconds': elapsed, 'backend': 'pytorch-mps', 'temperature': 0})
        print(f'{index}/50 {q["question_id"]} {len(output_ids)} tokens {elapsed:.2f}s {termination}', flush=True)
    record({'kind': 'complete', 'records': len(prompts), 'completed_at': datetime.now(timezone.utc).isoformat()})


if __name__ == '__main__':
    main()
