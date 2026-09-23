# 文書の案内

```text
docs/
├── policies/        # データ分割、コード生成、選抜、評価の方針
├── procedures/      # データ生成作業の具体的な手順
├── specifications/  # 意味ASTと参照インタプリタの仕様
└── results/         # 実行済みの生成・検証結果
```

## 方針

- [`policies/terminology_policy.md`](policies/terminology_policy.md): 用語の統一
- [`policies/ast_split_policy.md`](policies/ast_split_policy.md): 意味ASTの分割
- [`policies/compositional_generalization_test_policy.md`](policies/compositional_generalization_test_policy.md): 組合せ汎化テスト
- [`policies/repetition_generalization_test_policy.md`](policies/repetition_generalization_test_policy.md): 反復汎化テスト
- [`policies/python_code_generation_policy.md`](policies/python_code_generation_policy.md): Pythonコード生成
- [`policies/code_duplicate_exclusion_policy.md`](policies/code_duplicate_exclusion_policy.md): 生成コードの完全重複除外
- [`policies/data_record_policy.md`](policies/data_record_policy.md): データレコードと選抜
- [`policies/japanese_paraphrase_test_policy.md`](policies/japanese_paraphrase_test_policy.md): 人手選定した未学習表現による日本語言い換えテスト
- [`policies/rule_generated_instruction_policy.md`](policies/rule_generated_instruction_policy.md): 承認済み表現と意味ASTから全文指示を決定的に作る方針

## 手順

- [`procedures/japanese_instruction_generation.md`](procedures/japanese_instruction_generation.md): 日本語指示の候補生成、人間承認、ルール結合、教師言い換え
- [`procedures/publishing_japanese_expression_dictionary.md`](procedures/publishing_japanese_expression_dictionary.md): 最終表現CSVと生成来歴JSONLだけをGitHubへ公開する手順

## 仕様

- [`specifications/atomic_semantic_asts.md`](specifications/atomic_semantic_asts.md): 24種類の単独操作
- [`specifications/reference_interpreter.md`](specifications/reference_interpreter.md): 参照インタプリタ

## 結果

- [`results/atomic_python_code_generation_results.md`](results/atomic_python_code_generation_results.md): 各操作1件の予備確認
- [`results/single_operation_python_code_generation_results.md`](results/single_operation_python_code_generation_results.md): 各操作20件の生成結果
- [`results/multi_operation_python_code_generation_results.md`](results/multi_operation_python_code_generation_results.md): 2・3操作を各AST 20件生成した結果
- [`results/japanese_atomic_expression_generation_results.md`](results/japanese_atomic_expression_generation_results.md): Qwen3による24操作各30件の初回生成パラメータ、結果、人間確認で見つかった問題
- [`results/japanese_atomic_expression_expansion_history.md`](results/japanese_atomic_expression_expansion_history.md): 各操作20件以上を目指した追加生成、承認数の推移、生成履歴保存の経緯
- [`results/japanese_atomic_expression_split_results.md`](results/japanese_atomic_expression_split_results.md): 人手選定による545件のtrain・test_only分割結果
- [`results/rule_generated_instruction_results.md`](results/rule_generated_instruction_results.md): 13,872意味ASTから作成した277,420件の全文指示
