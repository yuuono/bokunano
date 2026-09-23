# 日本語単純操作表現のtrain・test_only分割結果

## 実行結果

2026年9月24日に、人間が承認した545件を、人手選定済みの`expression_id`に従って分割した。

| 区分 | 件数 |
|---|---:|
| `train` | 522 |
| `test_only` | 23 |
| 合計 | 545 |

`test_only`は22操作を覆う。`atomic-000003`は「超過」を含む承認済み表現をすべて使用するため2件である。`atomic-000018`と`atomic-000021`は、希望した表現が承認済み545件に存在しないため0件である。

実行時の辞書バージョンは次のとおりである。

```text
9bd2d2b3b1585e9240cb77e8b1ddefe68a14618d5c87fa5402353c21406dc398
```

## 実行コマンド

```bash
uv run --python 3.12.12 python \
  scripts/instruction_generation/build_approved_expression_dictionary.py \
  --config config/build_approved_expression_dictionary.json \
  --overwrite
```

生成したローカル派生物は次の2ファイルである。

- `data/instruction_dictionaries/approved_expressions.jsonl`: 545行
- `data/instruction_dictionaries/approved_expression_stats.json`: 分割件数と人手選定ID

JSONL各行には、公開CSVの承認済み表現、`dictionary`区分、分割方法`human_reviewed`、公開来歴JSONLにあった完全な`generation_record`を保存した。

人手選定の内容と辞書外9候補の扱いは、[`japanese_paraphrase_test_policy.md`](../policies/japanese_paraphrase_test_policy.md)に記録している。
