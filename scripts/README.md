# scriptsディレクトリ

## uv仮想環境

すべてのPythonスクリプトはリポジトリ直下のuv仮想環境`.venv`で実行する。初回は用途に応じて次のどちらかを実行する。

```bash
uv sync --python 3.12.12
uv sync --python 3.12.12 --group instruction-generation
```

以降はシステムの`python`や`python3`を直接使わず、`uv run --python 3.12.12 python ...`を使う。`uv run`は`.venv/bin/python3`を自動的に選ぶため、手動activateは不要である。

## Pythonソースのコメント

初学者が処理を上から追えるよう、リポジトリ内のPythonソースは各論理処理行の直前、または同じ行に日本語の説明コメントを置く。空行、docstring、括弧だけの行は対象外とする。新しい処理を追加した後は次を実行し、未コメント行がないことを確認する。

```bash
uv run --python 3.12.12 python \
  scripts/validation/ensure_python_line_comments.py
```

既存コードへコメントを機械補完する必要がある場合だけ`--write`を指定する。補完後は内容に合う説明になっているか差分を読み、Ruffと単体テストを再実行する。

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
uv run --python 3.12.12 python scripts/code_generation/generate_python_code_candidates.py \
  --config config/python_code_generation.json
```

設定だけを検査する場合は`--validate-config`を追加する。

## 日本語指示生成

Qwen3を読み込まず、単純操作表現の設定と24操作の対応だけを確認する。

```bash
uv run --group instruction-generation --python 3.12.12 python scripts/instruction_generation/generate_atomic_expression_candidates.py \
  --config config/qwen_atomic_expression_generation.json \
  --validate-config
```

CUDA対応環境で`/home/ono_yusuke/Qwen3-4B-AWQ`のローカル重みを読み込み、各操作30件の候補と確認用CSVを生成する。Hubからは取得せず、`model_id`は生成物の出典表示、`model_path`は実際の読込元として使う。RTX 5090用のTritonコンパイルにPythonヘッダーが必要なため、`.python-version`でuv管理Python 3.12.12を固定している。

生成環境は`pyproject.toml`の`instruction-generation` dependency groupと`uv.lock`に記録している。初回は`uv sync --group instruction-generation`で復元する。RTX 5090で実行した`accelerate==1.15.0`、`torch==2.13.0`、`transformers==4.51.3`、`autoawq==0.2.9`を直接依存として固定している。システムPython 3.12.3はTritonが必要とする`Python.h`を持たないため、本生成には使用しない。

```bash
uv run --group instruction-generation --python 3.12.12 python scripts/instruction_generation/generate_atomic_expression_candidates.py \
  --config config/qwen_atomic_expression_generation.json \
  --model-path /absolute/path/to/Qwen3-4B-AWQ
```

`--model-path`には、同じrevisionのQwen3-4B-AWQをclone先で配置した絶対パスを指定する。設定JSON自体を書き換える必要はない。同じ出力先へ再生成する場合だけ`--overwrite`を追加する。現在の設定は各操作最大20試行で、再試行時も終止形・接続形の組を30件生成させ、既存候補と重複しない不足分だけを採用する。30件は最終的に各操作20件以上を人間承認するための候補母数である。目標未達の操作だけを既存候補へ補充する場合は`--resume`を使う。今回の実行だけ最大試行回数を変える場合は`--max-attempts-per-operation`を指定する。複数の操作へ絞る場合は`--operation-id`を操作ごとに繰り返す。

既存の確認CSVにある同一操作の表現を避けて新規候補を生成する場合は、`--existing-review-csv`を指定する。CSV内の既存例は設定した新規候補の目標件数には数えない。標準設定は30件で、特定操作の追加生成設定では最大100件まで指定できる。次の専用設定は新規50件を生成する。

```bash
uv run --group instruction-generation --python 3.12.12 python scripts/instruction_generation/generate_atomic_expression_candidates.py \
  --config config/qwen_atomic_expression_generation_every_other.json \
  --operation-id atomic-000024 \
  --existing-review-csv data/instruction_dictionaries/expression_review_approved_v2.csv \
  --overwrite
```

生成された`data/instruction_dictionaries/expression_review.csv`を開き、次の列を記入する。

- `review_status`: 使用する表現は`approved`、使用しない表現は`unused`
- `edited_expression_ja`: 終止形を直す場合だけ記入
- `edited_connective_expression_ja`: 接続形を直す場合だけ記入
- `dictionary`: `train`または`test_only`
- `reviewer`: 確認者名
- `reviewed_at`: 確認日時

確認後、承認済み表現辞書を作成する。

```bash
uv run --python 3.12.12 python scripts/instruction_generation/build_approved_expression_dictionary.py \
  --config config/build_approved_expression_dictionary.json
```

承認済みマスターから`unused`を除き、GitHub公開用の最終CSVと来歴JSONLを作る。

```bash
uv run --python 3.12.12 python \
  scripts/instruction_generation/prepare_approved_expression_release.py \
  --review-csv data/instruction_dictionaries/expression_review_approved_v2.csv \
  --candidate-jsonl data/instruction_dictionaries/expression_review_approved_v2_candidates.jsonl \
  --release-directory data/instruction_dictionaries/release \
  --prune-unused
```

公開対象とcommit・push時の確認事項は、[`publishing_japanese_expression_dictionary.md`](../docs/procedures/publishing_japanese_expression_dictionary.md)に従う。

ルール生成指示が完成した後、その一部について教師言い換え候補を作る。

```bash
uv run --group instruction-generation --python 3.12.12 python scripts/instruction_generation/generate_instruction_paraphrase_candidates.py \
  --config config/qwen_instruction_paraphrase_generation.json \
  --model-path /absolute/path/to/Qwen3-4B-AWQ
```

Qwen3はすべて`enable_thinking=false`、`local_files_only=true`で実行する。`model_path`にはローカル重みの絶対パス、`revision`にはその重みを取得した版の40桁のコミットIDを指定する。モデルが返した生出力、読込パス、解決済みrevision、プロンプトハッシュ、sampling設定、seedも生成物と一緒に保存する。ただし、`<think>`または`</think>`タグを含む応答は保存前に全体を拒否する。

## 検証

```bash
uv run --python 3.12.12 python scripts/validation/verify_reference_interpreter.py
uv run --python 3.12.12 python scripts/validation/verify_multi_operation_code_candidates.py
uv run --python 3.12.12 python scripts/validation/ensure_python_line_comments.py
```
