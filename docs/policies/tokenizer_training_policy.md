# トークナイザ作成方針

## 1. 目的

最終訓練データだけを用いて、日本語指示とPythonコードを同一語彙で扱う2,048語彙のトークナイザをゼロから作成する。BPEとUnigramを同じ入力、特殊トークン、ByteLevel前処理、検証条件でそれぞれ学習し、実測結果から採用方式を決める。

既存モデルの語彙や評価データから語彙を移植しない。教師モデルQwen3のトークナイザも使用しない。

## 2. 学習入力

入力は次の最終訓練ZIPに固定する。

| 項目 | 値 |
|---|---|
| ZIP | `data/archives/final_train_dataset_records_2026-09-25.zip` |
| ZIP内JSONL | `final_dataset_records.jsonl` |
| SHA-256 | `799e6dd8be7e80e48df69fed4f70f5922f7a215a8669cf0f523f3de59ae91807` |
| 訓練レコード | 192,900件 |

各レコードから使用するのは次の2項目だけである。

1. `instruction_ja`
2. `reference_code`

`record_id`、`code_id`、`spec_id`、意味AST、各種SHA-256、生成来歴、検証結果、評価入力参照はトークナイザ学習へ入れない。JSONL一行全体を学習テキストとして渡さない。

入力レコードは全件で次を満たすことを機械的に確認する。

```text
split=train
test_suite=null
dictionary=train
input_set=build
```

validation、normal、compositional、paraphrase、repetition、boundaryの各評価レコードと`test_only`表現は、トークナイザ学習にも使用しない。評価データは完成トークナイザの解析にだけ使用する。

## 3. コーパスの重複制御

同じ日本語指示やコードが異なる組合せ由来で繰り返されても、トークナイザ語彙がその複製数へ過度に引っ張られないよう、`instruction_ja`と`reference_code`を項目別に完全一致で重複除去する。

重複判定は本文UTF-8 byte列のSHA-256で行う。正規化後の一致や空白除去後の一致にはしない。したがって、改行、インデント、コメント、変数名が異なるコードは別テキストとして残る。

重複除去の有無はYAMLの次の項目で変更できるが、正式比較では両方式を同じ値にする。

```yaml
corpus:
  deduplicate:
    instruction_ja: true
    reference_code: true
```

## 4. 共通前処理

BPEとUnigramの両方で`tokenizers`のByteLevel前処理を使用する。

```yaml
normalizer:
  type: identity

pre_tokenizer:
  type: byte_level
  add_prefix_space: false
  use_regex: false
  initial_alphabet: byte_level_256
```

- `identity`により大文字小文字、全角半角、互換文字を自動変換しない。
- 連続空白、タブ、改行、行末改行を削除しない。
- `add_prefix_space=false`により、先頭へ存在しない空白を追加しない。
- `use_regex=false`により、GPT-2固有の単語境界で日本語とコードを追加分割しない。
- 256 byteすべてを初期alphabetへ入れ、`byte_fallback=true`と組み合わせる。
- 入力は元レコード順・項目順に固定し、shuffleやランダム抽出を行わない。

Pythonではインデントと改行が意味を持つため、採用条件は`decode(encode(text)) == text`の完全一致である。

使用する`tokenizers==0.21.4`のUnigram trainerはseed指定を公開していないため、再学習したJSONのbyte単位一致を完了条件にはしない。入力、設定、依存版と生成物SHA-256を記録し、比較後に選定した`tokenizer.json`を固定成果物としてモデル訓練と評価で共用する。BPEも含め、再学習結果へ暗黙に差し替えない。

## 5. 語彙数と特殊トークン

最終語彙数は特殊トークンと256 byte alphabetを含めて2,048とする。学習後に特殊トークンを追加して2,055語彙に増やさない。

| ID | 名前 | トークン |
|---:|---|---|
| 0 | pad | `<|pad|>` |
| 1 | bos | `<|bos|>` |
| 2 | eos | `<|eos|>` |
| 3 | unk | `<|unk|>` |
| 4 | task | `<|task|>` |
| 5 | code | `<|code|>` |
| 6 | explanation | `<|explanation|>` |

`<|unk|>`はUnigram内部でもID 3へ固定する。byte coverageが正しく機能すれば通常本文では出現しない。`<|explanation|>`は将来用に予約するだけであり、説明文のない現在のデータから説明生成能力を学習するものではない。

モデルへ渡す完成系列は次の形式に固定する。

```text
<|bos|><|task|>
{instruction_ja}
<|code|>
{reference_code}<|eos|>
```

padは保存系列へ直接入れず、batch作成時に追加する。tokenizer側でBOS/EOSを自動追加せず、データ作成側で上記形式を一度だけ構成する。

## 6. BPE設定

正式候補は次の設定から開始する。

```yaml
model:
  type: bpe
  vocab_size: 2048
  byte_fallback: true
  unk_token: <|unk|>
  min_frequency: 5
  max_token_length: 24
  dropout: 0.0
```

- `min_frequency`は頻度5未満のpairをmergeしない。
- `max_token_length=24`はByteLevel変換後の長さを上限にし、日本語では概ね8文字分に相当する。頻出の日本語文全体が単一pieceになることを抑える。
- `dropout=0.0`で学習後の分割を決定的にする。0より大きい値は実験可能だが、正式比較では使用しない。

BPEはPythonのキーワード、演算子、定型構文を短く表現しやすく、分割規則が理解しやすい。反面、頻出する日本語テンプレートへ長いpieceを割り当て、未学習言い換えを細かく分割する可能性がある。

## 7. Unigram設定

正式候補は次の設定から開始する。

```yaml
model:
  type: unigram
  vocab_size: 2048
  byte_fallback: true
  unk_token: <|unk|>
  shrinking_factor: 0.75
  max_piece_length: 24
  n_sub_iterations: 2
```

- `shrinking_factor=0.75`で各剪定段階に残す候補割合を固定する。
- `max_piece_length=24`で長すぎるpieceを禁止する。
- `n_sub_iterations=2`で各剪定段階のEM反復回数を固定する。
- 推論時は最尤の決定的分割を使い、最初の比較ではsubword regularizationを使わない。

Unigramは日本語の未学習表現を既知の短いpieceへ分解しやすい可能性がある。反面、Pythonの記号列や定型構文がBPEより細かくなる可能性がある。

## 8. YAMLで変更できる主なパラメータ

| YAML項目 | 対象 | 意味 |
|---|---|---|
| `model.type` | 共通 | `bpe`または`unigram` |
| `model.vocab_size` | 共通 | 特殊トークン込み最終語彙数 |
| `model.byte_fallback` | 共通 | 未登録文字をbyteへ落とす。正式設定ではtrue必須 |
| `model.unk_token` | 共通 | unknownトークン本文 |
| `model.min_frequency` | BPE | mergeに必要な最小pair頻度 |
| `model.max_token_length` | BPE | 作成可能なpiece最大長 |
| `model.dropout` | BPE | encode時のmerge dropout |
| `model.shrinking_factor` | Unigram | 候補pieceの段階的剪定率 |
| `model.max_piece_length` | Unigram | piece最大長 |
| `model.n_sub_iterations` | Unigram | 剪定段階ごとのEM反復数 |
| `corpus.deduplicate.*` | 共通 | 項目別完全一致重複除去 |
| `pre_tokenizer.add_prefix_space` | 共通 | 先頭空白の自動追加 |
| `pre_tokenizer.use_regex` | 共通 | GPT-2形式の正規表現分割 |
| `validation.model_max_length` | 共通 | 超過率を測る系列長 |
| `validation.fail_on_overlength` | 共通 | 1件でも超過したら失敗させるか |

正規化方式、特殊トークン、コーパス、最大系列長を変更した実験は、BPEとUnigramの公平な比較にならないため、同じ比較組では揃える。

## 9. 生成物

各出力ディレクトリに次を保存する。

| ファイル | 内容 |
|---|---|
| `tokenizer.json` | model、normalizer、ByteLevel、decoder、特殊トークンを含む本体 |
| `tokenizer_config.json` | Transformers読込み用設定 |
| `special_tokens_map.json` | 特殊トークンの役割対応 |
| `training_config.yaml` | 実際に使用した解決済み設定 |
| `training_stats.json` | 入力ハッシュ、コーパス件数、語彙数、系列長、復元検証 |
| `vocab.tsv` | ID順の確認用語彙一覧 |

既存出力は既定で保護し、意図的に置き換える場合だけ`--overwrite`を使用する。一時ディレクトリで全検証に合格した後に完成出力へ置き換える。

## 10. 必須検証

完成前に次を全件確認する。

1. 入力ZIPのSHA-256とCRCが固定値と一致する。
2. 入力192,900件がtrain固定条件を満たす。
3. 入力ZIPの処理前後SHA-256が一致する。
4. 語彙数が特殊トークン込みで正確に2,048である。
5. 特殊トークンの本文とIDが表どおりである。
6. 学習済みmodelの`byte_fallback`がtrueである。
7. 日本語指示、Pythonコード、完成系列が全件encode/decode完全一致する。
8. 通常本文で`<|unk|>`が0件である。
9. 完成系列にbos、task、code、eosが各1件ある。
10. 256トークン超過件数、平均、p50、p95、p99、最大を保存する。
11. Python、PyYAML、tokenizersの実行版を保存する。
12. `tokenizer.json`を含む全生成物のSHA-256を保存し、モデル訓練と評価では選定時に固定した同一成果物を使う。

byte fallbackが有効なため、未知語の評価には`<|unk|>`率だけでなく、明示的byte fallback tokenの使用数と系列長増加を併記する。

## 11. BPEとUnigramの選定

両方式を同じデータと条件で作った後、次の順で判断する。

1. 完全復元、unknown 0、固定IDを満たさない方式は不採用にする。
2. 256トークン超過件数が少ない方式を優先する。
3. 訓練データの日本語指示とコードについて平均、p95、p99トークン数を比較する。
4. トークナイザ学習には使わず、paraphrase 30件のbyte分割率と系列長を比較する。
5. 小規模な同一モデル・同一token budget実験でvalidation lossとコード実行成功率を比較する。

系列長と下流性能が同程度なら、Python構文の分割が安定し実装が単純なBPEを第一候補とする。Unigramが言い換え表現を明確に短く表し、コード側の系列長と実行成功率を悪化させない場合はUnigramを採用する。

## 12. 再現コマンド

依存環境を復元する。

```bash
uv sync --python 3.12.12 --group tokenizer-training
```

BPEを作る。

```bash
uv run --group tokenizer-training --python 3.12.12 python \
  scripts/tokenizer/train_tokenizer.py \
  --config config/tokenizer_bpe_2048.yaml
```

Unigramを作る。

```bash
uv run --group tokenizer-training --python 3.12.12 python \
  scripts/tokenizer/train_tokenizer.py \
  --config config/tokenizer_unigram_2048.yaml
```

設定、入力SHA-256、ZIP CRCだけを検査する場合は、各コマンドへ`--validate-config`を追加する。
