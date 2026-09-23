# 日本語表現辞書のGitHub公開手順

## 1. 公開するもの

GitHubへ公開するデータは、`data/instruction_dictionaries/release/`の次の2ファイルだけとする。

| ファイル | 内容 |
|---|---|
| `japanese_atomic_expressions.csv` | 人間が最終承認した、実際に使用する終止形・接続形 |
| `japanese_atomic_expression_provenance.jsonl` | 各表現に対応する生成条件と修正前候補の来歴 |

CSVにはレビュー作業用の`review_status`、編集欄、確認者欄を含めない。`edited_expression_ja`または`edited_connective_expression_ja`がある場合は、その内容を公開CSVの`expression_ja`と`connective_expression_ja`へ反映する。

JSONLはCSVと同じ件数・同じ`expression_id`順にする。各行の`approved_expression_ja`と`approved_connective_expression_ja`が公開CSVの最終表現で、`generation_record`が修正前候補を含む生成時の完全なレコードである。CSVのヘッダーを除くデータ行NとJSONLのN行目を直接対応させられ、順序に依存しない確認には`expression_id`を使える。

## 2. 公開しない作業ファイル

次はローカルで生成・レビュー・監査に使うが、GitHubへは公開しない。

- `expression_review_approved_v2.csv`と、その承認候補JSONL
- ラウンド別の候補JSONLとレビューCSV
- モデルのraw responseと生成stats
- 未承認、`unused`、未判定の候補
- 公開物から再生成できる`approved_expressions.jsonl`と分割stats

これらは削除せずローカルに保持する。`.gitignore`では`data/instruction_dictionaries/`全体をいったん除外し、`release/`の上記2ファイルだけを再許可している。これにより、作業中の候補や生応答を誤って一括追加しない。`approved_expressions.jsonl`の人手選定結果は`config/build_approved_expression_dictionary.json`へ固定し、公開済み2ファイルから再生成できる。

## 3. 公開物の更新

レビュー後は次を実行する。

```bash
uv run --python 3.12.12 python \
  scripts/instruction_generation/prepare_approved_expression_release.py \
  --review-csv \
    data/instruction_dictionaries/expression_review_approved_v2.csv \
  --candidate-jsonl \
    data/instruction_dictionaries/expression_review_approved_v2_candidates.jsonl \
  --release-directory data/instruction_dictionaries/release \
  --prune-unused
```

`--prune-unused`は、`review_status=unused`の行を承認済みマスターCSVと承認済み専用JSONLから除く。ラウンド別候補JSONLは変更しないため、除外した候補の生成履歴は監査用作業ファイルに残る。あわせて、Excel由来の余分な先頭行をマスターCSVから除去する。

スクリプトは公開前に次を検査する。

1. レビュー状態が`approved`または`unused`だけである。
2. 承認行の`expression_id`が候補JSONLに存在する。
3. CSVとJSONLの`operation_id`が一致する。
4. `expression_id`と実効表現に重複がない。
5. 公開CSVと公開JSONLを同じatomic番号順・同じID順で出力できる。

## 4. commit・push方針

公開時は、再現に必要な方針・コード・設定・promptを先のcommit、確認済みデータと実験結果を後のcommitへ分ける。結果commitを必ず履歴の最後にし、作業用データはstageしない。Pull Requestは作らず、検査後に`main`へ直接pushする。

先に方針・再現環境をcommitしてpushする。

```bash
git status --short
git add \
  .python-version pyproject.toml uv.lock \
  boku1-nano.md docs/README.md \
  config prompts scripts tests \
  .gitignore \
  docs/procedures/publishing_japanese_expression_dictionary.md \
  docs/procedures/japanese_instruction_generation.md \
  docs/policies
git diff --cached --check
git diff --cached --stat
git commit -m "Make Japanese expression generation reproducible"
git push origin main
```

最後に結果だけをcommitしてpushする。

```bash
git add \
  data/instruction_dictionaries/release/japanese_atomic_expressions.csv \
  data/instruction_dictionaries/release/japanese_atomic_expression_provenance.jsonl \
  docs/results/japanese_atomic_expression_generation_results.md \
  docs/results/japanese_atomic_expression_expansion_history.md
git diff --cached --check
git diff --cached --stat
git commit -m "Publish reviewed Japanese atomic expressions"
git push origin main
```

`git add -f`は使わない。`git add data/instruction_dictionaries/`も避け、公開する2ファイルを明示する。各pushの直前に、意図した区分のファイルだけがstageされていることを確認する。結果commitでは次を確認する。

- 公開CSVとJSONLが同数である。
- 両ファイルの`expression_id`が行単位で一致する。
- 全行が人間承認済みで、`unused`が含まれない。
- CSVの最終表現とJSONLの承認済み表現が一致する。
- ラウンド別候補、raw response、レビュー途中のCSVがstageされていない。

この方針では、利用者に必要な最終辞書と再現性確認に必要な来歴だけをGitHubへ置き、確認途中の大量データは公開成果物から分離する。
