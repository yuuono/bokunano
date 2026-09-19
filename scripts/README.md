# scriptsディレクトリ

```text
scripts/
├── semantic_asts/    # 意味ASTの生成、抽出、分割
├── code_generation/  # Pythonコード候補の生成と結果文書の作成
└── validation/       # 参照インタプリタの検証
```

## 意味AST

1. `semantic_asts/generate_combined_semantic_asts.py`
2. `semantic_asts/extract_compositional_semantic_asts.py`
3. `semantic_asts/generate_repetition_semantic_asts.py`
4. `semantic_asts/split_semantic_asts.py`

## Pythonコード生成

正式な単一操作コード候補は、リポジトリのルートで次を実行して生成する。

```bash
uv run python scripts/code_generation/generate_python_code_candidates.py \
  --config config/python_code_generation.json
```

設定だけを検査する場合は`--validate-config`を追加する。

## 検証

```bash
uv run python scripts/validation/verify_reference_interpreter.py
uv run python scripts/validation/verify_multi_operation_code_candidates.py
```
