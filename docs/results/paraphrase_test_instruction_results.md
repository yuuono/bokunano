# 言い換えテスト指示の生成結果

## 実行結果

2026年9月24日に、承認済み辞書の`test_only` 23件と人手追加した辞書外9件から、単独操作の言い換え評価指示を32件生成した。

| 項目 | 件数 |
|---|---:|
| 承認済み辞書内の`test_only`表現 | 23 |
| 人手追加した辞書外表現 | 9 |
| 言い換え評価指示 | 32 |
| 被覆した操作 | 24 |
| 2操作・3操作の指示 | 0 |

各表現を対応する単独操作ASTへ一度だけ割り当て、終止形を訓練指示と同じ外側テンプレートへ埋め込んだ。接続形は辞書に保持するが、今回の1操作文には使用していない。

## 生成した32文

| No. | 操作ID | 全文指示 |
|---:|---|---|
| 1 | `atomic-000001` | 整数リストxsから偶数を分離するsolve関数を書いてください。 |
| 2 | `atomic-000001` | 整数リストxsから2で割り切れる値を残すsolve関数を書いてください。 |
| 3 | `atomic-000001` | 整数リストxsから奇数を除くsolve関数を書いてください。 |
| 4 | `atomic-000002` | 整数リストxsから奇数を分類して残すsolve関数を書いてください。 |
| 5 | `atomic-000002` | 整数リストxsから2で割り切れない値を残すsolve関数を書いてください。 |
| 6 | `atomic-000002` | 整数リストxsから偶数を除くsolve関数を書いてください。 |
| 7 | `atomic-000003` | 整数リストxsと整数kを受け取り、kを超過する値を残すsolve関数を書いてください。 |
| 8 | `atomic-000003` | 整数リストxsと整数kを受け取り、kを超過する値を切り出すsolve関数を書いてください。 |
| 9 | `atomic-000004` | 整数リストxsと整数kを受け取り、k以上の要素を維持するsolve関数を書いてください。 |
| 10 | `atomic-000005` | 整数リストxsと整数kを受け取り、k以上じゃない値だけを残すsolve関数を書いてください。 |
| 11 | `atomic-000006` | 整数リストxsと整数kを受け取り、k以下のものを保持するsolve関数を書いてください。 |
| 12 | `atomic-000007` | 整数リストxsと整数kを受け取り、kの倍数を特定して残すsolve関数を書いてください。 |
| 13 | `atomic-000008` | 整数リストxsから正の値に限定するsolve関数を書いてください。 |
| 14 | `atomic-000009` | 整数リストxsから負の数を抜き出すsolve関数を書いてください。 |
| 15 | `atomic-000010` | 整数リストxsから零を残すsolve関数を書いてください。 |
| 16 | `atomic-000011` | 整数リストxsと整数kを受け取り、各要素にkをプラスするsolve関数を書いてください。 |
| 17 | `atomic-000012` | 整数リストxsと整数kを受け取り、各数値からkを減らすsolve関数を書いてください。 |
| 18 | `atomic-000013` | 整数リストxsと整数kを受け取り、各要素にkを掛けるsolve関数を書いてください。 |
| 19 | `atomic-000013` | 整数リストxsと整数kを受け取り、kを掛けるsolve関数を書いてください。 |
| 20 | `atomic-000014` | 整数リストxsから各要素を2倍にするsolve関数を書いてください。 |
| 21 | `atomic-000014` | 整数リストxsから各要素を二倍にするsolve関数を書いてください。 |
| 22 | `atomic-000015` | 整数リストxsから全部を三倍するsolve関数を書いてください。 |
| 23 | `atomic-000015` | 整数リストxsから全部を3倍するsolve関数を書いてください。 |
| 24 | `atomic-000016` | 整数リストxsから数の正負を入れ替えるsolve関数を書いてください。 |
| 25 | `atomic-000017` | 整数リストxsから絶対値を算出するsolve関数を書いてください。 |
| 26 | `atomic-000018` | 整数リストxsからその数と自らをかけるsolve関数を書いてください。 |
| 27 | `atomic-000019` | 整数リストxsから値を最小から最大へ並べるsolve関数を書いてください。 |
| 28 | `atomic-000020` | 整数リストxsから大きい値が先になるように並べるsolve関数を書いてください。 |
| 29 | `atomic-000021` | 整数リストxsから順序をさかさにするsolve関数を書いてください。 |
| 30 | `atomic-000022` | 整数リストxsと整数kを受け取り、最初のk個を取り出すsolve関数を書いてください。 |
| 31 | `atomic-000023` | 整数リストxsと整数kを受け取り、後ろからk個を拾うsolve関数を書いてください。 |
| 32 | `atomic-000024` | 整数リストxsから先頭から1個おきに取るsolve関数を書いてください。 |

## 出力とハッシュ

| 項目 | 値 |
|---|---|
| 生JSONL | `data/instructions/paraphrase_test_instructions.jsonl` |
| 生JSONL件数 | 32 |
| 生JSONLサイズ | 31,982 bytes |
| 生JSONL SHA-256 | `23c09b146c664f175cef0579cbecf2d664c31e41af945e9e3ab0650754ca195e` |
| ZIP | `data/archives/paraphrase_test_instructions_2026-09-24.zip` |
| ZIP内メンバー | `data/instructions/paraphrase_test_instructions.jsonl` |
| ZIPサイズ | 5,862 bytes |
| ZIP SHA-256 | `b96b3c74f60f55b8d775126714febba192e6b5ba991685ea3d234e14ba3a54b6` |
| 承認済み辞書版 | `9bd2d2b3b1585e9240cb77e8b1ddefe68a14618d5c87fa5402353c21406dc398` |
| 言い換え専用32表現版 | `705b912b523e972d87c01d1da8339cd4c683f0a21e4993584e5cb4522953363d` |

生JSONLはローカル生成物としてGit管理せず、固定日時・固定権限・固定圧縮設定で作ったZIPをGit管理する。集計値は`data/instructions/paraphrase_test_instruction_stats.json`へ保存する。

## 再生成方法

承認済み辞書の派生JSONLがない場合は、先に次を実行する。

```bash
uv run --python 3.12.12 python \
  scripts/instruction_generation/build_approved_expression_dictionary.py \
  --config config/build_approved_expression_dictionary.json \
  --overwrite
```

続いて言い換え評価指示を生成する。

```bash
uv run --python 3.12.12 python \
  scripts/instruction_generation/generate_paraphrase_test_instructions.py \
  --config config/paraphrase_test_instruction_generation.json \
  --overwrite
```

生成器は32件すべてについて、`split=test`、`test_suite=paraphrase`、`dictionary=test_only`、操作列長1、表現ID数1を検査する。
