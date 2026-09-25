# 最終評価データ結合結果

## 実行日

2026年9月25日

## 目的

ルール生成した評価用日本語指示、言い換えテスト専用指示、検証済みPythonコード、固定済み評価入力6集合を最終評価レコードへ結合した。展開済みJSONLはローカル確認用に分け、Git管理用には6ファイルを格納した決定的BZIP2 ZIPを作成した。

## 実行コマンド

```bash
UV_CACHE_DIR=/tmp/bokunano-uv-cache \
uv run --python 3.12.12 python \
  scripts/instruction_generation/build_final_evaluation_records.py \
  --evaluation-instructions-archive data/archives/rule_generated_evaluation_instructions_2026-09-24.zip \
  --paraphrase-instructions-archive data/archives/paraphrase_test_instructions_2026-09-24.zip \
  --evaluation-code-archive data/archives/evaluation_python_code_candidates_2026-09-20.zip \
  --multi-operation-code-archive data/archives/multi_operation_python_code_candidates_2026-09-20.zip \
  --single-operation-codes data/code_candidates/single_operation/python_code_candidates.jsonl \
  --evaluation-input-stats data/evaluation_inputs/evaluation_input_stats.json \
  --output-dir data/final/evaluation \
  --archive data/archives/final_evaluation_dataset_records_2026-09-25.zip \
  --stats data/final/final_evaluation_dataset_stats.json \
  --expected-record-count 108590 \
  --pairing-seed 20260925
```

`UV_CACHE_DIR`は実行環境の既定uvキャッシュが読み取り専用だったため、一時領域へ向けた。依存関係とPythonはリポジトリのuv環境およびPython 3.12.12を使用した。

## 結合方法

1. validation、normal、compositional、repetitionは、意味ASTごとの指示20件とコード20件を元順序で一対一結合した。
2. paraphraseは、人手選定済み`test_only`指示30件へ、同じ単独操作の検証済み訓練コードを固定seedの安定順位で重複なく割り当てた。
3. boundaryはnormal 24,040件の指示、コード、`family_id`を維持し、評価入力参照と集合名だけを境界評価用に変更した。派生元は`derived_from_record_id`へ保存した。
4. 各レコードの`tests`には入力値を複製せず、対応する評価入力manifestの`test_set_id`を保存した。
5. 全レコードで`spec_id`と正規化意味AST、意味・コード・指示ハッシュ、検証済みコードの合格フラグを照合した。
6. 6集合横断で`record_id`を再計算し、一意性を確認した。

同じ意味AST内の指示とコードの直積は作っていない。boundaryだけは評価目的上normalの指示とコードを再利用するが、異なる`test_suite`と評価入力参照から別の`record_id`を作る。

## 件数

| 集合 | 最終レコード | 意味AST | 操作数内訳 | 入力集合 |
|---|---:|---:|---|---|
| validation | 24,040 | 1,202 | 2操作1,080、3操作22,960 | build 64入力 |
| normal | 24,040 | 1,202 | 2操作1,080、3操作22,960 | hidden 64入力 |
| compositional | 13,400 | 670 | 2操作200、3操作13,200 | hidden 64入力 |
| paraphrase | 30 | 24 | 1操作30 | hidden 64入力 |
| repetition | 23,040 | 1,152 | 2操作480、3操作22,560 | hidden 64入力 |
| boundary | 24,040 | 1,202 | 2操作1,080、3操作22,960 | 共通30入力とfilter AST固有964ケース |
| 合計 | 108,590 | 集合間重複を含む |  |  |

全108,590件の`record_id`は一意だった。boundaryがnormalの指示とコードを再利用するため、横断一意な`instruction_id`と`code_id`はそれぞれ84,550件である。

## 評価入力参照

| 集合 | `test_set_id` |
|---|---|
| validation | `validation-build-v1-seed-2026092601-cases-64` |
| normal | `normal-hidden-v1-seed-2026092602-cases-64` |
| compositional | `compositional-hidden-v1-seed-2026092603-cases-64` |
| paraphrase | `paraphrase-hidden-v1-seed-2026092604-cases-64` |
| repetition | `repetition-hidden-v1-seed-2026092605-cases-64` |
| boundary | `boundary-v1-shared-30-plus-filter-targeted` |

## 成果物

| ファイル | 件数・サイズ | SHA-256 | Git管理 |
|---|---:|---|---|
| `data/final/evaluation/validation_dataset_records.jsonl` | 24,040件、76,173,930 bytes | `d6933aae60fadcd4ae76fe76cfce304bbaaa515db8e74dfec60b0f20f2d2ba0d` | 対象外。ZIPから復元 |
| `data/final/evaluation/normal_test_dataset_records.jsonl` | 24,040件、76,361,527 bytes | `e554f0f80433522d1fbd43ef56fdb944894c4ea437424503af99b6d0d3339030` | 対象外。ZIPから復元 |
| `data/final/evaluation/compositional_test_dataset_records.jsonl` | 13,400件、42,829,965 bytes | `1e192d7831cf3fdbf8211a9cc43312225680b72bb99a5488a0d8dc2b5e1f777b` | 対象外。ZIPから復元 |
| `data/final/evaluation/paraphrase_test_dataset_records.jsonl` | 30件、83,189 bytes | `91975d88712d0184c5d443640bb55ab2b0f5bb1e14b08b722c985b53e822088d` | 対象外。ZIPから復元 |
| `data/final/evaluation/repetition_test_dataset_records.jsonl` | 23,040件、73,596,547 bytes | `dd4efa4a3bc8cc8061def315f68b815f77035ad2ec44386db0c1e1f636638f06` | 対象外。ZIPから復元 |
| `data/final/evaluation/boundary_test_dataset_records.jsonl` | 24,040件、79,029,967 bytes | `8edf3740914cbbee5258d3335c542e005c7330f2fcab85ba82462d92174fdf46` | 対象外。ZIPから復元 |
| `data/archives/final_evaluation_dataset_records_2026-09-25.zip` | 6ファイル、36,108,156 bytes | `5b05b76202920f532cb379481d1cfab4adad74e936bdff518cb8b1750b33f0a1` | 対象 |
| `data/final/final_evaluation_dataset_stats.json` | 集計JSON | `f03bbe682a3ccb1e625842ce8afcd1ff1c5474ce0f0c8cd0dda9b440da70bd76` | 対象 |

ZIP内6 JSONLの展開後合計は348,075,125 bytesである。メンバー順はvalidation、normal、compositional、paraphrase、repetition、boundaryで固定した。

## 入力不変確認

処理前後で、評価指示ZIP2件、コード入力ZIP2件、単独操作コードJSONL、評価入力集計JSON、評価入力manifest 6件のSHA-256がすべて一致した。個別値は`data/final/final_evaluation_dataset_stats.json`の`input_sha256_before`と`input_sha256_after`へ保存した。

## 検証結果

- 6集合の件数が期待値と一致し、合計108,590件だった。
- 全108,590件の`record_id`が一意だった。
- validation、normal、compositional、repetitionの全意味ASTが20指示対20コードだった。
- paraphrase 30件は24単独操作をすべて含み、指示IDとコードIDを重複使用していない。
- boundary 24,040件すべてに一意なnormal派生元があり、`family_id`が一致した。
- 全コードで構文、AST安全性、シグネチャ、実行結果、入力不変検証が合格済みだった。
- 入力12ファイルは処理前後で変更されていなかった。
- `unzip -t`で6メンバーすべてのCRCと展開可能性を確認した。
- 同じ条件で`--overwrite`再生成した後もZIPのSHA-256は`5b05b76202920f532cb379481d1cfab4adad74e936bdff518cb8b1750b33f0a1`で一致した。
- `ruff check`が成功し、既存を含む全50単体テストが成功した。

## 復元方法

リポジトリのルートで次を実行する。

```bash
mkdir -p data/final/evaluation
unzip data/archives/final_evaluation_dataset_records_2026-09-25.zip \
  -d data/final/evaluation/
sha256sum data/final/evaluation/*.jsonl
```
