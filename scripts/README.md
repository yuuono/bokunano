# scriptsディレクトリ

## uv仮想環境

すべてのPythonスクリプトはリポジトリ直下のuv仮想環境`.venv`で実行する。初回は用途に応じて次のどちらかを実行する。

```bash
uv sync --python 3.12.12
uv sync --python 3.12.12 --group instruction-generation
```

以降はシステムの`python`や`python3`を直接使わず、`uv run --python 3.12.12 python ...`を使う。`uv run`は`.venv/bin/python3`を自動的に選ぶため、手動activateは不要である。

## Pythonソースのコメント

初学者が処理を上から追えるよう、リポジトリ内のPythonソースは各論理処理行の直前、または同じ行に日本語の説明コメントを置く。空行、docstring、括弧だけの行は対象外とし、追加・変更時に差分を人が確認する。

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
- `dictionary`: この確認段階では空欄とし、後の人手選定結果から一括付与
- `reviewer`: 確認者名
- `reviewed_at`: 確認日時

確認後、承認済み表現辞書を作成する。

```bash
uv run --python 3.12.12 python scripts/instruction_generation/build_approved_expression_dictionary.py \
  --config config/build_approved_expression_dictionary.json \
  --overwrite
```

この処理は公開済みの承認表現545件を読み、人手選定IDで`train=522件`、`test_only=23件`へ分ける。分割は自動抽出や乱数ではなく、設定JSONへ固定した23件を使う。出力JSONLには公開表現に加えて元の生成レコードも保持する。詳しい選定内容は[`japanese_paraphrase_test_policy.md`](../docs/policies/japanese_paraphrase_test_policy.md)に記録する。

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

分割済みの承認表現辞書と5集合の意味ASTから、全文日本語指示をルール生成する。

```bash
uv run --python 3.12.12 python \
  scripts/instruction_generation/generate_rule_instructions.py \
  --config config/rule_generated_instruction_generation.json \
  --overwrite
```

生JSONLは`data/instructions/rule_generated_instructions.jsonl`へ出力し、同じ実行でGit管理用のtrain ZIPと評価ZIPを作る。選択・結合・重複除外方針は[`rule_generated_instruction_policy.md`](../docs/policies/rule_generated_instruction_policy.md)に従う。

ルール生成指示が完成した後、その一部について教師言い換え候補を作る。

対象は`split=train`かつ`dictionary=train`に限定し、訓練用9,646意味ASTのそれぞれから固定seedによるランダム順位で10指示ずつ、合計96,460件を選ぶ。元文1件につき候補1件を`temperature=0.9`で生成し、人手確認前には採用しない。実行は設定JSONの`batch_size=96`で行い、候補JSONLと生応答JSONLを生成済みレコードごとに逐次保存する。

```bash
uv run --group instruction-generation --python 3.12.12 python scripts/instruction_generation/generate_instruction_paraphrase_candidates.py \
  --config config/qwen_instruction_paraphrase_generation.json \
  --model-path /absolute/path/to/Qwen3-4B-AWQ
```

Qwen3はすべて`enable_thinking=false`、`local_files_only=true`で実行する。`model_path`にはローカル重みの絶対パス、`revision`にはその重みを取得した版の40桁のコミットIDを指定する。モデルが返した生出力、読込パス、解決済みrevision、プロンプトハッシュ、sampling設定、seedも生成物と一緒に保存する。ただし、`<think>`または`</think>`タグを含む応答は保存前に全体を拒否する。

実行結果は[`instruction_paraphrase_generation_results.md`](../docs/results/instruction_paraphrase_generation_results.md)に記録する。候補JSONL、生応答JSONL、確認CSVは人手承認前の作業物なのでGitへ追加せず、集計JSONと結果MDだけを管理する。

候補をすべて一括承認する場合は、誤操作防止の`--approve-all`、承認者、タイムゾーン付き承認日時、期待件数を明示する。元候補の全項目を保持した承認済みJSONL、Git管理用の決定的ZIP、集計JSONを同時に作る。

```bash
uv run --python 3.12.12 python scripts/instruction_generation/prepare_approved_teacher_paraphrases.py \
  --candidate-jsonl data/instructions/teacher_paraphrase_candidates.jsonl \
  --output-jsonl data/instructions/approved_teacher_paraphrases.jsonl \
  --archive data/archives/approved_teacher_paraphrases_2026-09-24.zip \
  --stats data/instructions/approved_teacher_paraphrases_stats.json \
  --reviewer ono_yusuke \
  --approved-at 2026-09-24T20:51:52+09:00 \
  --expected-count 96390 \
  --approve-all
```

一括承認では`review_status=approved`へ更新し、元の`pending`は`candidate_review_status`へ保存する。さらに`approved_by`、`approved_at`、`approval_mode=blanket_all_candidates`を追加する。結果は[`instruction_paraphrase_approval_results.md`](../docs/results/instruction_paraphrase_approval_results.md)に記録する。

教師言い換えを元のルール生成指示への一対一置換として扱い、検証済みコードとの結合前分布を確認する場合は次を実行する。

```bash
uv run --python 3.12.12 python scripts/instruction_generation/report_pre_join_distribution.py \
  --rule-instructions data/instructions/rule_generated_instructions.jsonl \
  --approved-paraphrases data/instructions/approved_teacher_paraphrases.jsonl \
  --paraphrase-generation-stats data/instructions/teacher_paraphrase_generation_stats.json \
  --single-operation-codes data/code_candidates/single_operation/python_code_candidates.jsonl \
  --multi-operation-code-archive data/archives/multi_operation_python_code_candidates_2026-09-20.zip \
  --output-json data/instructions/pre_join_distribution_stats.json \
  --output-md docs/results/pre_join_distribution_report.md \
  --output-by-ast-jsonl data/instructions/pre_join_distribution_by_ast.jsonl \
  --report-date 2026-09-25
```

この検査では、承認済み言い換えの`source_instruction_id`、`spec_id`、意味ASTを元指示と照合し、教師生成に失敗した70件を元文維持として数える。さらに、単一・2・3操作の検証済みコードを照合し、意味ASTごとの置換後指示数とコード数を報告する。20指示未満だった単一操作6種類については、2操作・3操作を含む全訓練指示のうち、その操作を含む意味AST数、指示文数、操作出現回数も集計する。`pre_join_distribution_by_ast.jsonl`には、全9,646意味ASTの指示数、教師置換成功数、失敗数、コード数を一件ずつ保存する。

承認済み教師言い換えを実際の訓練指示へ一対一で置換反映する場合は、次を実行する。元のルール生成指示と承認済み教師言い換えは読み取り専用入力として扱い、別の置換済みJSONLを作る。

```bash
uv run --python 3.12.12 python \
  scripts/instruction_generation/build_replacement_resolved_train_instructions.py \
  --rule-instructions data/instructions/rule_generated_instructions.jsonl \
  --approved-paraphrases data/instructions/approved_teacher_paraphrases.jsonl \
  --paraphrase-generation-stats data/instructions/teacher_paraphrase_generation_stats.json \
  --output-jsonl data/instructions/replacement_resolved_train_instructions.jsonl \
  --archive data/archives/replacement_resolved_train_instructions_2026-09-25.zip \
  --stats data/instructions/replacement_resolved_train_instruction_stats.json \
  --expected-output-count 192900 \
  --expected-replacement-count 96390
```

置換成功レコードには、元の`source_instruction_id`、`source_instruction_ja`、`source_text_hash`、表現ID、文テンプレートID、ルール生成条件と、教師モデル・prompt・sampling・承認来歴の両方を保存する。教師生成に失敗した70件と非選抜96,440件は元文を変更せず維持し、理由を`retention_reason`へ保存する。結果は[`replacement_resolved_train_instruction_results.md`](../docs/results/replacement_resolved_train_instruction_results.md)に記録する。

### 置換反映済み指示と検証済みコードの最終結合

```bash
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
  --pairing-seed 20260925
```

全9,646意味ASTを`spec_id`と正規化意味ASTで照合し、指示とコードを直積にせず一対一結合する。指示不足の6意味ASTではコード形式を均等化する決定的選抜を行い、余ったコードは元JSONL情報を保持した`rejected_train_code_candidates.jsonl`へ分離する。最終レコードはコード生成時の41検証入力を共有テスト集合IDで参照し、元の指示来歴とコード来歴を両方保存する。

最終JSONLを格納するZIPは、全来歴を保持したままGitHubの単一ファイル上限内へ収め、一般的な`unzip`でも扱えるよう、BZIP2方式で決定的に圧縮する。

### 評価入力6集合の生成

```bash
uv run --python 3.12.12 python \
  scripts/validation/generate_evaluation_input_sets.py \
  --config config/evaluation_input_generation.json
```

validation用build入力64件、normal・compositional・paraphrase・repetition用の相互に分離したhidden入力各64件、boundary共通30件と抽出AST固有ケースを作る。訓練コード検証の41入力との完全一致を除外し、全対象意味ASTを参照インタプリタで実行して、入力不変と整数リスト出力を確認する。詳細は[`evaluation_input_policy.md`](../docs/policies/evaluation_input_policy.md)に記録する。

2026年9月25日の実行件数、成果物SHA-256、filter全不合格へ到達不能な12 ASTは、[`evaluation_input_generation_results.md`](../docs/results/evaluation_input_generation_results.md)に記録する。

## 検証

```bash
uv run --python 3.12.12 python scripts/validation/verify_reference_interpreter.py
uv run --python 3.12.12 python scripts/validation/verify_multi_operation_code_candidates.py
```
