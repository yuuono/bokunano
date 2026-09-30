# BPEトークナイザーの二つの実装例

## 目的

Boku1-nanoでは、同じ192,900件の訓練データから、設定の異なる二つのByteLevel BPEトークナイザーを作成した。本書では、長いpieceを許可する既存版と、短いpieceへ制限した比較版について、語彙、系列長、学習token量、GPUメモリの違いを整理する。

どちらも既存モデルのトークナイザーや事前学習済み語彙を流用していない。日本語指示と正解Pythonコードだけからゼロから学習し、特殊token込みの語彙数を2,048に固定した。

## 共通条件

| 項目 | 条件 |
| --- | --- |
| 学習データ | train 192,900件 |
| コーパス | `instruction_ja`と`reference_code` |
| 方式 | ByteLevel BPE |
| 語彙数 | 特殊token込み2,048 |
| normalizer | identity |
| byte fallback | 有効 |
| BPE dropout | 0 |
| 最大系列長 | 256 token |
| 特殊token | `<|pad|>`、`<|bos|>`、`<|eos|>`、`<|unk|>`、`<|task|>`、`<|code|>`、`<|explanation|>` |

評価データは語彙学習へ使用していない。両方とも訓練データ全件に対し、unknown token 0件、round-trip不一致0件、256 token超過0件を確認した。

## 実装例A：長いpieceを許可する既存BPE

既存の3エポックモデルと10エポックモデルで使用しているトークナイザーである。

```yaml
model:
  type: bpe
  vocab_size: 2048
  min_frequency: 5
  max_token_length: 24
  byte_fallback: true
  dropout: 0.0
```

| 項目 | 値 |
| --- | ---: |
| 実語彙数 | 2,048 |
| 特殊tokenを除く実測最大piece内部長 | 23 |
| 日本語指示の平均token数 | 11.55 |
| Pythonコードの平均token数 | 17.42 |
| 完成系列の平均token数 | 35.97 |
| 完成系列のp99 | 46 |
| 完成系列の最大 | 94 |
| 1エポックの系列token数 | 6,939,466 |
| tokenizer SHA-256 | `6840a392e8fcae1083be06842774fa912a1797217c7033944ba2d87f1c227293` |

頻出する日本語表現やPythonの定型構文を比較的長いpieceへまとめられるため、系列を短くできる。一方、長い定型pieceへ依存し、未学習の言い換えを細かく分解しにくくなる可能性がある。

成果物：

- [`config/tokenizer_bpe_2048.yaml`](../../config/tokenizer_bpe_2048.yaml)
- [`data/tokenizers/bpe_2048/tokenizer.json`](../../data/tokenizers/bpe_2048/tokenizer.json)
- [`data/tokenizers/bpe_2048/training_stats.json`](../../data/tokenizers/bpe_2048/training_stats.json)

## 実装例B：短いpieceへ制限したBPE

長い日本語テンプレートやPython文全体に近いpieceを抑える比較実験として作成した。

```yaml
model:
  type: bpe
  vocab_size: 2048
  min_frequency: 2
  max_token_length: 8
  byte_fallback: true
  dropout: 0.0
```

| 項目 | 値 |
| --- | ---: |
| 実語彙数 | 2,048 |
| 特殊tokenを除く実測最大piece内部長 | 7 |
| 日本語指示の平均token数 | 31.54 |
| Pythonコードの平均token数 | 51.05 |
| 完成系列の平均token数 | 89.59 |
| 完成系列のp99 | 118 |
| 完成系列の最大 | 137 |
| 1エポックの系列token数 | 17,281,995 |
| tokenizer SHA-256 | `f09f3d7eccbca2ab1224c662064b71e572d64147147b8b559ebdb428eb035dbf` |

`min_frequency=2`でも、コーパスにmerge候補が十分存在したため、実語彙数は2,048に到達した。ただし、設定した語彙数は到達目標であり、どのコーパスでも必ず2,048語彙になるとは限らない。本実装では`require_exact_vocab_size: true`により、実語彙数が2,048未満なら失敗として扱う。

`max_token_length`は日本語の文字数ではなく、ByteLevel変換後の内部記号列に対する上限である。したがって、`max_token_length=8`は日本語8文字を意味しない。

成果物：

- [`config/tokenizer_bpe_2048_minfreq2_maxlen8.yaml`](../../config/tokenizer_bpe_2048_minfreq2_maxlen8.yaml)
- [`data/tokenizers/bpe_2048_minfreq2_maxlen8/tokenizer.json`](../../data/tokenizers/bpe_2048_minfreq2_maxlen8/tokenizer.json)
- [`data/tokenizers/bpe_2048_minfreq2_maxlen8/training_stats.json`](../../data/tokenizers/bpe_2048_minfreq2_maxlen8/training_stats.json)

## 比較結果

| 指標 | 実装例A：min 5 / max 24 | 実装例B：min 2 / max 8 | 変化 |
| --- | ---: | ---: | ---: |
| 実語彙数 | 2,048 | 2,048 | 同じ |
| 日本語指示・平均 | 11.55 | 31.54 | 2.73倍 |
| Pythonコード・平均 | 17.42 | 51.05 | 2.93倍 |
| 完成系列・平均 | 35.97 | 89.59 | 2.49倍 |
| 完成系列・p99 | 46 | 118 | 2.57倍 |
| 完成系列・最大 | 94 | 137 | 1.46倍 |
| 1エポックの系列token | 6,939,466 | 17,281,995 | 2.49倍 |
| 最大GPU使用量 | 16,264 MiB | 27,392 MiB | 1.68倍 |

最大GPU使用量は、同じ約15.7Mパラメータのモデル、`micro_batch_size=512`を使用した学習時の実測値である。実装例Bでは11,128 MiB、約68.4%増加した。現時点では測定手段が保存されていないため、`nvidia-smi`のプロセス使用量か、PyTorchの最大割当量かは未確定である。以後の比較では`torch.cuda.max_memory_allocated()`と`torch.cuda.max_memory_reserved()`をそれぞれ記録する。

## 同じモデルとバッチサイズでもGPU使用量が増える理由

語彙数が同じなので、embeddingと出力headを含むモデルのパラメータ数は変わらない。しかし、訓練時のGPUメモリはモデル重みだけでは決まらず、backward用に保持するactivationが大きな割合を占める。

実装例Bでは、同じ文章とコードがより多くのtokenへ分割される。現在のcollate処理は、バッチ内で最も長い系列へ全系列をpaddingする。512系列をランダムにまとめると、ほぼすべてのバッチにp99付近の長い系列が含まれる。

```text
実装例A: 512系列 × p99 46 token
実装例B: 512系列 × p99 118 token
```

同じ「batch size 512」でも、代表的なpadding後token枠は約2.57倍になる。各Transformer層では、hidden state、Query、Key、Value、SwiGLU中間値などをbackwardまで保持するため、系列長の増加に応じてactivationメモリが増える。attentionの計算量は系列長の二乗に近い形で増え、使用するkernelによっては作業領域にも影響する。

また、1エポックと3エポックの違いは最大GPUメモリを小さくしない。epoch数は同じ処理を何周するかを変える値であり、1回のforward・backwardで必要なピークメモリは、主にmicro batch内の系列数とpadding後系列長で決まる。

## 15Mモデルでの学習例

実装例Aは、既存の3エポック・10エポックモデルで使用した。

```bash
uv run --group model-training --python 3.12.12 python \
  scripts/model/train_boku_nano.py \
  --config config/boku_nano_bpe_2048.yaml
```

実装例Bは、同じ15,735,168パラメータ構成を1エポック学習する専用scriptを用意している。

```bash
scripts/model/run_boku_nano_minfreq2_maxlen8_1epoch_nohup.sh
```

対応する設定は[`config/boku_nano_bpe_2048_minfreq2_maxlen8_1epoch.yaml`](../../config/boku_nano_bpe_2048_minfreq2_maxlen8_1epoch.yaml)である。

二つのトークナイザーはどちらも2,048語彙だが、token IDとpieceの意味が異なる。既存の学習済みモデルへ別のトークナイザーだけを差し替えることはできず、トークナイザーごとにモデルをランダム初期値から学習する必要がある。

## GPUメモリを抑える方法

実装例Bを使用する場合は、micro batchを半分にし、gradient accumulationでoptimizer更新当たりの実効バッチサイズを維持する方法が現実的である。

```yaml
training:
  micro_batch_size: 256
  gradient_accumulation_steps: 2
  validation_batch_size: 256
```

さらに、系列長の近いレコードを同じバッチへまとめるlength bucketingを導入すると、短い系列を長い系列へ合わせるpaddingを減らせる。

## 使い分け

| 観点 | 実装例A：長いpiece | 実装例B：短いpiece |
| --- | --- | --- |
| 系列長 | 短い | 長い |
| 計算効率 | 良い | 不利 |
| GPUメモリ | 小さい | 大きい |
| 定型構文 | 少数tokenで表現 | 複数tokenへ分割 |
| 未学習表現 | 長いpiece依存の可能性 | 短い部分語で組み立てやすい可能性 |
| 現在の位置付け | 正式3・10エポックモデルで採用 | 1エポック比較実験 |

現時点では実装例Aが計算効率で明確に有利である。実装例Bを採用するかは、1エポックモデルのValidation loss、通常テスト、日本語言い換えテスト、生成速度を測り、系列長とGPU負荷の増加に見合う性能改善が得られるかで判断する。
