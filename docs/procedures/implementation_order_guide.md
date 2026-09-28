# Boku1-nano 実装順と文書の対応

## 目的

学生がBoku1-nanoをデータ生成からブラウザ推論まで順番に実装できるように、各工程で最初に読む文書、実行方法、実行済み結果の所在をまとめる。

一連の再実行コマンドは[`boku_nano_end_to_end_reproduction.md`](boku_nano_end_to_end_reproduction.md)にまとめている。本書は、その手順を学習順に読み解くための入口である。

## 実装順

| 順番 | 実装するもの | 最初に読む文書 | 実行方法・結果 |
| ---: | --- | --- | --- |
| 1 | 24種類の基本操作と意味AST | [`../specifications/atomic_semantic_asts.md`](../specifications/atomic_semantic_asts.md) | [`../../scripts/README.md`](../../scripts/README.md)の「意味AST」、[`../../data/README.md`](../../data/README.md)の「semantic_asts」 |
| 2 | 参照インタプリタ | [`../specifications/reference_interpreter.md`](../specifications/reference_interpreter.md) | 同文書の「実行確認」 |
| 3 | 正解Pythonコード生成 | [`../policies/python_code_generation_policy.md`](../policies/python_code_generation_policy.md) | [`../../scripts/README.md`](../../scripts/README.md)の「Pythonコード生成」、[`../results/single_operation_python_code_generation_results.md`](../results/single_operation_python_code_generation_results.md)、[`../results/multi_operation_python_code_generation_results.md`](../results/multi_operation_python_code_generation_results.md) |
| 4 | 生成コードの実行検証 | [`../policies/python_code_generation_policy.md`](../policies/python_code_generation_policy.md) | 参照インタプリタとの照合結果は、単独・複数操作の各コード生成結果に記録 |
| 5 | 日本語指示生成 | [`japanese_instruction_generation.md`](japanese_instruction_generation.md) | [`../policies/rule_generated_instruction_policy.md`](../policies/rule_generated_instruction_policy.md)、[`../results/rule_generated_instruction_results.md`](../results/rule_generated_instruction_results.md)、[`../results/final_train_dataset_results.md`](../results/final_train_dataset_results.md) |
| 6 | BPEトークナイザー | [`../policies/tokenizer_training_policy.md`](../policies/tokenizer_training_policy.md) | [`../../scripts/README.md`](../../scripts/README.md)の「トークナイザ訓練」、[`../results/bpe_tokenizer_training_results.md`](../results/bpe_tokenizer_training_results.md) |
| 7 | Decoder-only Transformer | [`../policies/boku_nano_training_policy.md`](../policies/boku_nano_training_policy.md)の「固定モデル仕様」 | [`../cards/MODEL_CARD.md`](../cards/MODEL_CARD.md)の「モデル構成」、[`../../scripts/README.md`](../../scripts/README.md)の「Boku-nano本学習」 |
| 8 | モデル学習 | [`../policies/boku_nano_training_policy.md`](../policies/boku_nano_training_policy.md) | [`../results/boku_nano_three_epoch_training_results.md`](../results/boku_nano_three_epoch_training_results.md) |
| 9 | hidden test評価 | [`../policies/boku_nano_model_evaluation_policy.md`](../policies/boku_nano_model_evaluation_policy.md) | [`../results/boku_nano_3epoch_evaluation_results.md`](../results/boku_nano_3epoch_evaluation_results.md)、[`../results/boku_nano_evaluation_metrics_and_random_baseline.md`](../results/boku_nano_evaluation_metrics_and_random_baseline.md) |
| 10 | ONNX変換とブラウザ推論 | [`boku_nano_onnx_web_demo.md`](boku_nano_onnx_web_demo.md) | 同文書の「ONNXの再生成」「実ブラウザ試験」「GitHub Pages公開」 |

## BPEトークナイザーの実装順

BPEトークナイザーの各工程は、[`../policies/tokenizer_training_policy.md`](../policies/tokenizer_training_policy.md)に次のように記載している。

| 順番 | 工程 | 記載箇所 |
| ---: | --- | --- |
| 1 | 学習コーパスを作る | 「学習入力」「コーパスの重複制御」 |
| 2 | ByteLevelで前処理する | 「共通前処理」 |
| 3 | 2,048語彙のBPEを学習する | 「語彙数と特殊トークン」「BPE設定」 |
| 4 | 特殊トークンとIDを固定する | 「語彙数と特殊トークン」 |
| 5 | unknownトークン、系列長、encode/decodeを検査する | 「必須検証」 |
| 6 | 設定、依存版、生成物のSHA-256を保存する | 「生成物」「必須検証」 |

実測値と検査結果は[`../results/bpe_tokenizer_training_results.md`](../results/bpe_tokenizer_training_results.md)に記録している。ここには、訓練データ192,900件だけを使用したこと、特殊トークン込みの語彙数が2,048であること、unknownトークンが0件であること、最大系列長が94 tokenであること、各成果物のSHA-256が含まれる。

## 文書の役割

- `specifications`: 何を実装するかを定義する。
- `policies`: データ漏洩を防ぎ、条件を揃えるための判断基準を定義する。
- `procedures`: 実行する順番とコマンドを示す。
- `results`: 実行済みの件数、loss、評価値、ハッシュを記録する。
- `cards`: 完成したデータセットとモデルの全体像、用途、制約、来歴を示す。

したがって、学生は本書を入口に仕様、方針、手順、結果の順で読み、最後に[`boku_nano_end_to_end_reproduction.md`](boku_nano_end_to_end_reproduction.md)を使って全工程を再実行する。
