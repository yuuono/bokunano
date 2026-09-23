# 全文日本語指示のルール生成方針

## 1. 目的

承認済みの単純操作表現を意味ASTの操作順に結合し、教師モデルを使わずに意味を追跡できる全文日本語指示を作る。

この工程では新しい意味ASTやPythonコードを作らない。既存の意味ASTへ日本語指示を対応付け、後続のコード結合と一部の教師全文言い換えの入力を用意する。

## 2. 入力

表現辞書は`data/instruction_dictionaries/approved_expressions.jsonl`を使用する。545件のうち`dictionary=train`の522件だけを使用し、`test_only`の23件は読み込んでも選択対象へ入れない。

意味ASTは次の5集合を入力とする。

| 集合 | 意味AST数 | 辞書 | 用途 |
|---|---:|---|---|
| train | 9,646 | `train` | 学習用 |
| validation | 1,202 | `train` | validation loss監視用 |
| normal | 1,202 | `train` | 通常テスト用。境界値テストでも同じ指示を再利用 |
| compositional | 670 | `train` | 組合せ汎化テスト用 |
| repetition | 1,152 | `train` | 反復汎化テスト用 |
| 合計 | 13,872 |  |  |

言い換えテストは`normal`と同じ意味ASTへ`test_only`表現を割り当てる別工程とし、この出力へ混ぜない。境界値テストは日本語表現を変えず、`normal`の指示と意味ASTを再利用して実行入力だけを変える。

## 3. 全文の組み立て

1操作では終止形を使う。2・3操作では最後以外を接続形、最後を終止形にし、操作順を変えず読点`、`で結ぶ。

```text
1操作: 終止形
2操作: 接続形、終止形
3操作: 接続形、接続形、終止形
```

`k`を使わない操作列には次の外側文を使う。

```text
整数リストxsから{operations}solve関数を書いてください。
```

比較、`k`倍、`k`加減算、先頭・末尾`k`個など、`k`を使う操作が一つでもあれば次を使う。

```text
整数リストxsと整数kを受け取り、{operations}solve関数を書いてください。
```

外側文には固定した`sentence_template_id`を付ける。Qwenはこの工程では使用しない。

## 4. ASTごとの表現組選択

1意味ASTにつき最大20件の固有全文を作る。20件は、各意味ASTから生成済みの最大20件のPythonコード候補と、後続工程で無制限な直積を作らず対応付けやすくするための上限である。

各操作位置の表現候補数を基数とする直積へ通し番号を付け、次の値からSHA-256で開始位置と歩幅を決める。

```text
generator_seed + spec_id + 正規化semantic_ast
```

歩幅は直積サイズと互いに素になるよう決めるため、直積全体を重複なく一巡できる。巡回中に同じ全文になる表現組を除外し、固有全文が20件へ達した時点で止める。全文の組合せ自体が20件未満なら、得られる固有件数だけを保存し、同じ文を水増ししない。

この選択は入力順や実行時乱数へ依存せず、設定、辞書、意味ASTが同じなら再現できる。すべての生成指示で`dictionary=train`を保存し、使用した`expression_ids`を意味AST順に記録する。

## 5. 出力レコード

各レコードには少なくとも次を保存する。

```json
{
  "instruction_id": "instruction-rule-...",
  "spec_id": "combined-...",
  "semantic_ast": {"sequence": []},
  "split": "train",
  "test_suite": null,
  "instruction_ja": "...",
  "instruction_source": "rule",
  "dictionary": "train",
  "dictionary_version": "...",
  "expression_ids": ["expr-candidate-..."],
  "sentence_template_id": "sentence-xs-from-v1",
  "generator_version": "1",
  "generator_seed": 20260924,
  "teacher_model": null,
  "teacher_revision": null,
  "prompt_hash": null,
  "text_hash": "..."
}
```

`instruction_id`は`spec_id`、外側テンプレートID、意味AST順の表現IDから作る。`text_hash`は完成した日本語指示のSHA-256とする。

## 6. 検査条件

生成処理は次を満たさない場合に停止する。

1. 入力意味ASTが合計13,872件で、`spec_id`と正規化意味ASTが集合間で重複しない。
2. 意味ASTの全操作が24操作のtrain辞書で解決できる。
3. `test_only`表現を一件も使用しない。
4. 同じ意味AST内と出力全体で全文が完全重複しない。
5. `instruction_id`が重複しない。
6. 522件のtrain表現が少なくとも一度使われる。
7. 実生成件数が設定へ固定した277,420件と一致する。

## 7. 保存とGit公開

生JSONLは約287 MiBあり、Gitで直接管理するには大きい。既存の複数操作Pythonコード候補と同様に、生JSONLはローカル派生物として`.gitignore`へ入れ、固定メタデータ・deflate level 9で作るZIPだけをGitへ保存する。

```text
ローカル:  data/instructions/rule_generated_instructions.jsonl
Git管理1: data/archives/rule_generated_train_instructions_2026-09-24.zip
Git管理2: data/archives/rule_generated_evaluation_instructions_2026-09-24.zip
```

GitHubの推奨50 MiBを超えないよう、`split=train`の192,900件と、それ以外のvalidation・normal・compositional・repetition 84,520件へ分ける。前者をtrain用、後者を評価用と呼ぶ。設定、生成器、集計JSON、結果文書はZIPへ入れず通常ファイルとしてGit管理する。

## 8. 再生成コマンド

承認済み辞書を作った後、次を実行する。

```bash
uv run --python 3.12.12 python \
  scripts/instruction_generation/generate_rule_instructions.py \
  --config config/rule_generated_instruction_generation.json \
  --overwrite
```

clone後にZIPから展開する場合は次を実行する。二つのZIPは別名のJSONLへ展開されるため、用途ごとにそのまま利用できる。

```bash
unzip data/archives/rule_generated_train_instructions_2026-09-24.zip -d .
unzip data/archives/rule_generated_evaluation_instructions_2026-09-24.zip -d .
```
