# Boku Nano データ生成から評価までの再実行手順

## 目的

この手順は、クリーンな取得状態からデータを組み立て、トークナイザと学生モデルを学習し、5種類のテストと学習前後比較までを一つの順序で再実行するためのものである。

標準手順では、Git管理済みの表現辞書、検証済みコード候補ZIP、教師言い換えZIPを固定入力として使う。新たな人手承認は行わない。教師出力から後続データを作り直す場合も、形式検査を通過した候補を機械的に一括採用する。

教師モデルから言い換え自体を再生成する場合は、Hugging Faceから固定revisionを取得する。教師モデルはデータ生成時だけ使用し、学生モデルの学習・推論・評価には読み込まない。

## 前提

- リポジトリのルートで実行する。
- Python 3.12.12と`uv`を使用する。
- 学生モデルの学習と評価にはCUDA対応GPUを使用する。
- 教師言い換えを再生成する場合だけ、Hugging Faceへ接続できる環境と教師モデル用GPUが必要になる。
- 既存成果物を上書きするため、作業用の新しいcloneまたはworktreeで実行する。

## 1. 実行環境を復元する

~~~bash
uv sync --python 3.12.12
uv sync --python 3.12.12 --group instruction-generation
uv sync --python 3.12.12 --group tokenizer-training
uv sync --python 3.12.12 --group model-training
~~~

実行版は`pyproject.toml`と`uv.lock`で固定する。

## 2. 意味ASTと表現辞書を再生成する

意味ASTを決定的に再生成し、Git管理済みの最終表現CSVと来歴JSONLから使用辞書を作る。この工程に新しい人手判定はない。

~~~bash
uv run --python 3.12.12 python scripts/semantic_asts/generate_combined_semantic_asts.py
uv run --python 3.12.12 python scripts/semantic_asts/extract_compositional_semantic_asts.py
uv run --python 3.12.12 python scripts/semantic_asts/generate_repetition_semantic_asts.py
uv run --python 3.12.12 python scripts/semantic_asts/split_semantic_asts.py

uv run --python 3.12.12 python \
  scripts/instruction_generation/build_approved_expression_dictionary.py \
  --config config/build_approved_expression_dictionary.json \
  --overwrite
~~~

期待件数は、訓練9,646 AST、検証1,202 AST、通常テスト1,202 AST、組合せ汎化670 AST、反復1,152 ASTである。

## 3. コード候補を復元して漏洩を検査する

検証済みコード候補は大容量のため、GitではZIPを正本として管理している。

~~~bash
unzip -o data/archives/multi_operation_python_code_candidates_2026-09-20.zip -d .
unzip -o data/archives/evaluation_python_code_candidates_2026-09-20.zip -d .

uv run --python 3.12.12 python \
  scripts/validation/verify_reference_interpreter.py

uv run --python 3.12.12 python \
  scripts/validation/verify_multi_operation_code_candidates.py
~~~

検査では、全277,440コード候補の集合内完全重複と、5集合間10通りの完全一致が0件であることを確認する。

## 4. 日本語指示を再生成する

固定済み辞書と意味ASTから、訓練・検証・各テスト用の日本語指示を生成する。

~~~bash
uv run --python 3.12.12 python \
  scripts/instruction_generation/generate_rule_instructions.py \
  --config config/rule_generated_instruction_generation.json \
  --overwrite

uv run --python 3.12.12 python \
  scripts/instruction_generation/generate_paraphrase_test_instructions.py \
  --config config/paraphrase_test_instruction_generation.json \
  --overwrite
~~~

標準手順では、固定済みの教師言い換えZIPを展開する。ここでも人手承認は不要である。

~~~bash
unzip -o data/archives/approved_teacher_paraphrases_2026-09-24.zip \
  -d data/instructions/
~~~

## 5. 必要な場合だけ教師言い換えを再生成する

前節の固定ZIPを使う場合、この節は省略する。教師出力から作り直す場合は、Hugging FaceからモデルIDとrevisionを固定して取得する。

~~~bash
BOKUNANO_TEACHER_DIR=/absolute/path/to/Qwen3-4B-AWQ

uv run --group instruction-generation hf download \
  Qwen/Qwen3-4B-AWQ \
  --revision 74d4bd2bd4bff9cafc9345221320bffb08b406a3 \
  --local-dir "$BOKUNANO_TEACHER_DIR"

uv run --group instruction-generation --python 3.12.12 python \
  scripts/instruction_generation/generate_instruction_paraphrase_candidates.py \
  --config config/qwen_instruction_paraphrase_generation.json \
  --model-path "$BOKUNANO_TEACHER_DIR" \
  --overwrite
~~~

形式検査を通過した候補は、個別の人手判定を挟まず機械的に一括採用する。既存スクリプトの`reviewer`、`approved_at`、`review_status`は来歴schema上の項目であり、この再実行手順では人手承認を意味しない。

~~~bash
uv run --python 3.12.12 python \
  scripts/instruction_generation/prepare_approved_teacher_paraphrases.py \
  --candidate-jsonl data/instructions/teacher_paraphrase_candidates.jsonl \
  --output-jsonl data/instructions/approved_teacher_paraphrases.jsonl \
  --archive data/archives/approved_teacher_paraphrases_2026-09-24.zip \
  --stats data/instructions/approved_teacher_paraphrases_stats.json \
  --reviewer automated_pipeline \
  --approved-at 2026-09-24T20:51:52+09:00 \
  --expected-count 96390 \
  --approve-all \
  --overwrite
~~~

## 6. 最終訓練・評価データを組み立てる

教師言い換えをルール生成文へ一対一で反映し、検証済みコードと結合する。

~~~bash
uv run --python 3.12.12 python \
  scripts/instruction_generation/build_replacement_resolved_train_instructions.py \
  --rule-instructions data/instructions/rule_generated_instructions.jsonl \
  --approved-paraphrases data/instructions/approved_teacher_paraphrases.jsonl \
  --paraphrase-generation-stats data/instructions/teacher_paraphrase_generation_stats.json \
  --output-jsonl data/instructions/replacement_resolved_train_instructions.jsonl \
  --archive data/archives/replacement_resolved_train_instructions_2026-09-25.zip \
  --stats data/instructions/replacement_resolved_train_instruction_stats.json \
  --expected-output-count 192900 \
  --expected-replacement-count 96390 \
  --overwrite

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
~~~

評価入力と最終評価レコードを作る。

~~~bash
uv run --python 3.12.12 python \
  scripts/validation/generate_evaluation_input_sets.py \
  --config config/evaluation_input_generation.json \
  --overwrite

uv run --python 3.12.12 python \
  scripts/instruction_generation/build_final_evaluation_records.py \
  --evaluation-instructions-archive data/archives/rule_generated_evaluation_instructions_2026-09-24.zip \
  --paraphrase-instructions-archive data/archives/paraphrase_test_instructions_2026-09-24.zip \
  --evaluation-code-archive data/archives/evaluation_python_code_candidates_2026-09-20.zip \
  --multi-operation-code-archive data/archives/multi_operation_python_code_candidates_2026-09-20.zip \
  --single-operation-codes data/code_candidates/single_operation/python_code_candidates.jsonl \
  --evaluation-input-stats data/evaluation_inputs/evaluation_input_stats.json \
  --output-dir data/final/evaluation \
  --archive data/archives/final_evaluation_dataset_records_2026-09-25.zip \
  --stats data/final/final_evaluation_dataset_stats.json \
  --expected-record-count 108590 \
  --pairing-seed 20260925 \
  --overwrite
~~~

## 7. トークナイザを新規学習する

評価データや事前学習済み語彙を使わず、最終訓練データ192,900件だけからBPE 2,048語彙を作る。

~~~bash
uv run --group tokenizer-training --python 3.12.12 python \
  scripts/tokenizer/train_tokenizer.py \
  --config config/tokenizer_bpe_2048.yaml \
  --overwrite
~~~

期待するtokenizer SHA-256は`6840a392e8fcae1083be06842774fa912a1797217c7033944ba2d87f1c227293`である。

## 8. 学生モデルをランダム初期値から学習する

既存のモデル重みは読み込まず、seed `20260925`で15,735,168 parameterを初期化して3エポック学習する。

~~~bash
uv run --group model-training --python 3.12.12 python \
  scripts/model/train_boku_nano.py \
  --config config/boku_nano_bpe_2048.yaml \
  --overwrite
~~~

1エポックは訓練系列6,939,466 tokenで、loss対象はコードとEOSの3,746,067 tokenである。

## 9. 5テストと学習前後比較を実行する

~~~bash
uv run --group model-training --python 3.12.12 python \
  scripts/model/evaluate_boku_nano.py \
  --config config/boku_nano_evaluation.yaml \
  --overwrite

uv run --group model-training --python 3.12.12 python \
  scripts/model/evaluate_boku_nano_comparison.py \
  --config config/boku_nano_comparison_evaluation.yaml \
  --overwrite
~~~

正式評価は通常、組合せ汎化、日本語言い換え、同一操作の反復、境界値の5集合、合計84,550問である。比較評価は固定430問で、学習前ランダムモデルと3エポックモデルのpass@1・pass@5を比較する。

## 10. 完了確認

次をすべて確認できれば再実行完了とする。

- 訓練レコードが192,900件、評価レコードが108,590件である。
- tokenizerが訓練データだけから作成され、期待SHA-256と一致する。
- 学生モデルがランダム初期値から3エポック完了している。
- train lossとvalidation lossが3エポック分保存されている。
- 5テスト84,550問の評価結果が保存されている。
- 固定430問の学習前後比較が保存されている。
- 意味AST、コード、hidden入力の漏洩検査結果が保存されている。
- 教師モデルは学生モデルの推論・評価時に読み込まれていない。

GPU kernel差により学生モデル重みのbyte単位一致までは要求しない。データ件数、固定入力、設定、seed、tokenizer SHA-256、評価条件を再現基準とする。
