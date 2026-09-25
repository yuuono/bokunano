# dataディレクトリ

生成段階ごとにデータを分ける。

```text
data/
├── semantic_asts/                  # Pythonコード生成前の意味AST
├── instructions/                   # 日本語指示の生成物と集計
├── final/                          # 最終訓練レコードの集計、テスト参照、不採用コード
├── evaluation_inputs/              # validation・hidden・boundaryの評価入力
├── archives/                       # Git管理する大容量JSONLのZIP
└── code_candidates/
    ├── atomic_preview/             # 24操作を1件ずつ生成した予備確認
    ├── single_operation/           # 訓練用の1操作を20件ずつ生成した結果
    ├── train/
    │   ├── two_operation/          # 訓練用の2操作を20件ずつ生成した結果
    │   └── three_operation/        # 訓練用の3操作を20件ずつ生成した結果
    ├── compositional/              # 組合せ汎化用の2・3操作
    ├── validation/                 # 検証用の2・3操作
    ├── normal/                     # 通常テスト用の2・3操作
    └── repetition/                 # 反復汎化用の2・3操作
```

## `semantic_asts`

| ファイル | 内容 |
|---|---|
| `atomic_semantic_asts.jsonl` | 24種類の単独操作 |
| `combined_semantic_asts.jsonl` | 重複操作なしの1〜3操作AST 12,720件 |
| `compositional_semantic_asts.jsonl` | 組合せ汎化テスト用670件 |
| `repetition_semantic_asts.jsonl` | 反復汎化テスト用1,152件 |
| `train_semantic_asts.jsonl` | 訓練用意味AST |
| `val_semantic_asts.jsonl` | 検証用意味AST |
| `normal_semantic_asts.jsonl` | 通常テスト用意味AST |

## `code_candidates`

各サブディレクトリに、採用コードのJSONL、不採用記録、実行設定と件数の集計JSONをまとめる。

2操作・3操作の件数、参照インタプリタとの照合、完全重複の確認結果は、[`docs/results/multi_operation_python_code_generation_results.md`](../docs/results/multi_operation_python_code_generation_results.md)に記録する。

検証、通常テスト、反復汎化の生成結果は、[`docs/results/evaluation_python_code_generation_results.md`](../docs/results/evaluation_python_code_generation_results.md)に記録する。

日本語指示を結合した最終データは、作成時に`data/final/`へ保存する。

## 大容量生成物のZIP

2・3操作の`python_code_candidates.jsonl`と展開済み全文指示JSONLは容量が大きいため、Gitでは直接管理しない。Gitでは次のZIPを管理する。

| ファイル | 対象 | 収録ファイル | 収録コード | SHA-256 |
|---|---|---:|---:|---|
| `archives/multi_operation_python_code_candidates_2026-09-20.zip` | 訓練・組合せ汎化 | 4 | 205,840件 | `369fb2175c715f15c6c7aeccd6d3ce96191404dac4537da8d72774e52d862a8e` |
| `archives/evaluation_python_code_candidates_2026-09-20.zip` | 検証・通常テスト・反復汎化 | 6 | 71,120件 | `5fcab861bcc6d69fb12758fb62325e02a00ab00e5da55db25c7b2e03134821d4` |
| `archives/rule_generated_train_instructions_2026-09-24.zip` | trainの全文日本語指示 | 1 | 192,900件 | `6299f0c09b0fcbe095d1537a55dc9f4f0fa5dd815f5ba01f0fd75e7c9a871d24` |
| `archives/rule_generated_evaluation_instructions_2026-09-24.zip` | validation・normal・compositional・repetitionの全文日本語指示 | 1 | 84,520件 | `1a9e25807c2921359f308fb4951faabf13c9fbb9fbd1f0e5e7019f8be6f6ed3b` |
| `archives/replacement_resolved_train_instructions_2026-09-25.zip` | 教師言い換えを一対一置換したtrain指示 | 1 | 192,900件 | `7a90b24796e7ef2ad9d9510168e734df7556b18faa092a00f81466f96a9818c2` |
| `archives/final_train_dataset_records_2026-09-25.zip` | 日本語指示と検証済みコードを一対一結合した最終trainレコード | 1 | 192,900件 | `799e6dd8be7e80e48df69fed4f70f5922f7a215a8669cf0f523f3de59ae91807` |

設定JSON、集計JSON、不採用記録、共有テスト集合、生成・検証スクリプトはZIPへ入れず、通常のファイルとしてGitで管理する。最終訓練ZIPはBZIP2方式で圧縮している。

リポジトリのルートで次を実行すると、各JSONLを元の保存先へ展開できる。

```bash
unzip data/archives/multi_operation_python_code_candidates_2026-09-20.zip -d .
unzip data/archives/evaluation_python_code_candidates_2026-09-20.zip -d .
unzip data/archives/rule_generated_train_instructions_2026-09-24.zip -d .
unzip data/archives/rule_generated_evaluation_instructions_2026-09-24.zip -d .
unzip data/archives/replacement_resolved_train_instructions_2026-09-25.zip -d data/instructions/
mkdir -p data/final
unzip data/archives/final_train_dataset_records_2026-09-25.zip -d data/final/
```

展開後は次で、件数、保存済み検証結果、コード全文の完全重複を再確認できる。

```bash
uv run --python 3.12.12 python scripts/validation/verify_multi_operation_code_candidates.py
```
