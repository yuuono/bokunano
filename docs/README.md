# 文書の案内

```text
docs/
├── policies/        # データ分割、コード生成、選抜、評価の方針
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

## 仕様

- [`specifications/atomic_semantic_asts.md`](specifications/atomic_semantic_asts.md): 24種類の単独操作
- [`specifications/reference_interpreter.md`](specifications/reference_interpreter.md): 参照インタプリタ

## 結果

- [`results/atomic_python_code_generation_results.md`](results/atomic_python_code_generation_results.md): 各操作1件の予備確認
- [`results/single_operation_python_code_generation_results.md`](results/single_operation_python_code_generation_results.md): 各操作20件の生成結果
- [`results/multi_operation_python_code_generation_results.md`](results/multi_operation_python_code_generation_results.md): 2・3操作を各AST 20件生成した結果
