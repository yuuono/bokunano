"""Evaluate official non-quantized Qwen3-1.7B weights as FP16 on Apple MPS."""
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
MODEL_ID = 'Qwen/Qwen3-1.7B'
REVISION = '70d244cc86ccca08cf5af4e1e306ecf908b1ad5e'


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda: f.read(8 * 1024 * 1024), b''):
            digest.update(data)
    return digest.hexdigest()


def load_model(model_path):
    import torch
    from accelerate import init_empty_weights
    from safetensors.torch import load_file
    from transformers import Qwen3Config, Qwen3ForCausalLM
    from collections import Counter
    config = json.loads((model_path / 'config.json').read_text())
    assert 'quantization_config' not in config
    assert config['model_type'] == 'qwen3' and config['tie_word_embeddings']
    index = json.loads((model_path / 'model.safetensors.index.json').read_text())
    state = {}
    for filename in sorted(set(index['weight_map'].values())):
        shard = load_file(model_path / filename, device='cpu')
        assert not set(state).intersection(shard)
        state.update(shard)
    assert set(state) == set(index['weight_map'])
    source_dtypes = dict(Counter(str(value.dtype) for value in state.values()))
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
    return model, {'load_state_dict': 'strict', 'runtime_dtype': 'float16',
                   'checkpoint_tensor_dtypes': source_dtypes, 'quantization': None,
                   'parameter_count': model.num_parameters(),
                   'weight_shards': sorted(set(index['weight_map'].values()))}


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
    config = {'run_id': args.run.name, 'model_id': MODEL_ID, 'revision': REVISION, 'model': 'qwen3-1.7b',
              'conditions': ['A'], 'question_count': 50, 'questions_sha256': sha(question_path),
              'backend': 'pytorch-mps', 'weight_loading': 'Official non-quantized checkpoint cast to FP16; no AWQ or 4-bit quantization',
              'temperature': 0, 'do_sample': False, 'repetition_penalty': 1, 'max_new_tokens': 512,
              'enable_thinking': False, 'history': False, 'attention_implementation': 'eager',
              'prompt_matches_original_qwen': True, 'versions': {p: importlib.metadata.version(p) for p in ['torch', 'transformers', 'accelerate', 'safetensors', 'tokenizers']}}
    (args.run / 'config.json').write_text(json.dumps(config, ensure_ascii=False, indent=2)+'\n')
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in [Path(__file__).resolve(), question_path, ROOT/'scripts/model/score_browser_100_benchmark.py', ROOT/'reference_interpreter.py', ROOT/'generated_code_verifier.py']}
    hashes.update({f'model/{p.name}': sha(p) for p in sorted(args.model_path.iterdir()) if p.is_file()})
    (args.run / 'source_hashes.json').write_text(json.dumps(hashes, indent=2)+'\n')
    provenance = {'model_id': MODEL_ID, 'revision': REVISION, 'weight_hashes': {}}
    for filename in sorted(args.model_path.glob('*.safetensors')):
        metadata = (args.model_path/'.cache/huggingface/download'/f'{filename.name}.metadata').read_text().splitlines()
        assert metadata[0] == REVISION and metadata[1] == hashes[f'model/{filename.name}']
        provenance['weight_hashes'][filename.name] = metadata[1]
    provenance['verified_against_download_metadata'] = True
    (args.run/'model_provenance.json').write_text(json.dumps(provenance, indent=2)+'\n')
    model, validation = load_model(args.model_path)
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
                'model': 'qwen3-1.7b', 'model_id': MODEL_ID, 'condition': 'A', 'instruction': q['instruction_ja'],
                'messages': messages, 'prompt': prompt, 'prompt_ids': encoded['input_ids'][0].tolist(),
                'output_ids': output_ids, 'raw_output': raw, 'termination': termination,
                'elapsed_seconds': elapsed, 'backend': 'pytorch-mps', 'temperature': 0})
        print(f'{index}/50 {q["question_id"]} {len(output_ids)} tokens {elapsed:.2f}s {termination}', flush=True)
    record({'kind': 'complete', 'records': len(prompts), 'completed_at': datetime.now(timezone.utc).isoformat()})


if __name__ == '__main__':
    main()
