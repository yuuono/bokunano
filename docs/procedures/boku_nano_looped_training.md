# Looped Boku-nano：1M反復・小型化モデルの学習と評価

[設計理由と比較条件](../policies/boku_nano_looped_transformer_plan.md)に基づく実装。既存1Mの3物理層を保持した1epoch反復比較と、1物理層・embedding共有を使う3epoch小型化比較を扱う。以下はリポジトリのルートで実行する。

## 準備

```bash
uv sync --python 3.12.12 --group model-training
```

既存の標準BPE、訓練192,900レコードのZIP、validation ZIPを使う。設定に記載したSHA-256・件数・特殊token IDを検証する。標準はCUDA/bfloat16、CUDAのない環境では`auto`はCPUを選ぶ。CPU動作確認には下記の`--device cpu --dtype float32`を指定する。

## 既存1Mの構造を保ち、1epochでloopの効果を比較する

2026-10-16追加。[小型4モデルの結果](../results/boku_nano_looped_all_sizes_20261015.md)とは別実験である。今回の目的は容量削減ではなく、既存1Mの重み数・幅・3物理層を保ったまま反復計算を追加し、1epochの生成・実行正解率が上がるか調べること。

| variant | 固有層×周回 | block適用回数 | parameters | epochs |
| --- | ---: | ---: | ---: | ---: |
| u3（通常版） | 3×1 | 3 | 1,016,704 | 1 |
| u3_r2 | 3×2 | 6 | 1,016,704 | 1 |
| u3_r3 | 3×3 | 9 | 1,016,704 | 1 |
| u3_r6（任意） | 3×6 | 18 | 1,016,704 | 1 |

```text
通常: embedding → B0 → B1 → B2 → norm → head
2周:  embedding → B0 → B1 → B2 → B0 → B1 → B2 → norm → head
                   └─ 3種類のblockを次の周回でも再利用 ─┘
```

幅128・FFN256・4heads・語彙2048・context256・embedding/head非共有を維持する。入力再注入は`none`。B0/B1/B2はそれぞれ独立した重みを持ち、同じ番号のblockだけを周回間で共有する。初期化の残差スケールも物理3層基準を維持するため、同じseedで通常版とloop版の初期重みは完全一致する。学習済み1Mから継続するのではなく、各条件を同じseedのランダム初期値から学習する。

**学習から固定5集合の評価まで一括実行：**

```bash
uv run --group model-training --python 3.12.12 python \
  scripts/model/run_boku_nano_1m_looped_experiment.py \
  --output-root data/models/looped_1m_1epoch_run \
  --run --evaluate
```

既定は`u3 u3_r2 u3_r3`、1epoch、seed20260925。全候補で同じ訓練192,900件、377 optimizer更新、系列token6,939,466、教師token3,746,067を使う。optimizer・学習率scheduleは既存1M・1epoch設定と同じ。3epoch schedule途中のepoch 1とは区別する。1epochでもblock部分の計算は2周で約2倍・3周で約3倍になるため、同じデータ提示量の比較であり、同じ計算量・学習時間の比較ではない。

`--run`を省けば設定生成だけ、`--validate`を付ければ入力hash等の検証まで行う。`--run`だけなら学習までで、生成・実行評価は後から実行できる。`--evaluate`には`--run`が必要で、`--max-steps`との併用は拒否する。

```bash
# 3周だけ学習する（通常版との比較は別途必要）
uv run --group model-training --python 3.12.12 python \
  scripts/model/run_boku_nano_1m_looped_experiment.py \
  --output-root data/models/looped_1m_r3_run --variants u3_r3 --run

# 6周を含める追加実験
uv run --group model-training --python 3.12.12 python \
  scripts/model/run_boku_nano_1m_looped_experiment.py \
  --output-root data/models/looped_1m_r6_run \
  --variants u3 u3_r2 u3_r3 u3_r6 --run --evaluate
```

メモリ不足時は全候補に同じ`--micro-batch-size 64 --gradient-accumulation-steps 8`を指定する。専用入口は1Mの4構成だけを受け付ける。`--epochs`による変更も可能だが、今回の主比較では既定の1を使う。

### 結果の見方・評価の再開

`<output-root>/<variant>_seed20260925/`の`model/training_manifest.json`と`model/training_metrics.jsonl`が学習記録。学習中の標準出力は`console.log`、評価中は`evaluation_console.log`へ保存する。全件評価後は`evaluation/evaluation_manifest.json`にsuite別の正解率・問題数・timeout等が入り、`evaluation/`内の問題別JSONLには生成コードと合否が残る。

一括評価完了時の`<output-root>/comparison.json`には、全体の合格数・正解率、suite別結果、同じ実験内の`u3`との差`delta_vs_u3_percentage_points`を保存する。`u3`を省いた場合の差は`null`。部分評価が混じった場合は集計を拒否する。通常版から全体正解率が上がったかに加え、組合せ・反復・言い換えの個別得点も確認する。性能改善は実験前には保証しない。

学習済みの3条件を後から評価、または中断した評価を再開する場合：

```bash
for variant in u3 u3_r2 u3_r3; do
  uv run --group model-training --python 3.12.12 python \
    scripts/model/evaluate_boku_nano.py \
    --config "data/models/looped_1m_1epoch_run/${variant}_seed20260925/evaluation.yaml" \
    --resume
done
```

この手動実行では各モデルの評価manifestが更新される。一括runnerの`comparison.json`は再生成されない。runner自体は既存出力先への再実行を拒否するので、学習の再開には後述のtrainerの`--resume-from`を使う。

CPUで3層×2周の学習経路だけを2更新確認する例：

```bash
OMP_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false \
uv run --group model-training --python 3.12.12 python \
  scripts/model/run_boku_nano_1m_looped_experiment.py \
  --output-root data/models/looped_1m_cpu_smoke --variants u3_r2 \
  --device cpu --dtype float32 \
  --micro-batch-size 16 --gradient-accumulation-steps 32 --run --max-steps 2
```

## 0.426Mの小型モデルを学習する

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
