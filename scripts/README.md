# scriptsディレクトリ

```text
scripts/
├── semantic_asts/    # 意味ASTの生成、抽出、分割
├── code_generation/  # Pythonコード候補の生成と結果文書の作成
├── instruction_generation/ # Qwen3による日本語候補生成と承認済み辞書作成
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

## 日本語指示生成

Qwen3を読み込まず、単純操作表現の設定と24操作の対応だけを確認する。

```bash
uv run python scripts/instruction_generation/generate_atomic_expression_candidates.py \
  --config config/qwen_atomic_expression_generation.json \
  --validate-config
```

CUDA対応環境で`Qwen/Qwen3-4B-AWQ`を読み込み、各操作20件の候補と確認用CSVを生成する。スクリプト内の依存関係定義を使うため、`python`を間に入れずに実行する。

```bash
uv run scripts/instruction_generation/generate_atomic_expression_candidates.py \
  --config config/qwen_atomic_expression_generation.json
```

生成された`data/instruction_dictionaries/expression_review.csv`を開き、次の列を記入する。

- `review_status`: 使用する表現は`approved`、使用しない表現は`unused`
- `edited_expression_ja`: 表現を直す場合だけ記入
- `dictionary`: `train`または`test_only`
- `reviewer`: 確認者名
- `reviewed_at`: 確認日時

確認後、承認済み表現辞書を作成する。

```bash
uv run python scripts/instruction_generation/build_approved_expression_dictionary.py \
  --config config/build_approved_expression_dictionary.json
```

ルール生成指示が完成した後、その一部について教師言い換え候補を作る。

```bash
uv run scripts/instruction_generation/generate_instruction_paraphrase_candidates.py \
  --config config/qwen_instruction_paraphrase_generation.json
```

Qwen3はすべて`enable_thinking=false`で実行する。モデルの`revision`には`main`ではなく40桁のコミットIDを指定する。モデルが返した生出力、解決済みrevision、プロンプトハッシュ、sampling設定、seedも生成物と一緒に保存する。ただし、`<think>`または`</think>`タグを含む応答は保存前に全体を拒否する。

## 検証

```bash
uv run python scripts/validation/verify_reference_interpreter.py
uv run python scripts/validation/verify_multi_operation_code_candidates.py
```
