# BPEトークナイザ訓練結果

## 実行日

2026年9月25日

## 位置付け

最終訓練データ192,900件だけから、日本語指示とPythonコードを同一語彙で扱うBPEトークナイザ候補を学習した。これはUnigramとの比較前の候補であり、現時点では最終採用トークナイザではない。

## 実行コマンド

```bash
uv run --group tokenizer-training --python 3.12.12 python \
  scripts/tokenizer/train_tokenizer.py \
  --config config/tokenizer_bpe_2048.yaml
```

## 入力

| 項目 | 値 |
|---|---|
| 訓練ZIP | `data/archives/final_train_dataset_records_2026-09-25.zip` |
| ZIP内JSONL | `final_dataset_records.jsonl` |
| 訓練レコード | 192,900件 |
| 入力SHA-256 | `799e6dd8be7e80e48df69fed4f70f5922f7a215a8669cf0f523f3de59ae91807` |
| 使用項目 | `instruction_ja`、`reference_code` |

入力レコードは全件が`split=train`、`test_suite=null`、`dictionary=train`、`input_set=build`だった。評価レコード、`test_only`表現、意味AST、ID、ハッシュ、生成来歴、検証情報は学習コーパスへ入れていない。入力ZIPの処理前後SHA-256は一致した。

## 設定

| パラメータ | 値 |
|---|---|
| model type | BPE |
| 語彙数 | 2,048 |
| byte fallback | true |
| initial alphabet | ByteLevel 256 byte |
| normalizer | identity |
| add prefix space | false |
| regex分割 | false |
| minimum frequency | 5 |
| max token length | 24 |
| dropout | 0.0 |
| 最大系列長の検査値 | 256 |

実行環境はPython 3.12.12、PyYAML 6.0.3、tokenizers 0.21.4だった。

## 学習コーパス

`instruction_ja`と`reference_code`は項目別に完全一致重複を除外した。

| 項目 | 入力件数 | 重複除外 | 学習へ渡した件数 | UTF-8 bytes |
|---|---:|---:|---:|---:|
| 日本語指示 | 192,900 | 1,171 | 191,729 | 33,244,471 |
| Pythonコード | 192,900 | 0 | 192,900 | 52,059,684 |
| 合計 | 385,800 | 1,171 | 384,629 | 85,304,155 |

重複判定は本文UTF-8 byte列の完全一致であり、空白やUnicodeを正規化していない。

## 特殊トークン

| ID | トークン |
|---:|---|
| 0 | `<|pad|>` |
| 1 | `<|bos|>` |
| 2 | `<|eos|>` |
| 3 | `<|unk|>` |
| 4 | `<|task|>` |
| 5 | `<|code|>` |
| 6 | `<|explanation|>` |

全IDが設定どおりであることを完成`tokenizer.json`から再確認した。

## トークン長

### 日本語指示

| 指標 | トークン数 |
|---|---:|
| 平均 | 11.5547 |
| p50 | 11 |
| p95 | 15 |
| p99 | 19 |
| 最大 | 75 |

### Pythonコード

| 指標 | トークン数 |
|---|---:|
| 平均 | 17.4197 |
| p50 | 17 |
| p95 | 24 |
| p99 | 26 |
| 最大 | 29 |

### 完成系列

完成系列は次の形式で測定した。

```text
<|bos|><|task|>
{instruction_ja}
<|code|>
{reference_code}<|eos|>
```

| 指標 | トークン数 |
|---|---:|
| 平均 | 35.9744 |
| p50 | 36 |
| p95 | 43 |
| p99 | 46 |
| 最大 | 94 |
| 256超過 | 0件 |

## 全件検証

- 実語彙数は特殊トークン込みで2,048だった。
- 日本語指示192,900件、Pythonコード192,900件、完成系列192,900件のencode/decodeが完全一致した。
- roundtrip不一致は0件だった。
- 通常本文で`<|unk|>`は0件だった。
- 明示的な`<0xXX>`形式byte fallback tokenは0件だった。
- bos、task、code、eosの欠落または重複は0件だった。
- 256トークンを超える完成系列は0件だった。
- 入力訓練ZIPは処理前後で変更されなかった。

## 成果物

| ファイル | サイズ | SHA-256 |
|---|---:|---|
| `data/tokenizers/bpe_2048/tokenizer.json` | 176,013 bytes | `6840a392e8fcae1083be06842774fa912a1797217c7033944ba2d87f1c227293` |
| `data/tokenizers/bpe_2048/tokenizer_config.json` | 344 bytes | `85045150d137194e7b93a2e486d057b374d6749f8460e49cb0860cf9ddc83e19` |
| `data/tokenizers/bpe_2048/special_tokens_map.json` | 199 bytes | `b2c2157d8b8e45ac214154bb1aeeeab40cf48184f7022d38d792578bd1643435` |
| `data/tokenizers/bpe_2048/training_config.yaml` | 1,424 bytes | `df16f104a07d27ad6da0f3a9c42eca9ebee1323296987766ae755df4a3bf1c0a` |
| `data/tokenizers/bpe_2048/training_stats.json` | 14,425 bytes | `2bfc0cda8db992b9aa22d51550cf7d05cb4d9ca7fbd65762158834b7635e9a0c` |
| `data/tokenizers/bpe_2048/vocab.tsv` | 51,017 bytes | `c4127ceeab2eb3b18e3f0b0fc12b9f7028359419a08655ec2d8f536a4e73d73d` |

成果物合計は約260 KiBであるためZIP化せず、6ファイルを直接Gitで管理する。`training_stats.json`内の設定と入力パスはリポジトリ相対表記にし、clone先の絶対パスを含めていない。

## 次の作業

同じ訓練データと共通設定からUnigram 2,048語彙候補を作成する。その後、訓練データと固定済み評価データに対する系列長、未知語、byte分割、言い換え30件の分割状況を比較し、最終採用方式を決める。
