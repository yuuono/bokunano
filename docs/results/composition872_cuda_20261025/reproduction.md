# 2026-10-25 CUDA評価の再現

リポジトリのルートで実行する。以下は今回実行した条件。既存の出力先は拒否されるため、再評価時は出力名を変更する。必要な重みは新たに訓練しない。

## 環境

```bash
uv sync --python 3.12.12 --group model-training
uv pip install --python .venv/bin/python onnxruntime==1.30.0 matplotlib==3.11.2
```

ONNX Runtimeは81 prefixの比較診断に使用する。CUDA本評価だけなら不要。図にはNoto Sans CJK JPを使用。

## 通常3モデル、旧ONNX比較、batch1比較

```bash
.venv/bin/python scripts/model/benchmark.py \
  --output-root data/evaluations/composition872_cuda_20261025_baselines \
  --batch-size 32 --score-workers 4 --check-batch-size-one \
  --reference-root data/benchmarks/composition_suite_20261008/runs
```

## 追加の標準BPE・構造比較7モデル

```bash
.venv/bin/python scripts/model/benchmark.py \
  --output-root data/evaluations/composition872_cuda_20261025_standard_extra \
  --model boku-15m-3epoch=data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_3epoch \
  --model boku-15m-10epoch=data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_10epoch \
  --model boku-1m-1epoch=data/models/boku_nano_1m_bpe_2048_minfreq5_maxlen24_1epoch \
  --model ablation-heads4-dim64=data/models/architecture_ablation_run_20261006/15m_heads_4_dim64_seed20260925/model \
  --model ablation-layers2=data/models/architecture_ablation_run_20261006/15m_layers_2_seed20260925/model \
  --model ablation-layers4=data/models/architecture_ablation_run_20261006/15m_layers_4_seed20260925/model \
  --model ablation-layers6=data/models/architecture_ablation_run_20261006/15m_layers_6_seed20260925/model \
  --batch-size 32 --score-workers 4
```

## 短いBPE4モデル

モデルが学習したtokenizerを使用する。既定の標準BPEに置き換えない。指定hash・学習manifest・tokenizer実体の三者一致を検証する。

```bash
.venv/bin/python scripts/model/benchmark.py \
  --output-root data/evaluations/composition872_cuda_20261025_short_bpe \
  --model boku-15m-short-1epoch=data/models/boku_nano_15m_bpe_2048_minfreq2_maxlen8_1epoch \
  --model boku-5m-short-1epoch=data/models/boku_nano_5m_bpe_2048_minfreq2_maxlen8_1epoch \
  --model boku-1m-short-1epoch=data/models/boku_nano_1m_bpe_2048_minfreq2_maxlen8_1epoch \
  --model boku-1m-short-3epoch=data/models/boku_nano_1m_bpe_2048_minfreq2_maxlen8_3epoch \
  --tokenizer-sha256 f09f3d7eccbca2ab1224c662064b71e572d64147147b8b559ebdb428eb035dbf \
  --batch-size 32 --score-workers 4
```

## 小型loop4モデル

最初のコマンドは元重み・元ディレクトリを変更せず、報告の固定hash・構造・strict loadを検証して、評価用設定と復元記録だけを新しい場所へ作る。元training manifestではないことを記録する。

```bash
.venv/bin/python scripts/model/prepare_looped_evaluation_recovery.py \
  --output-root data/evaluations/composition872_cuda_20261025_recovered_inputs

.venv/bin/python scripts/model/benchmark.py \
  --output-root data/evaluations/composition872_cuda_20261025_small_loops \
  --recovered-model loop-lt1-3epoch=data/evaluations/composition872_cuda_20261025_recovered_inputs/lt1/recovery_manifest.json \
  --recovered-model loop-f128-3epoch=data/evaluations/composition872_cuda_20261025_recovered_inputs/f128/recovery_manifest.json \
  --recovered-model loop-w96-3epoch=data/evaluations/composition872_cuda_20261025_recovered_inputs/w96/recovery_manifest.json \
  --recovered-model loop-w64-3epoch=data/evaluations/composition872_cuda_20261025_recovered_inputs/w64/recovery_manifest.json \
  --batch-size 32 --score-workers 4
```

## 数値診断・作図

数値診断は通常3の保存結果を参照する。GPU速度計測へ混ぜないよう、本評価の完了後に実行する。

```bash
.venv/bin/python scripts/model/diagnose_composition872_backends.py \
  --output data/evaluations/composition872_cuda_20261025_backend_logits.json

.venv/bin/python scripts/model/report_composition872_cuda.py \
  --run-roots data/evaluations/composition872_cuda_20261025_baselines \
    data/evaluations/composition872_cuda_20261025_standard_extra \
    data/evaluations/composition872_cuda_20261025_short_bpe \
    data/evaluations/composition872_cuda_20261025_small_loops \
  --expected-model-count 18

.venv/bin/python -m unittest \
  tests.test_evaluate_boku_composition_torch \
  tests.test_evaluate_boku_composition_recovery
```

保存結果を使って図だけ再生成する場合は、[結果ZIP](../../../data/archives/composition872_cuda_20261025_results.zip)をリポジトリのルートに展開し、作図コマンドを実行する。既存評価がある場合は別のcheckout等へ展開し、上書きしない。
