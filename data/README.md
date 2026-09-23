# dataディレクトリ

生成段階ごとにデータを分ける。

```text
data/
├── semantic_asts/                  # Pythonコード生成前の意味AST
├── instructions/                   # 日本語指示の生成物と集計
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

## コード候補のZIP

2操作・3操作の`python_code_candidates.jsonl`は容量が大きいため、展開済みファイルをGitでは管理しない。Gitでは次のZIPを管理する。

| ファイル | 対象 | 収録ファイル | 収録コード | SHA-256 |
|---|---|---:|---:|---|
| `archives/multi_operation_python_code_candidates_2026-09-20.zip` | 訓練・組合せ汎化 | 4 | 205,840件 | `369fb2175c715f15c6c7aeccd6d3ce96191404dac4537da8d72774e52d862a8e` |
| `archives/evaluation_python_code_candidates_2026-09-20.zip` | 検証・通常テスト・反復汎化 | 6 | 71,120件 | `5fcab861bcc6d69fb12758fb62325e02a00ab00e5da55db25c7b2e03134821d4` |
| `archives/rule_generated_instructions_2026-09-24.zip` | train・validation・normal・compositional・repetitionの全文日本語指示 | 1 | 277,420件 | `643ffab5dc0d2215ab7b6b9c3eccf328021b2a655644f8fcd6ee5afd9c056ac6` |

設定JSON、集計JSON、不採用記録、生成・検証スクリプトはZIPへ入れず、通常のファイルとしてGitで管理する。

リポジトリのルートで次を実行すると、各JSONLを元の保存先へ展開できる。

```bash
unzip data/archives/multi_operation_python_code_candidates_2026-09-20.zip -d .
unzip data/archives/evaluation_python_code_candidates_2026-09-20.zip -d .
unzip data/archives/rule_generated_instructions_2026-09-24.zip -d .
```

展開後は次で、件数、保存済み検証結果、コード全文の完全重複を再確認できる。

```bash
uv run --python 3.12.12 python scripts/validation/verify_multi_operation_code_candidates.py
```
