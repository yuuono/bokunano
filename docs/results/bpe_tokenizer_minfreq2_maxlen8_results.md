# BPE 2,048語彙・最小頻度2・最大piece長8の作成結果

## 結論

`min_frequency=2`、`max_token_length=8`でも、最終語彙数を特殊token込みで**2,048**にできた。192,900件の訓練データだけから学習し、unknown token、round-trip不一致、最大系列長256超過はいずれも0件だった。

ただし、`max_token_length`を24から8へ小さくした影響で系列が大幅に長くなった。1レコードの平均系列長は35.97 tokenから89.59 tokenへ増え、1エポック当たりの系列token数は6,939,466から17,281,995へ約2.49倍になった。語彙数は同じでも、現在の3・10エポックモデルとtoken IDの意味は異なるため、既存モデルへこのトークナイザーだけを差し替えることはできない。使用する場合はモデルをランダム初期値から再学習する。

## 設定

| 項目 | 既存BPE | 今回のBPE |
| --- | ---: | ---: |
| vocab size | 2,048 | 2,048 |
| min frequency | 5 | 2 |
| max token length | 24 | 8 |
| pre-tokenizer | ByteLevel | ByteLevel |
| byte fallback | 有効 | 有効 |
| dropout | 0 | 0 |
| 学習データ | train 192,900件 | 同じtrain 192,900件 |

`max_token_length`は、人間が見る日本語の文字数ではなく、ByteLevel変換後の内部記号列に対する上限である。日本語1文字はUTF-8で複数byteになるため、`8`は日本語8文字を意味しない。今回の実語彙では、特殊tokenを除くpieceの内部長は最大7だった。

設定ファイルは[`config/tokenizer_bpe_2048_minfreq2_maxlen8.yaml`](../../config/tokenizer_bpe_2048_minfreq2_maxlen8.yaml)に保存した。

## 実行結果

| 検査 | 結果 |
| --- | ---: |
| 設定語彙数 | 2,048 |
| 実語彙数 | 2,048 |
| unknown token | 0件 |
| round-trip不一致 | 0件 |
| 必須特殊token不一致 | 0件 |
| 256 token超過 | 0件 |
| 最大系列長 | 137 token |
| tokenizer SHA-256 | `f09f3d7eccbca2ab1224c662064b71e572d64147147b8b559ebdb428eb035dbf` |

`min_frequency=2`に下げても、このコーパスには条件を満たすmerge候補が十分存在したため、trainerは2,048語彙まで到達した。設定では`require_exact_vocab_size: true`としているので、2,048未満なら学習処理は成功扱いにならない。

## 既存BPEとの系列長比較

| 指標 | 既存：min 5 / max 24 | 今回：min 2 / max 8 | 変化 |
| --- | ---: | ---: | ---: |
| 日本語指示・平均 | 11.55 | 31.54 | 2.73倍 |
| 日本語指示・p95 | 15 | 37 | 2.47倍 |
| 日本語指示・最大 | 75 | 75 | 同じ |
| Pythonコード・平均 | 17.42 | 51.05 | 2.93倍 |
| Pythonコード・p95 | 24 | 72 | 3.00倍 |
| Pythonコード・最大 | 29 | 93 | 3.21倍 |
| 完成系列・平均 | 35.97 | 89.59 | 2.49倍 |
| 完成系列・p95 | 43 | 111 | 2.58倍 |
| 完成系列・p99 | 46 | 118 | 2.57倍 |
| 完成系列・最大 | 94 | 137 | 1.46倍 |
| 1エポックの系列token | 6,939,466 | 17,281,995 | 2.49倍 |

最大系列長256には収まるため学習は可能である。一方、同じ192,900件・同じepoch数でも処理token数が約2.49倍になるので、学習時間、GPU計算量、attention計算量は増える。特にコード平均長は約2.93倍であり、ブラウザ推論の生成step数も増える可能性が高い。

## 成果物

| 成果物 | 内容 |
| --- | --- |
| [`tokenizer.json`](../../data/tokenizers/bpe_2048_minfreq2_maxlen8/tokenizer.json) | 学習済みトークナイザー本体 |
| [`training_config.yaml`](../../data/tokenizers/bpe_2048_minfreq2_maxlen8/training_config.yaml) | 実行時設定の固定コピー |
| [`training_stats.json`](../../data/tokenizers/bpe_2048_minfreq2_maxlen8/training_stats.json) | コーパス、語彙、全件検証結果、hash |
| [`vocab.tsv`](../../data/tokenizers/bpe_2048_minfreq2_maxlen8/vocab.tsv) | ID順語彙一覧 |
| [`tokenizer_config.json`](../../data/tokenizers/bpe_2048_minfreq2_maxlen8/tokenizer_config.json) | 最大系列長などの設定 |
| [`special_tokens_map.json`](../../data/tokenizers/bpe_2048_minfreq2_maxlen8/special_tokens_map.json) | 特殊token対応 |

## 再生成方法

```bash
.venv/bin/python scripts/tokenizer/train_tokenizer.py \
  --config config/tokenizer_bpe_2048_minfreq2_maxlen8.yaml
```

既存成果物を明示的に再生成する場合だけ`--overwrite`を付ける。

## 15Mモデルの1エポック学習

新しいトークナイザーを使用し、既存モデルと同じ15,735,168 parameter構成をランダム初期値から1 epoch学習する設定と起動scriptを用意した。既存の3・10エポックモデルとは別の出力先を使う。

| 項目 | 値 |
| --- | --- |
| model config | [`config/boku_nano_bpe_2048_minfreq2_maxlen8_1epoch.yaml`](../../config/boku_nano_bpe_2048_minfreq2_maxlen8_1epoch.yaml) |
| 起動script | [`run_boku_nano_15m_1epoch_nohup.sh`](../../scripts/model/run_boku_nano_15m_1epoch_nohup.sh) |
| parameter数 | 15,735,168 |
| epoch数 | 1 |
| 1 epochの系列token | 17,281,995 |
| 出力先 | `data/models/boku_nano_15m_bpe_2048_minfreq2_maxlen8_1epoch/` |
| console log | `data/models/boku_nano_15m_bpe_2048_minfreq2_maxlen8_1epoch_console.log` |

学習前検証では、語彙数2,048、トークナイザーSHA-256、特殊token ID、モデルparameter数、訓練・validation ZIPのSHA-256がすべて一致した。学習は次でbackground起動できる。

```bash
scripts/model/run_boku_nano_15m_1epoch_nohup.sh \
  --tokenizer bpe_2048_minfreq2_maxlen8
```

scriptは実行中PIDによる二重起動と、既存出力ディレクトリの暗黙上書きを拒否する。

## 採用判断

この構成は、長い日本語テンプレートやPython文全体に近いpieceを抑え、短い部分語へ分割する比較実験として利用できる。ただし、現行BPEより系列が約2.49倍長くなるため、計算効率では不利である。

次の比較では、同じモデル構造をこのトークナイザーでランダム初期化して学習し、通常テストと言い換えテストを比較する必要がある。特に確認すべきなのは、短いpieceが未学習の言い換えに有利か、コード生成stepの増加による誤りが増えないか、学習時間がどの程度増えるかである。
