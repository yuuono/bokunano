# Boku1-nano Dataset Card

## 概要

Boku1-nanoのデータは、日本語の指示から`solve(xs, k) -> list[int]`形式のPython関数を生成する限定領域の合成データである。整数リストに対する24種類の単独操作と、その1〜3操作の組合せを扱う。

| 分割・集合 | レコード数 | 主な用途 |
| --- | ---: | --- |
| train | 192,900 | tokenizer学習、モデル学習 |
| validation | 24,040 | epochごとのvalidation loss |
| 全評価成果物 | 108,590 | validation、通常、組合せ、言い換え、反復、境界評価 |

訓練archiveは`data/archives/final_train_dataset_records_2026-09-25.zip`、SHA-256は`799e6dd8be7e80e48df69fed4f70f5922f7a215a8669cf0f523f3de59ae91807`である。評価archiveは`data/archives/final_evaluation_dataset_records_2026-09-25.zip`、SHA-256は`5b05b76202920f532cb379481d1cfab4adad74e936bdff518cb8b1750b33f0a1`である。

## 生成方法

1. 自作の24操作定義から意味ASTを作る。
2. 意味ASTから自作テンプレートでPythonコード候補を生成する。
3. `ast.parse`、Safe-AST、signature、隔離実行テストでコードを検証する。
4. 自作の日本語表現辞書とルールで日本語指示を生成する。
5. 一部の日本語表現候補と言い換え候補だけをQwen3で生成する。
6. instruction、code、意味AST、split、由来を結合し、hash付きレコードにする。

コード本文はQwen3へ生成させていない。インターネット、GitHub、オンライン記事、既存コード集からコードを収集していない。コード側は自作テンプレートとルール生成物だけで構成する。

## 教師モデルの使用

- model: `Qwen/Qwen3-4B-AWQ`
- revision: `74d4bd2bd4bff9cafc9345221320bffb08b406a3`
- license: Apache License 2.0
- thinking: disabled
- network: generation時は`local_files_only=true`
- saved license: `third_party/qwen3-4b-awq/LICENSE`

単独操作表現では主に`max_new_tokens=2048`、`temperature=0.9`、`top_p=0.95`、`top_k=50`、`repetition_penalty=1.1`を使用した。追加roundの一部ではtemperatureを`1.0`へ変更しており、各roundのseedを含む正確な条件は`config/qwen_atomic_expression_generation*.json`に保存している。

訓練指示の言い換えでは`max_new_tokens=256`、`temperature=0.9`、`top_p=0.8`、`top_k=20`、`repetition_penalty=1.05`を使用した。正確な条件は`config/qwen_instruction_paraphrase_generation.json`に保存している。

プロンプト本文は`prompts/japanese_instruction_generation/`に保存し、採用済み単独表現のmodel、revision、seed、sampling、生成日時、prompt hashは`data/instruction_dictionaries/release/japanese_atomic_expression_provenance.jsonl`に保存している。全文言い換えは96,390件を使用し、96,510件はルール指示を維持した。

## 長い一致と来歴検査

`scripts/validation/check_long_code_matches.py`により、最終訓練192,900件を検査した。

| 検査項目 | 結果 |
| --- | ---: |
| `code_generator_version`またはseedの欠落 | 0 |
| `reference_code`と`code_hash`の不一致 | 0 |
| リポジトリ内既存Pythonコードとの24字句以上の完全一致 | 0 |

結果は`data/provenance/long_code_match_report.json`に保存している。この結果は、記録した比較コーパスに対する完全一致検査である。未知の非公開コードやインターネット上の全コードとの非一致を証明するものではない。

## データ漏洩対策

- train、validation、通常、組合せ、言い換え、反復の意味ASTを方針に基づいて分離した。
- validation・hidden test入力はコード作成時の検証入力と分けた。
- code hashと全文比較で分割間の完全重複を検査した。
- 教師言い換えはtrain由来の指定集合だけを対象にした。
- tokenizerはtrainのinstructionとreference codeだけから学習した。

詳細は`docs/policies/`、`docs/results/final_train_dataset_results.md`、`docs/results/final_evaluation_dataset_results.md`を参照する。

## ライセンスと制約

このカードはデータの来歴を記録するものであり、データセット全体について第三者権利が存在しないことを保証しない。Qwen3のApache License 2.0だけを根拠に、教師生成文や最終データ全体の権利状態を断定しない。公開・再配布前には利用目的と法域に応じた確認が必要である。
