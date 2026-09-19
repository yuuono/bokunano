# dataディレクトリ

生成段階ごとにデータを分ける。

```text
data/
├── semantic_asts/                  # Pythonコード生成前の意味AST
└── code_candidates/
    ├── atomic_preview/             # 24操作を1件ずつ生成した予備確認
    └── single_operation/           # 24操作を20件ずつ生成した結果
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

日本語指示を結合した最終データは、作成時に`data/final/`へ保存する。
