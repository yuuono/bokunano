# Boku Nanoモデル評価方針

## 目的

学習済みBoku Nanoへ日本語指示だけを与えてPythonコードを生成させ、未学習の意味構造・表現・入力に対する機能的正しさを5種類の固定テスト集合で測定する。参照コードとの文字列一致ではなく、生成した`solve(xs, k)`の実行結果を主要判定にする。

学習中のvalidation lossは最適化状況の監視であり、この最終評価とは分離する。validation集合を5テストの成績へ含めない。

## 評価対象

| テスト名 | 内部識別子 | レコード | 評価目的 | 実行入力 |
|---|---|---:|---|---|
| 通常テスト | `normal` | 24,040 | 通常の未学習意味ASTと指示への汎化 | 専用hidden 64件 |
| 組合せ汎化テスト | `compositional` | 13,400 | 未学習の操作組み合わせへの汎化 | 専用hidden 64件 |
| 日本語言い換えテスト | `paraphrase` | 30 | 学習辞書外の日本語表現への汎化 | 専用hidden 64件 |
| 同一操作の反復テスト | `repetition` | 23,040 | 同一操作が隣接反復する構造への汎化 | 専用hidden 64件 |
| 境界値テスト | `boundary` | 24,040 | 空、単一要素、極値、重複、`k`境界などへの耐性 | 共通30件と対象filter固有1件 |
| 合計 | 84,550 |  |  |

評価レコードは`data/archives/final_evaluation_dataset_records_2026-09-25.zip`から直接読み、展開済みコピーを作らない。5集合のhidden入力は相互に分離され、訓練コード候補のbuild検証入力とも完全一致しない。

## 固定条件

- モデルは`training_manifest.json`が`status: completed`であるものだけを使う。
- `model.safetensors`のSHA-256は同じディレクトリの学習manifestと照合する。
- tokenizer、評価ZIP、各入力manifestは`config/boku_nano_evaluation.yaml`に固定したSHA-256と照合する。
- promptは学習時と同じ`<|bos|><|task|>\n{instruction_ja}\n<|code|>\n`とする。
- decodingはsamplingなしのgreedy decodingとする。
- 生成はEOS、最大生成160 token、またはモデルのcontext length到達で終了する。
- 同一モデルの再評価では、設定、モデルSHA-256、tokenizer SHA-256、評価データSHA-256を結果manifestへ残す。

異なるエポックのモデルを比較するときは、モデルディレクトリと結果ディレクトリだけを変更し、tokenizer、評価データ、decoding、検証条件は変更しない。

## 生成コードの検査

生成コードは既存の`generated_code_verifier.py`を通し、次の順で検査する。

1. Pythonとして構文解析できる。
2. 許可したAST、演算、組み込み関数だけを使う。
3. `solve(xs: list[int], k: int) -> list[int]`の固定signatureを持つ。
4. 隔離した子プロセス内で各入力を実行する。
5. 参照インタプリタの出力と完全一致する。
6. 入力リスト`xs`を変更しない。
7. 出力が整数だけを含むlistである。
8. 1生成コードに対する全case実行を5秒以内に終える。

静的検査に失敗したコードは実行しない。子プロセスはtimeout時に破棄して次のコード用に再作成する。これはOSやコンテナによる完全なsandboxではないため、評価対象はこのリポジトリで学習したモデルの出力に限定する。

## 合格判定と指標

1レコードは、対応する全入力で参照結果と一致し、入力不変・出力型条件も満たした場合だけ合格とする。主要指標は集合ごとのrecord pass rateである。

```text
record pass rate = 全case合格レコード数 / 評価レコード数
```

次の値は診断用に併記する。

- Validation loss
- Syntax-valid率
- Safe-AST率
- Signature-valid率
- Executable率
- pass@1
- 固定部分集合におけるpass@5
- 組合せ汎化率
- 最大GPUメモリ
- 生成tokens/s
- 操作数別のrecord pass rate
- EOS、最大生成token、context上限の終了理由
- timeout件数
- 参照コードとの完全文字列一致件数
- 構文・安全性・signature・実行結果の失敗内容

参照コードとの文字列一致は主要指標にしない。同じ機能を持つ別実装を正解として扱うためである。また、集合間の件数と目的が異なるため、全84,550件を単純合算した精度だけでモデルを判断せず、5集合を個別に報告する。

pass@1はsamplingなしのgreedy生成1候補で測る。pass@5は計算量が5倍になるため、全件の正式評価とは分け、固定seedで選んだ共通部分集合に対してgreedy 1候補とsampling 4候補のうち1候補以上が合格した割合を報告する。samplingのseed、temperature、top-p、比較集合IDを結果manifestへ残す。

## 比較実験

最低1件の比較実験として、学習前ランダムモデルと学習済みモデルを比較する。ランダムモデルは学習時と同じ構造・初期化seed・tokenizerを使い、両モデルへ同じ日本語指示とhidden testを適用する。

比較時はValidation loss、Syntax-valid率、Safe-AST率、Signature-valid率、Executable率、pass@1、pass@5、最大GPUメモリ、tokens/sを同じ条件で記録する。比較用部分集合はrecord IDと固定seedのhash順で選び、結果の良否によって選び直さない。

## 実行手順

### 推論なしの事前確認

```bash
uv run --group model-training --python 3.12.12 python \
  scripts/model/evaluate_boku_nano.py \
  --config config/boku_nano_evaluation.yaml \
  --validate-config
```

### 最小smoke test

まず30件の日本語言い換えテストで、モデル読込、生成、静的検査、隔離実行、集計までを確認する。コマンドでは内部識別子`paraphrase`を指定する。

```bash
uv run --group model-training --python 3.12.12 python \
  scripts/model/evaluate_boku_nano.py \
  --config config/boku_nano_evaluation.yaml \
  --suite paraphrase
```

### 5集合の正式評価

```bash
uv run --group model-training --python 3.12.12 python \
  scripts/model/evaluate_boku_nano.py \
  --config config/boku_nano_evaluation.yaml
```

中断後は同じ条件で`--resume`を追加する。既存結果を最初から置き換える場合だけ`--overwrite`を使う。動作確認で件数を絞る場合は`--max-records 10`のように指定し、正式結果とは別の出力ディレクトリを使う。

### 10エポックモデルとの比較

```bash
uv run --group model-training --python 3.12.12 python \
  scripts/model/evaluate_boku_nano.py \
  --config config/boku_nano_evaluation.yaml \
  --model-directory data/models/boku_nano_bpe_2048_10epoch \
  --output-directory data/evaluations/boku_nano_bpe_2048_10epoch
```

## 出力

`data/evaluations/<model>/`に次を保存する。

| ファイル | 内容 |
|---|---|
| `<suite>_results.jsonl` | record単位の生成コード、終了理由、検証結果 |
| `<suite>_summary.json` | 集合全体と操作数別の合格率 |
| `evaluation_manifest.json` | モデル・データhash、実行条件、集合別summary |

生JSONLは生成コードと失敗時の入力情報を含み、大容量になるためGit管理対象外とする。結果を公開する場合は、5集合のsummaryと再現条件を別の結果Markdownへ転記し、生JSONLやhidden入力を公開物へ複製しない。
