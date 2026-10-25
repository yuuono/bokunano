# 発表資料の872問をNVIDIA CUDA・PyTorchで評価する

2026-10-25作成。発表資料の日本語指示872問を変更せず、通常モデルとloopモデルを同じ問題・同じ採点基準で比較する。モデルにはPythonの`solve(xs, k)`を生成させ、各問について固定179入力のすべてを正しく処理した場合に合格とする。

新しい実行入口は[`scripts/model/benchmark.py`](../../scripts/model/benchmark.py)、本体は[`evaluate_boku_composition_torch.py`](../../scripts/model/evaluate_boku_composition_torch.py)。NVIDIA CUDA専用で、ONNX Runtimeは不要。モデル推論は同じprompt長ごとのバッチで行う。生成されたPythonコードの採点は従来どおりCPUの隔離プロセスで行う。

**この変更を作成したPCではモデル評価を実行していない。CUDAでの速度・旧出力との一致・middle4の872問成績は、以下を実行して確認する。**

## 1. 固定する評価条件

| 項目 | 条件 |
|---|---|
| 質問 | `data/benchmarks/composition_suite_20261008/questions.jsonl` の872問、9カテゴリ |
| 質問SHA-256 | `aa119fa2a9e8507136ad14a54b9d3d2e9043fd81af9e48251ef7f5c49c20f97f` |
| 検査入力 | 同ディレクトリの`test_cases.json`、179個 |
| 入力SHA-256 | `0090a38d255848a813876ce3b64a8029603aa14e4181b453a89801b41ac67fc2` |
| tokenizer | 元のBPE 2,048語彙。SHA-256 `6840a392e8fcae1083be06842774fa912a1797217c7033944ba2d87f1c227293` |
| prompt | 旧テンプレートを固定（下記） |
| 生成 | greedy、履歴なし、修復なし、EOSまたはpromptと生成の合計256 tokenで終了 |
| 精度 | float32、autocastなし、TF32無効、SDPA math |
| バッチ | 既定上限32。同じprompt長をまとめ、paddingせず生成 |
| 採点 | 旧`score_composition_suite.score_one`を直接呼ぶ。静的検査・179入力・CPU 2秒/wall 5秒の制限を維持 |
| 保存 | 毎回新しい出力先。旧キャッシュの補完・上書き・再開はしない |

promptテンプレート（`\n`は改行）：

```text
<|bos|><|task|>\n{instruction_ja}\n<|code|>\n
```

質問だけでなくprotocolと採点コードのhashも検査する。モデル重み・モデル設定・学習manifest・tokenizerの整合も確認し、baselineの既定名では発表資料と同じ重みとモデル設定のhashだけを許可する。同じ重みのloop回数だけを変える実験も含め、異なる条件を評価する場合は別名を付ける。

旧`run_composition_suite.py`／`evaluate_boku_composition.py`はONNX Runtimeによる実装だった。**問題・prompt・生成条件・採点基準は旧版へ統一するが、推論実装そのものは新しいPyTorch CUDA版である。** float32でもbackendやバッチによる数値差は起こり得るため、保存済み出力との一致を自動照合できるようにした。

## 2. NVIDIA環境を準備する

リポジトリのルートで実行する。NVIDIAドライバとCUDA対応PyTorchが利用できるLinux環境を想定する。

```bash
git pull --ff-only
uv sync --python 3.12.12 --group model-training
nvidia-smi
```

CPU/MPSへの自動切替は行わない。GPUを選択する場合は実行前に`CUDA_VISIBLE_DEVICES`を設定する。プロセスから見える最初のGPUを使用する。ONNX関連の依存groupを追加する必要はない。

## 3. 通常3モデルを評価する

通常15M・1epoch、5M・1epoch、1M・3epochの学習済みartifactと、発表資料の保存済みraw/scored/config/provenance/summaryをGitに含めている。以下は全3モデルの全872問を新しく生成・採点し、旧ONNX出力との差も保存する。

```bash
uv run --no-sync --python 3.12.12 python scripts/model/benchmark.py \
  --output-root data/evaluations/composition872_cuda_baselines_01 \
  --batch-size 32 \
  --reference-root data/benchmarks/composition_suite_20261008/runs
```

実行前にモデルの復元・推論・採点をせず、ファイルhashとpromptだけを確認する場合は、同じコマンドに`--validate-only`を加える。この検査では出力ディレクトリも作成しない。

GPUメモリ不足なら`--batch-size 16`または`8`に下げ、新しい`--output-root`で実行する。中断した結果は残り、上書きされない。既存の出力先を指定した場合はエラーで停止する。

## 4. middle4の2候補を含む5モデルを比較する

middle4の重みはGit配布に含まれない。NVIDIA環境に以前の3epoch学習成果物があることを確認する。

| モデル名 | 必要なディレクトリ |
|---|---|
| `middle4-1m-3epoch` | `data/models/middle4_1m_3epoch_20261018/u3_middle4_seed20260925/model` |
| `middle4-scaled025-1m-3epoch` | `data/models/middle4_1m_3epoch_20261018/u3_middle4_scaled025_seed20260925/model` |

各ディレクトリに`model.safetensors`、`model_config.json`、`training_manifest.json`が必要。重みをこの評価スクリプトが新しく訓練することはない。全既定モデルの場所は`--list-models`で確認できる。

```bash
uv run --no-sync --python 3.12.12 python scripts/model/benchmark.py \
  --models boku-15m-1epoch boku-5m-1epoch boku-1m-3epoch \
    middle4-1m-3epoch middle4-scaled025-1m-3epoch \
  --output-root data/evaluations/composition872_cuda_five_models_01 \
  --batch-size 32 \
  --reference-root data/benchmarks/composition_suite_20261008/runs
```

通常3モデルには旧出力との照合結果が付き、旧出力のないmiddle4は新規評価のみになる。再構成版の数値は取り込まない。

配置が異なる場合や別のloop候補を評価する場合は`--model 名前=ディレクトリ`を指定する。これだけを指定すると、そのモデルだけを評価する。

```bash
uv run --no-sync --python 3.12.12 python scripts/model/benchmark.py \
  --model my-loop=/path/to/training-output/model \
  --output-root data/evaluations/composition872_cuda_my_loop_01 \
  --batch-size 32
```

同じtokenizer・context 256・学習manifest形式を使うBokuNano通常/loopモデルに対応する。既定名の配置だけを変更する場合は、例えば`--model middle4-1m-3epoch=/path/to/model`を使う。既定名の構造条件も検査される。

## 5. バッチ化の速度と結果への影響を調べる

PyTorchのバッチ化はGPUをまとめて使うための実装だが、実測速度はGPUと系列長に依存する。まず15Mだけでバッチ32と1を照合するには次を実行する。

```bash
uv run --no-sync --python 3.12.12 python scripts/model/benchmark.py \
  --models boku-15m-1epoch \
  --output-root data/evaluations/composition872_cuda_15m_batch_check_01 \
  --batch-size 32 --check-batch-size-one \
  --reference-root data/benchmarks/composition_suite_20261008/runs
```

これは同じ全872問をbatch 32とbatch 1の両方で生成・採点する追加検証なので、通常より時間がかかる。`batch_size_comparison.json`に生成token等の差、合否変更件数、両者の推論時間を保存する。`reference_comparison.json`は旧ONNX出力との差を表す。両方を分けて読むことで、バッチ化の影響と旧backendからの変更を区別できる。

生成コードの採点は`--score-workers`（既定4）で並行実行する。これはモデル推論のbatch数とは独立する。timeoutが増える場合はCPU負荷も確認する。

## 6. 保存先と読み方

出力ルートには`config.json`、`environment.json`、`protocol.json`、全モデル比較の`comparison.json`を保存する。`comparison.json`の`status`が`completed`になったものを完了結果として扱う。

各モデルのサブディレクトリには次を保存する。

- `raw_inference.jsonl`：問題ID、実prompt、入出力token列、生成コード、終了理由。
- `scored.jsonl`：旧採点器による合否と失敗理由。
- `summary.json`：9カテゴリそれぞれの合格数と問題数。
- `run_metrics.json`：全体成績、推論秒数、問/秒、GPUメモリ使用量、照合件数。
- `config.json`、`source_hashes.json`、`scoring_provenance.json`：使用した重み・コード・データとhash。
- `reference_comparison.json`：旧出力を指定したモデルのみ。生成差と合否変更の問題IDを記録。
- `batch_size_one_raw.jsonl`、`batch_size_one_scored.jsonl`、`batch_size_comparison.json`：batch=1照合を指定した場合のみ。

旧出力とのtoken差があっても、直ちに点数差があるとは限らない。`different_generation_count`と`pass_change_count`を区別して確認する。通常1Mとloopを比べる際は、同じCUDA評価条件の新しい結果同士を比較する。

既定の保存先例`data/evaluations/`はGitでignoreされる。結果を共有・保存する際は、この出力ルートをまとめて保持する。

## 7. 撤回した再構成版と歴史資料

[比較監査報告](../results/benchmark_872_comparison_audit_20261024/README.md)に、初めて読む人向けに問題集合が変わった経緯、4操作の難度差、29→63を改善と解釈できない理由を記載した。再構成版の質問・報告・図・集計は現行Gitツリーから削除済み。過去commitは書き換えていない。正式5集合84,550件など、別の評価結果は保持している。

発表資料に記載された旧`benchmark.py --presentation ...`は当時の作図コマンドであり、現在のCLIとは異なる。このPCにあった旧作図スクリプトは`benchmark_presentation_legacy.py`へ同じbytesでローカル保全した。これは未追跡の作業用ファイルで、今回の配布物ではない。新規cloneでは本書のCUDA評価コマンドを使用する。
