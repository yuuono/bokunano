"""Run existing attention diagnostics on the five trained architecture ablations."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
MODELS = ('existing', 'heads_4_dim64', 'layers_2', 'layers_4', 'layers_6')
TOKENIZER = Path('data/tokenizers/bpe_2048/tokenizer.json')
INSTRUCTION = 'xsの各要素を絶対値にして降順に並べるsolve関数を書いてください。'
SCRIPTS = ('scripts/model/analyze_boku_nano_attention.py',
           'scripts/model/analyze_boku_nano_attention_interpretability.py')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, default=Path('docs/results/attention_ablation_20261006'))
    parser.add_argument('--models', nargs='+', choices=MODELS, default=list(MODELS))
    parser.add_argument('--workers', type=int, choices=[1, 2], default=2)
    args = parser.parse_args()
    os.chdir(ROOT)
    if len(set(args.models)) != len(args.models):
        parser.error('Duplicate model selection')
    root = args.output_root
    if any((root/name).exists() for name in args.models):
        parser.error('Selected output already exists; choose a new output root')
    root.mkdir(parents=True, exist_ok=True)

    def run(name):
        model_dir = Path(f'data/models/architecture_ablation_run_20261006/15m_{name}_seed20260925/model')
        training = json.loads((model_dir/'training_manifest.json').read_text())
        assert training['status'] == 'completed'
        assert sha(model_dir/'model.safetensors') == training['model_sha256']
        assert sha(TOKENIZER) == training['tokenizer_sha256']
        output = root/name
        output.mkdir(exist_ok=False)
        commands = []
        for script, metric in zip(SCRIPTS, ('attention.json', 'interpretability.json'), strict=True):
            command = [sys.executable, script, '--model-directory', str(model_dir),
                       '--tokenizer', str(TOKENIZER), '--figure-directory', str(output/'figures'),
                       '--metrics', str(output/metric)]
            if metric == 'attention.json':
                command += ['--instruction', INSTRUCTION]
            commands.append(command)
        manifest = dict(model=name, model_sha256=training['model_sha256'],
                        tokenizer_sha256=training['tokenizer_sha256'],
                        source_sha256={p:sha(p) for p in (*SCRIPTS, 'scripts/model/boku_nano.py',
                            'scripts/model/visualize_boku_nano_kv.py', 'generated_code_verifier.py',
                            'config/japanese_atomic_operations.json', __file__)},
                        commands=commands, device='cpu', dtype='float32', threads_per_process=1,
                        started_at=datetime.now(timezone.utc).isoformat(), status='running')
        manifest_path=output/'manifest.json'
        manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        try:
            for i, command in enumerate(commands):
                print(f'{name}: {Path(command[1]).name}', flush=True)
                with (output/f'analysis_{i+1}.log').open('x') as log:
                    subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT,
                                   env={**os.environ,'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'})
        except BaseException:
            manifest['status']='failed'
            manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
            raise
        manifest.update(status='completed', completed_at=datetime.now(timezone.utc).isoformat())
        manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        print(f'{name}: completed',flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        list(executor.map(run,args.models))


if __name__ == '__main__':
    main()
