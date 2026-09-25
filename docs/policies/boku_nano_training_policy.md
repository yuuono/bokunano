# Boku-nano本学習方針

## 1. 目的

固定済みBPE 2,048語彙と最終訓練データ192,900件だけを用い、既存モデルの重みを一切読み込まず、約1,600万parameterのDecoder-only Transformerをランダム初期値から3 epoch学習する。

モデルは日本語指示を条件として、固定シグネチャを持つPython `solve`関数を生成する。教師モデルQwen3の重み、logit、hidden stateは本学習へ使用しない。

## 2. 固定モデル仕様

| 項目 | 値 |
|---|---:|
| model type | Decoder-only Transformer |
| parameter数 | 15,735,168（約1,600万） |
| 語彙数 | 2,048 |
| `d_model` | 384 |
| block数 | 8 |
| attention head数 | 6 |
| head次元 | 64 |
| SwiGLU `d_ff` | 1,024 |
| 文脈長 | 256 |
| 位置表現 | RoPE |
| 正規化 | pre-norm RMSNorm |
| embeddingと出力層 | 非共有 |
| dropout | 0.0 |

parameter内訳は次のとおりである。

| 構成 | parameter数 |
|---|---:|
| token embedding | 786,432 |
| Transformer 8 block | 14,161,920 |
| final RMSNorm | 384 |
| LM output head | 786,432 |
| 合計 | 15,735,168 |

入力embeddingと出力headは共有しない。共有すると約1,495万parameterとなるため、今回の約1,600万parameter仕様では独立parameterとする。linear層にbiasは持たせない。attentionはPyTorchのscaled dot-product attentionを使うが、model parameterはすべて本実装でランダム初期化する。

## 3. 固定トークナイザ

使用するのは次の完成済みBPEだけである。

| 項目 | 値 |
|---|---|
| tokenizer | `data/tokenizers/bpe_2048/tokenizer.json` |
| SHA-256 | `6840a392e8fcae1083be06842774fa912a1797217c7033944ba2d87f1c227293` |
| 語彙数 | 2,048 |
| 文脈長検査 | 256 |

本学習時にトークナイザを再学習しない。実ファイルのSHA-256、実語彙数、特殊トークンIDを開始前に照合し、一つでも異なれば停止する。

| ID | token |
|---:|---|
| 0 | `<|pad|>` |
| 1 | `<|bos|>` |
| 2 | `<|eos|>` |
| 3 | `<|unk|>` |
| 4 | `<|task|>` |
| 5 | `<|code|>` |
| 6 | `<|explanation|>` |

## 4. 訓練データ

| 項目 | 値 |
|---|---|
| ZIP | `data/archives/final_train_dataset_records_2026-09-25.zip` |
| member | `final_dataset_records.jsonl` |
| SHA-256 | `799e6dd8be7e80e48df69fed4f70f5922f7a215a8669cf0f523f3de59ae91807` |
| レコード数 | 192,900 |

全レコードについて次を開始前に確認する。

```text
split=train
test_suite=null
dictionary=train
input_set=build
```

完成系列はトークナイザ作成時と同じ次の形式に固定する。

```text
<|bos|><|task|>
{instruction_ja}
<|code|>
{reference_code}<|eos|>
```

切り捨ては行わない。1件でも256 tokenを超えた場合は学習を停止する。現在のBPE検証では最大94 token、1 epoch当たり6,939,466非padding tokenである。3 epochでは同じ192,900件を3回だけ使用するため、モデルが読む非padding tokenは20,818,398 tokenとなる。このうちlossへ使うcode・EOS教師tokenは1 epoch当たり3,746,067、3 epoch合計11,238,201 tokenである。

ここで「3 epoch」は30億tokenを意味しない。今回の固定コーパスを3周する、約2,082万tokenの本学習である。

## 5. 損失範囲

日本語指示からPythonコードを生成する目的へ合わせ、損失は`<|code|>`直後から`<|eos|>`までに限定する。

- 日本語指示、`<|bos|>`、`<|task|>`、`<|code|>`はcontextとしてモデルへ入力する。
- prompt部分のlabelは`-100`としてcross entropyから除外する。
- Pythonコード、改行、最後の`<|eos|>`を教師tokenとする。
- paddingも`-100`として損失から除外する。

これにより、日本語文そのものを復唱する学習ではなく、与えられた指示に対応するコードの次token予測を直接最適化する。

## 6. batchとpadding

| 項目 | 値 |
|---|---:|
| micro batch size | 512 |
| gradient accumulation | 1 |
| effective batch size | 512レコード |
| 1 epochのoptimizer step | 377 |
| 3 epochのoptimizer step | 1,131 |

batchごとの最大長まで右paddingする。系列packingは行わない。平均系列長が約36 tokenと短いため、まずは文書境界をまたぐattentionや位置IDの複雑さを持ち込まず、各レコードを独立系列として扱う。

右paddingされた位置のlossは無視する。causal attentionでは実token位置から未来のpaddingを参照できないため、実tokenの表現へpaddingは混入しない。

## 7. optimizerと学習率

| 項目 | 値 |
|---|---:|
| optimizer | AdamW |
| 最大learning rate | `3.0e-4` |
| 最小learning rate | `3.0e-5` |
| warmup | 全1,131 stepの5%（57 step） |
| schedule | linear warmup + cosine decay |
| betas | `(0.9, 0.95)` |
| epsilon | `1.0e-8` |
| weight decay | 0.1 |
| gradient clipping | global norm 1.0 |

weight decayは2次元以上の行列parameterへ適用し、RMSNormのscaleなど1次元parameterには適用しない。CUDAではfused AdamWを使う。

## 8. 精度と実行環境

RTX 5090上では`bfloat16` autocastを使用する。parameterとoptimizer stateの管理はPyTorch標準に従い、forwardの語彙logitsとcross entropy計算はfloat32へ上げる。

`torch.compile`は初回正式学習では無効にする。まずeager実行を再現基準とし、compile有効化は速度比較を別実験として行う。乱数seedは`20260925`へ固定するが、CUDA kernel差によるbit単位完全一致までは保証しない。

## 9. validationとhidden評価の分離

各epoch終了後に`validation_dataset_records.jsonl` 24,040件のcode-only lossとperplexityを測定する。validationによる早期終了やbest checkpoint選択は行わず、正式成果物は固定3 epoch終了時のモデルとする。

次のhidden評価集合は本学習中にencode、loss計算、model選択へ使用しない。

- normal
- compositional
- paraphrase
- repetition
- boundary

評価ZIPには6集合が同居するが、学習コードが開くmemberはvalidationだけである。hidden 5集合は3 epochモデルを固定した後の最終評価で初めて使用する。

## 10. 保存物

標準出力先は`data/models/boku_nano_bpe_2048/`とし、次を保存する。

| ファイル | 内容 |
|---|---|
| `model.safetensors` | 最終または明示的smoke終了時のモデル重み |
| `model_config.json` | 推論時に必要なモデル構造 |
| `training_config.yaml` | 実際に使用した解決済み設定 |
| `training_manifest.json` | 入力・tokenizerハッシュ、件数、parameter数、実行結果 |
| `training_metrics.jsonl` | train loss、学習率、gradient norm、validation loss |
| `checkpoints/epoch_XX.pt` | epoch境界から再開するモデル・optimizer状態 |

重みとoptimizer checkpointは大容量かつ実行環境依存の成果物なのでGitへ追加しない。モデルを公開する場合は別の成果物保管先を使い、`model.safetensors`のSHA-256と対応するGit commitを結果MDへ記録する。

既存出力は暗黙に上書きしない。新規学習で置き換える場合だけ`--overwrite`を指定する。再開はepoch境界checkpointを指定し、異なるモデル設定への読込みを拒否する。

## 11. 実行手順

依存環境を作る。

```bash
uv sync --python 3.12.12 --group model-training
```

GPUを使用せず、モデル構造、15,735,168 parameter、tokenizer SHA-256、訓練・validation ZIPのSHA-256を確認する。

```bash
uv run --group model-training --python 3.12.12 python \
  scripts/model/train_boku_nano.py \
  --config config/boku_nano_bpe_2048.yaml \
  --validate-config
```

本学習を開始する。

```bash
uv run --group model-training --python 3.12.12 python \
  scripts/model/train_boku_nano.py \
  --config config/boku_nano_bpe_2048.yaml
```

既存出力を確認したうえで新規学習へ置き換える場合だけ次を使う。

```bash
uv run --group model-training --python 3.12.12 python \
  scripts/model/train_boku_nano.py \
  --config config/boku_nano_bpe_2048.yaml \
  --overwrite
```

epoch 1終了checkpointからepoch 2を再開する例は次のとおりである。

```bash
uv run --group model-training --python 3.12.12 python \
  scripts/model/train_boku_nano.py \
  --config config/boku_nano_bpe_2048.yaml \
  --resume-from data/models/boku_nano_bpe_2048/checkpoints/epoch_01.pt
```

`--max-steps`は配線確認用であり、本学習結果には使用しない。指定時のmanifestは`stopped_at_max_steps`となり、3 epoch完了モデルと区別する。

epoch数を変える追加実験では元YAMLを書き換えず、`--epochs`と別の`--output-dir`を指定する。例えば10 epoch実験は`--epochs 10 --output-dir data/models/boku_nano_bpe_2048_10epoch`とする。学習率scheduleも全10 epochを前提に最初から作るため、3 epoch checkpointへ継ぎ足さずランダム初期値から学習する。

## 12. 学習完了後の必須確認

1. `training_manifest.json`が`status=completed`である。
2. `global_step=1131`である。
3. 入力ZIPとtokenizerのSHA-256が設定値と一致する。
4. `parameter_count=15735168`である。
5. 3 epoch分の非padding token数が20,818,398である。
6. 3 epoch分のcode・EOS教師token数が11,238,201である。
7. train lossとvalidation lossにNaNまたはinfがない。
8. epochごとのloss推移とgradient normを結果MDへ記録する。
9. 完成`model.safetensors`のSHA-256を固定する。
10. 固定後の同一モデルだけでhidden 5集合を評価する。
