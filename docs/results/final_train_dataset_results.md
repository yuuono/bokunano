# 最終訓練データ結合結果

## 実行日

2026年9月25日

## 目的

教師言い換えを一対一置換した訓練用日本語指示192,900件と、検証済みPythonコード候補192,920件を、同じ`spec_id`かつ同じ正規化意味ASTの範囲で一対一結合した。全指示を一度ずつ使用し、指示数が20件未満の6意味ASTで余るコード20件は削除せず、元JSONLの情報を保った不採用記録へ分離した。

## 実行コマンド

```bash
UV_CACHE_DIR=/tmp/bokunano-uv-cache \
uv run --python 3.12.12 python \
  scripts/instruction_generation/build_final_train_records.py \
  --instructions data/instructions/replacement_resolved_train_instructions.jsonl \
  --single-operation-codes data/code_candidates/single_operation/python_code_candidates.jsonl \
  --multi-operation-code-archive data/archives/multi_operation_python_code_candidates_2026-09-20.zip \
  --output-jsonl data/final/final_dataset_records.jsonl \
  --archive data/archives/final_train_dataset_records_2026-09-25.zip \
  --rejected-codes data/final/rejected_train_code_candidates.jsonl \
  --test-set-manifest data/final/build_verification_test_set.json \
  --stats data/final/final_train_dataset_stats.json \
  --expected-record-count 192900 \
  --expected-code-count 192920 \
  --pairing-seed 20260925 \
  --overwrite
```

`UV_CACHE_DIR`は実行環境の既定uvキャッシュが読み取り専用だったため、一時領域へ向けた。依存関係とPythonはリポジトリのuv環境およびPython 3.12.12を使用している。

## 結合方法

1. 指示JSONLと1・2・3操作コードJSONLを、元ファイルの意味AST順でストリーム処理した。
2. 全9,646意味ASTについて`spec_id`と正規化した`semantic_ast`を照合した。
3. 20指示・20コードがある9,640意味ASTは、全件を元順序で一対一結合した。
4. 指示数が20件未満の6意味ASTは、`code_style`別採用数をできるだけ均等にし、同順位を`pairing_seed=20260925`から決定的に選んだ。
5. 全指示ID、採用コードID、最終レコードIDの一意性を検査した。
6. 元指示来歴、教師モデル来歴、コード生成来歴、意味・コード・指示ハッシュを最終レコードへ保存した。
7. コード生成時の境界9件とseed 0のランダム32件を共有テスト集合として保存し、各最終レコードの`tests`からID参照した。

## 件数

| 項目 | 件数 |
|---|---:|
| 入力日本語指示 | 192,900 |
| 入力コード候補 | 192,920 |
| 意味AST | 9,646 |
| 最終訓練レコード | 192,900 |
| 採用コード | 192,900 |
| 指示不足で不採用にしたコード | 20 |
| 共有コード検証入力 | 41 |

### 操作数別

| 操作数 | 最終レコード数 |
|---:|---:|
| 1 | 460 |
| 2 | 8,680 |
| 3 | 183,760 |
| 合計 | 192,900 |

### 日本語指示生成元別

| 生成元 | 最終レコード数 |
|---|---:|
| ルール生成を維持 | 96,510 |
| 承認済み教師言い換えへ置換 | 96,390 |
| 合計 | 192,900 |

### コード形式別

| `code_style` | 最終レコード数 |
|---|---:|
| `expression_comprehension` | 4,458 |
| `mixed` | 95,043 |
| `staged_comprehension` | 66,058 |
| `staged_loop` | 27,341 |
| 合計 | 192,900 |

### 意味AST当たり最終レコード数

| 最終レコード数 | 意味AST数 |
|---:|---:|
| 11 | 1 |
| 16 | 1 |
| 17 | 1 |
| 18 | 1 |
| 19 | 2 |
| 20 | 9,640 |

## 指示不足6意味ASTの処理

| `spec_id` | 意味AST | 指示・採用コード | 入力コード | 不採用コード |
|---|---|---:|---:|---:|
| `combined-000010` | `filter: zero` | 11 | 20 | 9 |
| `combined-000007` | `filter: multiple_of_k` | 16 | 20 | 4 |
| `combined-000019` | `order: ascending` | 17 | 20 | 3 |
| `combined-000009` | `filter: negative` | 18 | 20 | 2 |
| `combined-000016` | `map: negate` | 19 | 20 | 1 |
| `combined-000008` | `filter: positive` | 19 | 20 | 1 |
| 合計 |  | 100 | 120 | 20 |

不採用JSONLには`code_id`、`spec_id`、`semantic_ast`、`reference_code`、`code_style`、`style_id`、`style_spec`、各ハッシュ、生成条件、検証結果を含む元コード候補の全項目を残した。その上で`reason=instruction_shortfall`、指示数、コード数、選抜方式、`pairing_seed`を追加した。したがって、不採用20件の元JSONL情報も失われていない。

## 入力不変確認

処理前後で次のSHA-256が一致した。

| 入力 | SHA-256 |
|---|---|
| 置換反映済み訓練指示JSONL | `a33ec7d4cf9a7e14581113dbbf85266ce8c55796db9e947ebf2f9f7959cef73b` |
| 1操作コードJSONL | `885da0686230e80e08ee79f671f33f3d6ee952976d79ce50dad7ce4c99e8cca6` |
| 2・3操作コードZIP | `369fb2175c715f15c6c7aeccd6d3ce96191404dac4537da8d72774e52d862a8e` |

## 成果物

| ファイル | 件数・サイズ | SHA-256 | Git管理 |
|---|---:|---|---|
| `data/final/final_dataset_records.jsonl` | 192,900件、742,098,087 bytes | `48f378c8d303d7c8faf3a8a1b98c8b42ead7e0ae5cd2188bf3f5ba31a3f2cdac` | 対象外。ZIPから復元 |
| `data/archives/final_train_dataset_records_2026-09-25.zip` | 79,184,641 bytes | `799e6dd8be7e80e48df69fed4f70f5922f7a215a8669cf0f523f3de59ae91807` | 対象 |
| `data/final/rejected_train_code_candidates.jsonl` | 20件、29,298 bytes | `a73d292376d391e09e4065fd0701a80ceb529c2fc8c5942ad8ba7177c75c4aa8` | 対象 |
| `data/final/build_verification_test_set.json` | 41入力、7,659 bytes | `72373d2dffce5adf01f83e0855572b0438308014eeb403dc8413f8cbc2090b32` | 対象 |
| `data/final/final_train_dataset_stats.json` | 4,743 bytes | `d9ce2786d1471278dacf1a339c9841f648f035761feef10c6155b57c4425ba9c` | 対象 |

ZIPには`final_dataset_records.jsonl`だけを格納した。ZIP内JSONLはローカルJSONLと同じ742,098,087 bytesである。

## ZIP方式の確認履歴

最初のDEFLATE ZIPは101,888,526 bytesで、GitHubの単一ファイル上限100,000,000 bytesを超えた。次にLZMA ZIPを試すと66,084,455 bytesまで縮んだが、実行環境の一般的な`unzip`が方式v6.3へ未対応だった。最終的にBZIP2 ZIPを採用し、79,184,641 bytesで上限内に収め、次の展開検査が成功した。

```text
Archive:  data/archives/final_train_dataset_records_2026-09-25.zip
    testing: final_dataset_records.jsonl   OK
No errors detected in compressed data of data/archives/final_train_dataset_records_2026-09-25.zip.
```

## 検証結果

- 最終レコード数192,900件、意味AST数9,646件が期待値と一致した。
- 全192,900指示を一度ずつ使用した。
- 採用コード192,900件と不採用コード20件は重複せず、合計が入力192,920件と一致した。
- `record_id`、`instruction_id`、採用`code_id`はそれぞれ一意だった。
- 全レコードで`spec_id`と正規化意味ASTが指示・コード間で一致した。
- 全レコードで`semantic_hash`、`code_hash`、`text_hash`、`family_id`、`record_id`を再計算して一致した。
- 全レコードが`split=train`、`test_suite=null`、`dictionary=train`、`input_set=build`だった。
- 全コードの構文・AST安全性・シグネチャ・実行結果・入力不変検証が合格済みだった。
- 教師由来96,390件ではモデル名、revision、`prompt_hash`が存在し、ルール由来96,510件では3項目が`null`だった。
- 入力3ファイルは処理前後のSHA-256が一致した。
- 同じコマンドによる再生成後も最終JSONLのSHA-256は`48f378c8d303d7c8faf3a8a1b98c8b42ead7e0ae5cd2188bf3f5ba31a3f2cdac`で一致した。
- `unzip -t`でBZIP2 ZIPのCRCと展開可能性を確認した。
- `ruff check`が成功し、全44単体テストが成功した。

## 復元方法

リポジトリのルートで次を実行する。

```bash
mkdir -p data/final
unzip data/archives/final_train_dataset_records_2026-09-25.zip -d data/final/
sha256sum data/final/final_dataset_records.jsonl
```

期待するSHA-256は`48f378c8d303d7c8faf3a8a1b98c8b42ead7e0ae5cd2188bf3f5ba31a3f2cdac`である。
