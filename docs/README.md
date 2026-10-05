# 文書の案内

```text
docs/
├── cards/           # Dataset CardとModel Card
├── policies/        # データ分割、コード生成、選抜、評価の方針
├── procedures/      # データ生成作業の具体的な手順
├── report/          # 発表資料と説明用ファクト集
├── specifications/  # 意味ASTと参照インタプリタの仕様
└── results/         # 実行済みの生成・検証結果
```

## カード

- [`cards/DATASET_CARD.md`](cards/DATASET_CARD.md): 訓練・評価データの生成方法、教師モデル、来歴、長い一致検査
- [`cards/MODEL_CARD.md`](cards/MODEL_CARD.md): モデル構造、variant、用途、評価、制約、ライセンス来歴
- [`../THIRD_PARTY.md`](../THIRD_PARTY.md): 教師モデル、ブラウザランタイム、主要依存関係のライセンスと来歴

## 方針

- [`policies/boku_nano_benchmark_100_plan.md`](policies/boku_nano_benchmark_100_plan.md): 100問ベンチマークの分類、70点を目安とした難易度設計、ブラウザ版Qwenとの比較・採点・検証計画
- [`policies/boku_nano_chat_ui_plan.md`](policies/boku_nano_chat_ui_plan.md): チャット形式Web UIの画面、Qwenによる追加指示の処理、実装手順と完了条件
- [`policies/boku_nano_autoregression_temperature_plan.md`](policies/boku_nano_autoregression_temperature_plan.md): 実コードに基づく自己回帰・温度の説明と、発表資料へ追加する2枚の作成計画
- [`policies/terminology_policy.md`](policies/terminology_policy.md): 用語の統一
- [`policies/ast_split_policy.md`](policies/ast_split_policy.md): 意味ASTの分割
- [`policies/compositional_generalization_test_policy.md`](policies/compositional_generalization_test_policy.md): 組合せ汎化テスト
- [`policies/repetition_generalization_test_policy.md`](policies/repetition_generalization_test_policy.md): 反復汎化テスト
- [`policies/python_code_generation_policy.md`](policies/python_code_generation_policy.md): Pythonコード生成
- [`policies/code_duplicate_exclusion_policy.md`](policies/code_duplicate_exclusion_policy.md): 生成コードの完全重複除外
- [`policies/data_record_policy.md`](policies/data_record_policy.md): データレコードと選抜
- [`policies/japanese_paraphrase_test_policy.md`](policies/japanese_paraphrase_test_policy.md): 人手選定した未学習表現による日本語言い換えテスト
- [`policies/rule_generated_instruction_policy.md`](policies/rule_generated_instruction_policy.md): 承認済み表現と意味ASTから全文指示を決定的に作る方針
- [`policies/evaluation_input_policy.md`](policies/evaluation_input_policy.md): validation・hidden・boundary評価入力の生成と分離
- [`policies/tokenizer_training_policy.md`](policies/tokenizer_training_policy.md): 訓練データ限定のBPE・Unigram共通語彙作成と比較方針
- [`policies/boku_nano_training_policy.md`](policies/boku_nano_training_policy.md): BPE 2,048語彙と約1,600万parameterモデルによる3 epoch本学習方針
- [`policies/boku_nano_chinchilla_scaling.md`](policies/boku_nano_chinchilla_scaling.md): Chinchilla則に基づく5M・15M・35Mモデル構成と訓練token量の概算
- [`policies/boku_nano_model_evaluation_policy.md`](policies/boku_nano_model_evaluation_policy.md): 学習済みBoku Nanoの5種類の生成・実行評価方針
- [`policies/browser_cnl_normalization_policy.md`](policies/browser_cnl_normalization_policy.md): ブラウザ内Qwenによる自由文からCNLへの翻訳とJavaScript検査の方針

## 手順

- [`procedures/implementation_order_guide.md`](procedures/implementation_order_guide.md): 24種類の基本操作からONNXブラウザ推論までの実装順と各文書の対応
- [`procedures/japanese_instruction_generation.md`](procedures/japanese_instruction_generation.md): 日本語指示の候補生成、人間承認、ルール結合、教師言い換え
- [`procedures/publishing_japanese_expression_dictionary.md`](procedures/publishing_japanese_expression_dictionary.md): 最終表現CSVと生成来歴JSONLだけをGitHubへ公開する手順
- [`procedures/boku_nano_end_to_end_reproduction.md`](procedures/boku_nano_end_to_end_reproduction.md): 人手承認を挟まず、固定成果物またはHugging Face教師モデルからデータ生成・学習・評価まで再実行する手順
- [`procedures/boku_nano_onnx_web_demo.md`](procedures/boku_nano_onnx_web_demo.md): 1M・5M・15Mの学習済み8モデルのONNX変換、実ブラウザ試験、GitHub Pages公開手順

## 仕様

- [`specifications/atomic_semantic_asts.md`](specifications/atomic_semantic_asts.md): 24種類の単独操作
- [`specifications/reference_interpreter.md`](specifications/reference_interpreter.md): 参照インタプリタ

## 発表資料

- [`report/boku1_nano_presentation.md`](report/boku1_nano_presentation.md): Boku1-nanoの発表用ドキュメント
- [`report/boku1_nano_presentation_facts.md`](report/boku1_nano_presentation_facts.md): 発表内容の根拠と説明用ファクト集

## 結果

- [`results/browser_100/dev50_20261005_condition_a_failures.md`](results/browser_100/dev50_20261005_condition_a_failures.md): 条件Aで各モデルが不合格になった全40問、生成コード、実測反例、失敗原因

- [`results/browser_100/dev50_20261005_results.md`](results/browser_100/dev50_20261005_results.md): Astra作成の10分類×5問によるブラウザ版QwenとBokuの実測比較、分類別得点、失敗例
- [`results/browser_100/dev50_20261005_details.md`](results/browser_100/dev50_20261005_details.md): 全50問・条件A・Bの実プロンプト、生成コード、採点詳細

- [`results/atomic_python_code_generation_results.md`](results/atomic_python_code_generation_results.md): 各操作1件の予備確認
- [`results/single_operation_python_code_generation_results.md`](results/single_operation_python_code_generation_results.md): 各操作20件の生成結果
- [`results/multi_operation_python_code_generation_results.md`](results/multi_operation_python_code_generation_results.md): 2・3操作を各AST 20件生成した結果
- [`results/japanese_atomic_expression_generation_results.md`](results/japanese_atomic_expression_generation_results.md): Qwen3による24操作各30件の初回生成パラメータ、結果、人間確認で見つかった問題
- [`results/japanese_atomic_expression_expansion_history.md`](results/japanese_atomic_expression_expansion_history.md): 各操作20件以上を目指した追加生成、承認数の推移、生成履歴保存の経緯
- [`results/japanese_atomic_expression_split_results.md`](results/japanese_atomic_expression_split_results.md): 人手選定による545件のtrain・test_only分割結果
- [`results/rule_generated_instruction_results.md`](results/rule_generated_instruction_results.md): 13,872意味ASTから作成した277,420件の全文指示
- [`results/final_train_dataset_results.md`](results/final_train_dataset_results.md): 置換反映済み日本語指示192,900件と検証済みコードの最終結合結果
- [`results/evaluation_input_generation_results.md`](results/evaluation_input_generation_results.md): validation・hidden・boundary評価入力6集合の生成・検証結果
- [`results/final_evaluation_dataset_results.md`](results/final_evaluation_dataset_results.md): 6評価集合108,590件の最終結合・ZIP作成結果
- [`results/bpe_tokenizer_training_results.md`](results/bpe_tokenizer_training_results.md): 訓練データ限定BPE 2,048語彙候補の学習・全件検証結果
- [`results/bpe_tokenizer_minfreq2_maxlen8_results.md`](results/bpe_tokenizer_minfreq2_maxlen8_results.md): 最小頻度2・最大piece長8のBPE 2,048語彙と既存版の系列長比較
- [`results/bpe_tokenizer_implementation_examples.md`](results/bpe_tokenizer_implementation_examples.md): 長いpiece版と短いpiece版の設定、系列長、GPU使用量の比較
- [`results/boku_nano_1m_evaluation_results.md`](results/boku_nano_1m_evaluation_results.md): 2種類の1Mモデルの1エポック学習、固定5テスト、日本語言い換え30件の詳細比較
- [`results/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch_results.md`](results/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch_results.md): 1M・既存BPEの3エポック学習、固定5テスト、attention解析
- [`results/boku_nano_1m_bpe_2048_minfreq2_maxlen8_3epoch_results.md`](results/boku_nano_1m_bpe_2048_minfreq2_maxlen8_3epoch_results.md): 1M・短いpiece版BPEの3エポック学習、固定5テスト、attention解析
- [`results/boku_nano_5m_1epoch_tokenizer_comparison.md`](results/boku_nano_5m_1epoch_tokenizer_comparison.md): 正確に5,065,472パラメータの1エポックモデルを2種類のBPEで学習・評価し、日本語言い換え30件を詳細比較
- [`results/boku_nano_15m_1epoch_tokenizer_comparison.md`](results/boku_nano_15m_1epoch_tokenizer_comparison.md): 正確に15,735,168パラメータの1エポックモデルを2種類のBPEで直接比較
- [`results/trained_model_inventory.md`](results/trained_model_inventory.md): 実際に学習済みの全モデル、正確なパラメータ数、構造、epoch、評価、ハッシュ
- [`results/model_reports/README.md`](results/model_reports/README.md): 学習済み全10モデルを同じ書式でまとめた個別の学習・評価報告書
- [`results/training_loss_every_20_steps.md`](results/training_loss_every_20_steps.md): 保存済み全10モデルの20 optimizer stepごとのtrain lossとepoch別validation loss
- [`results/boku_nano_1epoch_attention_comparison.md`](results/boku_nano_1epoch_attention_comparison.md): 1M・5M・15Mの各1epoch、2トークナイザーに対する学習時準拠文型のattention可視化、Value・head ablation、因果評価
- [`results/attention_1epoch_by_result/README.md`](results/attention_1epoch_by_result/README.md): 1epochのattention解析図をトークナイザー別、さらにhead役割・sink・ablationなど8種類に分けた一覧
- [`results/boku_nano_1epoch_attention_comparison_legacy_taishite_prompt.md`](results/boku_nano_1epoch_attention_comparison_legacy_taishite_prompt.md): 旧「整数リストxsに対して、」文型による24単独操作診断の保存記録
- [`results/boku_nano_bpe_2048_minfreq2_maxlen8_1epoch_evaluation_results.md`](results/boku_nano_bpe_2048_minfreq2_maxlen8_1epoch_evaluation_results.md): 短いpiece版15Mモデルの1エポック学習・固定5テスト評価結果
- [`results/boku_nano_three_epoch_training_results.md`](results/boku_nano_three_epoch_training_results.md): Boku Nanoモデルの3エポックにおけるtrain loss・validation loss推移
- [`results/boku_nano_kv_cache_visualization.md`](results/boku_nano_kv_cache_visualization.md): 制限自然言語SLMの一時K/V状態、headの役割候補、attention sink、Valueノルム、rollout、因果的ablation、KVキャッシュ非実装と導入時容量
- [`results/boku_nano_3epoch_evaluation_results.md`](results/boku_nano_3epoch_evaluation_results.md): 3エポックモデルの5集合評価と不合格116件の分析
- [`results/paraphrase_test_instruction_results.md`](results/paraphrase_test_instruction_results.md): 日本語言い換えテスト全30件の指示、3・10エポック合否、pass@5、失敗理由
- [`results/boku_nano_evaluation_metrics_and_random_baseline.md`](results/boku_nano_evaluation_metrics_and_random_baseline.md): 段階別評価指標、pass@5、GPU効率、学習前ランダムモデルとの比較
- [`results/boku_nano_goal_completion_report.md`](results/boku_nano_goal_completion_report.md): 課題仕様の10完了条件に対する達成状況、漏洩検査、由来、残課題の総括
