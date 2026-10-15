# 1M未満のLooped Boku-nano：学習と評価の実行手順

[設計理由と比較条件](../policies/boku_nano_looped_transformer_plan.md)に基づく実装。1M・3層・3epochを基準に、1物理層×3周とembedding共有を比較する。以下はリポジトリのルートで実行する。モデルを一から学習するためのスクリプトであり、学習済みの高精度な小型重みを配布するものではない。

## 準備

```bash
uv sync --python 3.12.12 --group model-training
```

既存の標準BPE、訓練192,900レコードのZIP、validation ZIPを使う。設定に記載したSHA-256・件数・特殊token IDを検証する。標準はCUDA/bfloat16、CUDAのない環境では`auto`はCPUを選ぶ。CPU動作確認には下記の`--device cpu --dtype float32`を指定する。

## まず本命0.426Mを学習する

```bash
uv run --group model-training --python 3.12.12 python \
  scripts/model/run_boku_nano_looped_experiment.py \
  --output-root data/models/looped_lt1_run \
  --variants lt1 --run
```

`lt1`は幅128・FFN256・1層×3周・embedding共有、426,368 parameters。既定は3epoch、seed20260925、実効batch512。実行前に設定と入力を検証し、学習中のログを`data/models/looped_lt1_run/lt1_seed20260925/console.log`へ書く。同じ出力先の再使用は拒否する。

既存trainerへ直接渡せる固定設定も用意した。

```bash
uv run --group model-training --python 3.12.12 python \
  scripts/model/train_boku_nano.py \
  --config config/boku_nano_looped_lt1_3epoch.yaml --validate-config

uv run --group model-training --python 3.12.12 python \
  scripts/model/train_boku_nano.py \
  --config config/boku_nano_looped_lt1_3epoch.yaml
```

直接実行した場合のモデル出力先は`data/models/boku_nano_looped_lt1_3epoch`。上の比較runnerとは別の出力先なので混同しない。

## 比較設定だけを生成する

`--run`を省くと設定・manifestのみを作り、学習はしない。`--validate`を加えるとデータのhash等も検証する。

```bash
uv run --group model-training --python 3.12.12 python \
  scripts/model/run_boku_nano_looped_experiment.py \
  --output-root data/models/looped_plan --validate
```

既定の9条件は`u3 u2 u1 l1 t3 t1 lt1 l1_add lt1_add`。実際に比較学習する場合は、新しい出力先で`--run`を指定する。

```bash
uv run --group model-training --python 3.12.12 python \
  scripts/model/run_boku_nano_looped_experiment.py \
  --output-root data/models/looped_baseline_run --run
```

| variant | 幅 / FFN | 固有層×周回 | embedding共有 | パラメータ |
| --- | --- | --- | --- | ---: |
| u3 | 128 / 256 | 3×1 | なし | 1,016,704 |
| u2 | 128 / 256 | 2×1 | なし | 852,608 |
| u1 / l1 | 128 / 256 | 1×1 / 1×3 | なし | 688,512 |
| t3 | 128 / 256 | 3×1 | あり | 754,560 |
| t1 / lt1 | 128 / 256 | 1×1 / 1×3 | あり | 426,368 |
| t2 / lt2 | 128 / 256 | 2×1 / 2×2 | あり | 590,464 |
| f128_plain / f128 | 128 / 128 | 1×1 / 1×3 | あり | 377,216 |
| w96_plain / w96 | 96 / 192 | 1×1 / 1×3 | あり | 289,056 |
| w64_plain / w64 | 64 / 128 | 1×1 / 1×3 | あり | 172,224 |
| w64_r2 / w64_r6 | 64 / 128 | 1×2 / 1×6 | あり | 172,224 |

`l1_add`と`lt1_add`はそれぞれ`l1`/`lt1`の2周目以降に入力embeddingを再注入する。重み数は変わらない。層・幅・FFN・共有の効果を分けるため、loop版だけでなく通常版の対照も実行する。

## 0.289M・0.172M等を比較する

```bash
uv run --group model-training --python 3.12.12 python \
  scripts/model/run_boku_nano_looped_experiment.py \
  --output-root data/models/looped_small_run \
  --variants u3 t1 lt1 f128_plain f128 w96_plain w96 w64_plain w64 --run
```

seedを変える場合は`--seed 20260926`などを指定し、出力先も変える。3epochが正式な主比較。`--epochs`は別の学習期間の実験用であり、候補だけ期間を増やした結果を同条件と扱わない。

メモリ不足時は、例えば`--micro-batch-size 64 --gradient-accumulation-steps 8`で実効batch512を維持する。全対照を同じ分割方法で再学習する。平均CEの集計が変わるため、512件一括と完全に同じ更新にはならない。

## 2更新だけの動作確認

```bash
OMP_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false \
uv run --group model-training --python 3.12.12 python \
  scripts/model/run_boku_nano_looped_experiment.py \
  --output-root data/models/looped_cpu_smoke \
  --variants lt1 --device cpu --dtype float32 \
  --micro-batch-size 16 --gradient-accumulation-steps 32 \
  --run --max-steps 2
```

全データの検証・tokenizeは行うが、optimizer更新を2回で止める。manifestの`smoke_test`とtrainerの完了状態で正式学習と区別する。この重みの精度を3epoch結果と比較しない。正式学習には新しい出力先を使い、`--max-steps`を外す。

## 保存結果と再開

```text
<output-root>/
  manifest.json
  <variant>_seed20260925/
    config.yaml
    evaluation.yaml
    console.log
    model/
      model_config.json
      model.safetensors
      training_config.yaml
      training_manifest.json
      training_metrics.jsonl
      checkpoints/epoch_01.pt ...
```

共有語彙行列は保存ファイルに1回だけ格納し、読込時にheadの別名を復元する。旧モデルの設定は`n_loops=1, loop_input_mode=none`として扱う。旧checkpointの再開も設定を正規化して比較する。R、幅、embedding共有の変更は通常のresumeでは拒否する。

epoch境界のcheckpointから、同じ設定・学習期間で再開する例：

```bash
uv run --group model-training --python 3.12.12 python \
  scripts/model/train_boku_nano.py \
  --config data/models/looped_lt1_run/lt1_seed20260925/config.yaml \
  --resume-from data/models/looped_lt1_run/lt1_seed20260925/model/checkpoints/epoch_01.pt
```

途中のmicro batchからの再開はしない。loop runner自体は既存ディレクトリへの自動再開を行わない。

## 生成・実行評価

runnerが出力した`evaluation.yaml`にはモデルの実パラメータ数・出力先が反映される。まず言い換え30件を確認し、その後別の出力先で全5集合を評価する。

```bash
uv run --group model-training --python 3.12.12 python \
  scripts/model/evaluate_boku_nano.py \
  --config data/models/looped_lt1_run/lt1_seed20260925/evaluation.yaml \
  --suite paraphrase \
  --output-directory data/evaluations/looped_lt1_paraphrase

uv run --group model-training --python 3.12.12 python \
  scripts/model/evaluate_boku_nano.py \
  --config data/models/looped_lt1_run/lt1_seed20260925/evaluation.yaml
```

CPU評価では`evaluation.yaml`の`generation.device`を`cpu`、`generation.dtype`を`float32`に設定する（評価CLIにはdevice/dtypeの上書き引数はない）。runnerを`--device cpu --dtype float32`で実行した場合は生成設定へ反映済み。固定設定で直接学習した場合は`config/boku_nano_looped_lt1_3epoch_evaluation.yaml`を使う。U3を同じ条件で再学習・評価して比較し、学習lossだけで小型モデルを採用しない。

## ONNX書き出し

```bash
uv run --group onnx-export --python 3.12.12 python \
  scripts/model/export_boku_nano_onnx.py \
  --model lt1=data/models/looped_lt1_run/lt1_seed20260925/model --in-place
```

モデルフォルダへ`model.onnx`と`onnx_manifest.json`を出力する。Rは書き出し時に固定し、PythonとONNXのlogits・greedy token列を検査する。tied embeddingの場合はconstant foldingを無効にして転置headの重複格納を抑える。未学習・動作確認重みでも数値比較はできるが、コード生成能力の保証にはならない。

現行Webの既定モデルは変更しない。学習後の品質とブラウザの速度・メモリを確認してから追加する。旧attention/KV解析は周回別の捕捉に未対応のため、loopモデルを明示的に拒否する。因子分解embedding、可変反復、KV cacheも今回の実装対象外。

## 自動テスト

```bash
uv run --group model-training --group onnx-export --python 3.12.12 python \
  -m unittest tests.test_looped_boku_nano tests.test_train_boku_nano tests.test_evaluate_boku_nano
```

R=1互換、因果性、展開モデルの勾配和、保存とoptimizer再開、設定生成、共有ONNXの数値一致を検証する。学習結果の能力評価とは別である。
