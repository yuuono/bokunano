# 全文日本語指示のルール生成結果

## 実行結果

2026年9月24日に、承認済み`train`表現522件と5集合の意味AST 13,872件から、全文日本語指示277,420件をルール生成した。

| 入力集合 | 意味AST数 | 生成指示数 |
|---|---:|---:|
| train | 9,646 | 192,900 |
| validation | 1,202 | 24,040 |
| normal | 1,202 | 24,040 |
| compositional | 670 | 13,400 |
| repetition | 1,152 | 23,040 |
| 合計 | 13,872 | 277,420 |

操作数別の指示数は次のとおりである。

| 操作数 | 指示数 |
|---|---:|
| 1操作 | 460 |
| 2操作 | 11,520 |
| 3操作 | 265,440 |
| 合計 | 277,420 |

2・3操作ASTでは各20件を生成した。1操作ASTでは、終止形が完全一致する表現IDを別々の全文として水増しせず、固有全文だけを最大20件生成した。このため24操作×20件の480件ではなく460件になった。

## 辞書と選択

- 辞書総数: 545件
- 使用区分: `train` 522件のみ
- `test_only`使用数: 0件
- 実際に一度以上使われたtrain表現: 522件
- 辞書バージョン: `9bd2d2b3b1585e9240cb77e8b1ddefe68a14618d5c87fa5402353c21406dc398`
- generator seed: `20260924`
- generator version: `1`

各操作内の表現使用回数は、表現数が異なるため操作間では比較しない。操作内では、最小使用回数と最大使用回数の差は平均使用回数に対して約2.9%〜11.2%の範囲だった。全522表現を使用できており、一部表現だけが未使用になる偏りはなかった。詳細値は`data/instructions/rule_generated_instruction_stats.json`に保存した。

## 検査結果

生成時に次を確認した。

- 意味AST 13,872件の`spec_id`と正規化意味ASTに集合間重複がない。
- 全操作がtrain辞書で解決できる。
- 意味ASTの操作順と`expression_ids`の順番が一致する。
- 最後以外は接続形、最後は終止形を使用する。
- 全277,420件で`instruction_id`が重複しない。
- 全277,420件で`instruction_ja`が完全重複しない。
- `test_only`表現を使用していない。
- 522件のtrain表現をすべて一度以上使用した。

## 出力とZIP

生JSONLと分割後ZIPの情報は次のとおりである。

| 項目 | 値 |
|---|---|
| 生JSONL | `data/instructions/rule_generated_instructions.jsonl` |
| レコード数 | 277,420 |
| 生JSONLサイズ | 300,622,921 bytes（約287 MiB） |
| 生JSONL SHA-256 | `419f26ed8797296975c801fab0adb2a944dcedd584470ed756f1c0bf1055a0a8` |
| train ZIP | `data/archives/rule_generated_train_instructions_2026-09-24.zip` |
| train ZIP収録数 | 192,900件 |
| train ZIPサイズ | 37,809,698 bytes（約36.1 MiB） |
| train ZIP SHA-256 | `6299f0c09b0fcbe095d1537a55dc9f4f0fa5dd815f5ba01f0fd75e7c9a871d24` |
| 評価ZIP | `data/archives/rule_generated_evaluation_instructions_2026-09-24.zip` |
| 評価ZIP収録数 | 84,520件 |
| 評価ZIPサイズ | 14,918,313 bytes（約14.2 MiB） |
| 評価ZIP SHA-256 | `1a9e25807c2921359f308fb4951faabf13c9fbb9fbd1f0e5e7019f8be6f6ed3b` |

生JSONLはGitHubへ直接置かず、train用と評価用のZIPだけをGit管理する。両ZIPともGitHubの推奨50 MiB未満で、既存のコード候補アーカイブと同じ方法で展開できる。設定・スクリプト・集計JSONを通常ファイルとして併せて管理するため、ZIPだけで生成条件が不明になることはない。

## 実行コマンド

```bash
uv run --python 3.12.12 python \
  scripts/instruction_generation/generate_rule_instructions.py \
  --config config/rule_generated_instruction_generation.json \
  --overwrite
```

ルール生成の具体的な選択・結合・保存方針は、[`rule_generated_instruction_policy.md`](../policies/rule_generated_instruction_policy.md)に記録した。
