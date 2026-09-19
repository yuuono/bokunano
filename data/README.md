# dataディレクトリ

生成段階ごとにデータを分ける。

```text
data/
├── semantic_asts/                  # Pythonコード生成前の意味AST
└── code_candidates/
    ├── atomic_preview/             # 24操作を1件ずつ生成した予備確認
    ├── single_operation/           # 訓練用の1操作を20件ずつ生成した結果
    ├── train/
    │   ├── two_operation/          # 訓練用の2操作を20件ずつ生成した結果
    │   └── three_operation/        # 訓練用の3操作を20件ずつ生成した結果
    └── compositional/
        ├── two_operation/          # 組合せ汎化用の2操作を20件ずつ生成した結果
        └── three_operation/        # 組合せ汎化用の3操作を20件ずつ生成した結果
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

日本語指示を結合した最終データは、作成時に`data/final/`へ保存する。

## 2操作・3操作コード候補のZIP

4つの`python_code_candidates.jsonl`は合計約358 MBになるため、展開済みファイルをGitでは管理しない。Gitでは次のZIPを管理する。

| ファイル | 収録コード | SHA-256 |
|---|---:|---|
| `archives/multi_operation_python_code_candidates_2026-09-20.zip` | 205,840件 | `369fb2175c715f15c6c7aeccd6d3ce96191404dac4537da8d72774e52d862a8e` |

ZIPには、訓練用と組合せ汎化テスト用の2操作・3操作コード候補JSONLを4ファイル収録している。設定JSON、集計JSON、不採用記録、生成・検証スクリプトはZIPへ入れず、通常のファイルとしてGitで管理する。

リポジトリのルートで次を実行すると、4ファイルを元の保存先へ展開できる。

```bash
unzip data/archives/multi_operation_python_code_candidates_2026-09-20.zip -d .
```

展開後は次で、件数、保存済み検証結果、コード全文の完全重複を再確認できる。

```bash
uv run python scripts/validation/verify_multi_operation_code_candidates.py
```
