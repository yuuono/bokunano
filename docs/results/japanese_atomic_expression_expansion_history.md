# 単純操作の日本語表現を20件以上へ増やす履歴

## 1. 目的と現在地

24種類の単純操作について、終止形`expression_ja`と接続形`connective_expression_ja`の組を複数用意し、各操作で20件以上の人間承認済み表現を確保することを目標とする。

2026年9月23日時点では、最終確認後の承認済み表現は合計545件である。24操作中20操作は20件以上へ到達し、4操作はまだ20件未満である。21件以下だった12操作に対して追加候補296件を生成し、29件に`approved`が付いた。このうち既存表現との完全一致2件を除く27件を承認済みCSVへ追加した。その後、指定参考例を使う`round_4`と`round_5`から、重複5件を除く10件を承認済みへ追加した。温度1.0の`round_6`は承認へ使用せず、66件の候補と生成履歴だけを保持している。従来表現一覧をpromptから外して温度0.9へ戻した`round_7`では、27承認行から重複1件を除く26件を追加した。その後の最終確認で8件を`unused`に変更し、承認済みマスターと公開成果物から除外した。

この文書では、次の件数を区別する。

- **生成候補数**: Qwenの出力から形式検査と完全一致重複除外を通過し、レビューCSVへ保存した件数
- **レビュー済み件数**: 人が`review_status=approved`を付けた件数
- **承認済み総数**: 重複を除いて`expression_review_approved_v2.csv`へ統合された件数
- **未レビュー候補数**: 生成済みだが、まだ承認済みCSVへ統合していない件数

生成候補を30件作っても、30件すべてが承認されるわけではない。そのため、目標20件を直接生成目標にせず、各操作30件を要求して人間確認後の残数を増やしている。

## 2. 件数を増やす手順

各追加生成では、次の手順を繰り返した。

1. `expression_review_approved_v2.csv`を操作ID別に集計する。
2. 承認済み件数が基準未満の操作だけを`--operation-id`で指定する。
3. 承認済みCSVを`--existing-review-csv`へ渡す。
4. 既存の終止形・接続形をプロンプトへ示し、完全一致する候補を除外する。
5. 各操作30件を目標として、指定した最大試行数までQwenを呼び出す。
6. ラウンド別の候補JSONLとレビューCSVへ保存する。
7. 人が内容を確認し、使用する行だけを`approved`にする。
8. 統合スクリプトで、承認行だけを承認済みCSVと生成履歴JSONLへ同時に追加する。
9. 操作別件数を再集計し、不足操作だけを次のラウンドへ回す。

追加生成の代表的な指定は次の形である。

```bash
uv run --group instruction-generation --python 3.12.12 python \
  scripts/instruction_generation/generate_atomic_expression_candidates.py \
  --config <ラウンド専用設定JSON> \
  --operation-id <対象操作ID> \
  --max-attempts-per-operation <最大試行数> \
  --existing-review-csv \
    data/instruction_dictionaries/expression_review_approved_v2.csv
```

複数操作を対象にするときは、`--operation-id`を操作ごとに繰り返す。既存表現は新規候補30件の目標数には含めず、プロンプトと完全一致除外にだけ使う。

## 3. 生成・承認ラウンドの推移

| 段階 | 対象 | 生成条件 | 生成候補 | 人間確認後の増減 | 承認済み総数 |
|---|---|---|---:|---:|---:|
| 初回生成 | 24操作すべて | 各30件、最大20試行 | 720 | 324件を承認 | 324 |
| `every_other`追加1 | `atomic-000024` | 30件 | 30 | 7件を追加 | 331 |
| `every_other`追加2 | `atomic-000024` | 50件 | 50 | 8件を追加 | 339 |
| `every_other`追加3 | `atomic-000024` | 50件 | 50 | 1件を追加 | 340 |
| 整理 | 承認済みCSV | `unused`と生成履歴を確定できない表現を整理 | ― | `atomic-000002`を1件、`atomic-000024`を2件削除 | 337 |
| 20件未満・予備試行 | 19操作 | 各30件、最大1試行 | 220 | 21件を一時追加後、生成履歴不足のため全件削除 | 337 |
| 20件未満・本生成 | 18操作 | 各30件、最大5試行 | 488 | 97件承認、完全一致2件を除き95件追加 | 432 |
| 20件未満・`round_2` | 14操作 | 各30件、最大3試行 | 352 | 58件追加 | 490 |
| 21件以下・`round_3` | 12操作 | 各30件、最大3試行 | 296 | 29件承認、完全一致2件を除き27件追加 | 517 |
| 3操作・指定参考例`round_4` | ゼロ抽出、k加算、順序反転 | 各30件、最大5試行 | 40 | 11件承認、29件未判定 | ― |
| 2操作・指定参考例`round_5` | k加算、順序反転 | 各30件、最大5試行 | 37 | 4件承認、33件未判定 | ― |
| `round_4`・`round_5`統合 | k加算、順序反転 | 候補JSONLを保持して統合 | ― | 15承認行から重複5件を除く10件追加 | 527 |
| 3操作・温度上昇`round_6` | ゼロ抽出、k加算、順序反転 | 各30件、最大5試行、温度1.0 | 66 | 未レビュー | 527 |
| 3操作・既存一覧なし`round_7` | ゼロ抽出、k加算、順序反転 | 各30件、最大5試行、温度0.9 | 73 | 27件承認、重複1件を除く26件追加 | 553 |
| 最終レビュー整理 | 承認済みマスター | `unused`をCSVと承認済み専用JSONLから除外 | ― | 8件削除 | 545 |

`every_other`の各出力ファイルは当初同じパスへ再生成していたため、表の30件、50件、50件は実行ごとの出力件数であり、現在のJSONLに130件がそのまま残っているという意味ではない。現在の`every_other_expression_candidates.jsonl`は、直近候補50件とraw responseから復元した11件を持つ。

予備試行の220件も、次の5試行版で同じ出力先を上書きしたため元ファイルは残っていない。ここで一時承認した21件は生成履歴を完全には確定できなかったため、承認済みCSVから削除した。この問題を受けて、以後はラウンド別出力と承認済み専用JSONLを分離した。

## 4. 追加生成ラウンドの実績

### 4.1 初回生成

- 設定: `config/qwen_atomic_expression_generation.json`
- 対象: 24操作
- 目標: 各30件、合計720件
- Qwen応答: 150回
- 結果: 720件、未達0操作
- 人間確認後: 324件を承認

初回生成の環境とモデル条件は[`japanese_atomic_expression_generation_results.md`](japanese_atomic_expression_generation_results.md)に記録している。

### 4.2 `atomic-000024`専用追加

「先頭から1個おきに取る」は、初回承認が4件で最少だった。この操作だけを専用設定で30件、続いて50件ずつ追加生成し、承認済み表現を4件から一時20件まで増やした。

専用追加1回目では、次の7件を採用した。

- `隔番に収集する`／`隔番に収集して`
- `隔開して列挙する`／`隔開して列挙して`
- `交互に列挙する`／`交互に列挙して`
- `隔番に集める`／`隔番に集めて`
- `隔番で集める`／`隔番で集めて`
- `隔番で並べる`／`隔番で並べて`
- `隔番に取り出す`／`隔番に取り出して`

専用追加2回目では、次の8件を採用した。

- `隔番で抽出する`／`隔番で抽出して`
- `隔番に列挙する`／`隔番に列挙して`
- `隔番で抜き出す`／`隔番で抜き出して`
- `隔番で切り出す`／`隔番で切り出して`
- `隔番で取り出す`／`隔番で取り出して`
- `先頭から隔番に取る`／`先頭から隔番に取って`
- `隔番でまとめる`／`隔番でまとめて`
- `隔番で選ぶ`／`隔番で選って`

専用追加3回目では、次の1件を採用した。

- `隔番で収集する`／`隔番で収集して`

その後、生成履歴を確定できなかった次の2件を削除し、18件とした。

- `隔番で取り出す`／`隔番で取り出して`
- `先頭から隔番に取る`／`先頭から隔番に取って`

このうち`隔番で取り出す`／`隔番で取り出して`は、後続の`round_2`で生成履歴を保持した候補として再び確認・承認したため、現在の承認済みCSVへ入っている。`先頭から隔番に取る`／`先頭から隔番に取って`は現在も削除されたままである。

### 4.3 20件未満・最大1試行の予備生成

最大試行数をCLIから指定できるようにし、まず19操作へ1試行だけ実施した。

- 生成候補: 220件
- 対象操作: 19
- 最大試行数: 1
- 30件到達: 0操作
- 一時承認: 21件

この21件を承認済みCSVへ追加した後、同じ候補JSONLを次の生成で上書きしたため、19件の完全な生成履歴が失われた。承認済み表現と生成履歴を一対一に保つ方針に反するため、21件はすべて削除した。

### 4.4 20件未満・最大5試行の本生成

- 設定: `config/qwen_atomic_expression_generation_below_20.json`
- 対象操作: 18
- 既存例: 227組
- 目標: 各30件
- 最大試行数: 5
- Qwen応答: 69回
- 生成候補: 488件
- 30件未達: 4操作

未達は次のとおりだった。

| 操作ID | 生成候補 |
|---|---:|
| `atomic-000002` | 24 |
| `atomic-000003` | 27 |
| `atomic-000011` | 6 |
| `atomic-000022` | 11 |

レビューでは97件が`approved`になった。このうち2件は既存承認済み表現と終止形・接続形が完全一致したため二重登録せず、95件を追加した。承認済み総数は337件から432件になった。

### 4.5 20件未満・`round_2`

- 設定: `config/qwen_atomic_expression_generation_below_20_round_2.json`
- 対象操作: 14
- 既存例: 189組
- 目標: 各30件
- 最大試行数: 3
- Qwen応答: 38回
- 生成候補: 352件
- 30件未達: 7操作
- レビュー承認・追加: 58件

この追加で承認済み総数は432件から490件になった。

### 4.6 21件以下・`round_3`

- 設定: `config/qwen_atomic_expression_generation_below_or_equal_21_round_3.json`
- 対象操作: 12
- 既存例: 195組
- 目標: 各30件
- 最大試行数: 3
- Qwen応答: 35回
- 生成候補: 296件
- 30件到達: 6操作
- 30件未達: 6操作
- レビュー結果: 29件に`approved`、267件は未判定
- 承認済みへの追加: 完全一致2件を除く27件
- 承認済み総数: 490件から517件

操作別の候補数は次のとおりである。

| 操作ID | 候補数 | 試行数 |
|---|---:|---:|
| `atomic-000002` | 23 | 3 |
| `atomic-000005` | 22 | 3 |
| `atomic-000006` | 30 | 3 |
| `atomic-000007` | 30 | 2 |
| `atomic-000008` | 30 | 3 |
| `atomic-000009` | 20 | 3 |
| `atomic-000010` | 30 | 3 |
| `atomic-000011` | 16 | 3 |
| `atomic-000016` | 30 | 3 |
| `atomic-000019` | 28 | 3 |
| `atomic-000021` | 30 | 3 |
| `atomic-000024` | 7 | 3 |

### 4.7 3操作・指定参考例`round_4`

承認済み件数がゼロ抽出10件、k加算4件、順序反転13件だったため、この3操作だけを別出力へ追加生成した。最初に操作単位で参考例を自動選択して3試行したround4は使用せず、同じ出力先を上書きした。上書き後は、ゼロ抽出とk加算へ指定された承認済み表現を3件ずつだけ渡し、順序反転は従来どおり同一操作の既存例だけを与えた。

- 設定: `config/qwen_atomic_expression_generation_targeted_reference_round_4.json`
- 対象: `atomic-000010`、`atomic-000011`、`atomic-000021`
- 目標: 各30件
- 最大試行数: 5
- Qwen応答: 各5回、合計15回
- JSON解析成功: 15回
- 生成候補: 40件
- 30件到達: 0操作
- レビュー結果: 11件を承認、29件が未判定
- 実際の統合順での追加: `round_5`統合後に6件追加、5件は既存IDまたは実効表現重複

| 操作ID | 承認済み行 | promptの既存除外例 | 別操作の参考例 | 生成候補 | 試行別採用数 |
|---|---:|---:|---:|---:|---|
| `atomic-000010` | 10 | 10 | 指定したfilter表現3件 | 25 | 6、8、3、8、0 |
| `atomic-000011` | 4 | 4 | 指定したmap表現3件 | 9 | 3、0、4、2、0 |
| `atomic-000021` | 13 | 16 | なし | 6 | 2、2、2、0、0 |

順序反転の「承認済み行13」に対して既存除外例が16組なのは、人が修正した3行について元候補と修正後の表現を両方とも再生成禁止例へ入れているためである。承認数自体は13件から変わっていない。

生成時点の40件は当時の承認済み実効表現とは完全一致していなかった。一方、`round_3`の未判定候補とは6件が完全一致していた。レビュー後は11件に`approved`が付き、`round_5`を先に統合した状態から6件を追加した。

- `atomic-000010`: `ゼロを特定する`／`ゼロを特定して`
- `atomic-000010`: `ゼロを拾う`／`ゼロを拾って`
- `atomic-000010`: `ゼロを分類する`／`ゼロを分類して`
- `atomic-000011`: `kを合わせる`／`kを合わせて`
- `atomic-000011`: `kを累積する`／`kを累積して`
- `atomic-000021`: `順序をひっくりかえる`／`順序をひっくりかえて`

実行コマンドは次のとおりである。

```bash
uv run --group instruction-generation --python 3.12.12 python \
  scripts/instruction_generation/generate_atomic_expression_candidates.py \
  --config config/qwen_atomic_expression_generation_targeted_reference_round_4.json \
  --operation-id atomic-000010 \
  --operation-id atomic-000011 \
  --operation-id atomic-000021 \
  --max-attempts-per-operation 5 \
  --existing-review-csv data/instruction_dictionaries/expression_review_approved_v2.csv \
  --reference-expression atomic-000010=atomic-000002=奇数のみを残す \
  --reference-expression atomic-000010=atomic-000001=偶数だけを抽出する \
  --reference-expression atomic-000010=atomic-000002=奇数を選び出す \
  --reference-expression atomic-000011=atomic-000013=要素毎にkを乗じる \
  --reference-expression atomic-000011=atomic-000014=すべての値を2倍する \
  --reference-expression atomic-000011=atomic-000012=各データをkで引く \
  --overwrite
```

system promptは従来の`atomic_expression_system.txt`を使った。user promptは今回追加した`atomic_expression_user_with_references.txt`で、テンプレートの参考例部分は次のとおりである。

```text
次の単一操作について、日本語表現を$count件生成してください。

操作ID: $operation_id
意味AST: $semantic_ast
正準な意味: $canonical_meaning_ja
厳守事項: $must_preserve_ja

すでに生成済みの次の終止形・接続形の組は出力しないでください。
$existing_expressions

次は、意味が異なる別操作の承認済み表現です。
対象操作の意味、比較条件、定数、対象位置を別操作の意味へ変えてはいけません。
これらは、対象の呼び方、動詞、語順、構文を多様化するための参考としてだけ使用してください。
$reference_expressions
```

この後ろに、終止形と接続形のJSONだけを返すこと、基本形・連用形またはて形の語尾、日本語以外を混ぜないことを従来と同じように指示している。実際に各試行へ渡した展開済みsystem prompt、user prompt、参考例全文、prompt hash、seed、モデル応答は`targeted_reference_round_4_atomic_expression_raw_responses.jsonl`へ保存した。

### 4.8 k加算・順序反転`round_5`

`round_4`と同じpromptと参考例条件を保ち、k加算と順序反転だけを新しいseedで最大5試行した。`round_4`は上書きせず、`round_5`専用の候補、レビューCSV、生応答、statsへ分離している。

- 設定: `config/qwen_atomic_expression_generation_targeted_reference_round_5.json`
- 対象: `atomic-000011`、`atomic-000021`
- 目標: 各30件
- 最大試行数: 5
- Qwen応答: 各5回、合計10回
- JSON解析成功: 10回
- 生成候補: 37件
- 30件到達: 0操作
- レビュー結果: 4件を承認、33件が未判定
- 承認済みへの追加: k加算2件、順序反転2件の合計4件
- 統合時点の承認済み総数: 517件から521件
- 後続の`round_4`統合後の承認済み総数: 527件

| 操作ID | 別操作の参考例 | 生成候補 | 試行別採用数 |
|---|---|---:|---|
| `atomic-000011` | `round_4`と同じ指定map表現3件 | 26 | 0、2、14、10、0 |
| `atomic-000021` | なし | 11 | 7、0、1、0、3 |

k加算へ渡した参考例は、`要素毎にkを乗じる`、`すべての値を2倍する`、`各データをkで引く`の3件である。順序反転へは別操作の参考例を渡していない。

生成時点の37件は当時の承認済み実効表現とは完全一致していなかった。レビュー後は4件を承認済みへ追加した。`round_4`とは順序反転の次の2件が完全一致している。

- `順序をひっくりかえる`／`順序をひっくりかえて`
- `順序を反転させる`／`順序を反転させ`

実行コマンドは次のとおりである。

```bash
uv run --group instruction-generation --python 3.12.12 python \
  scripts/instruction_generation/generate_atomic_expression_candidates.py \
  --config config/qwen_atomic_expression_generation_targeted_reference_round_5.json \
  --operation-id atomic-000011 \
  --operation-id atomic-000021 \
  --max-attempts-per-operation 5 \
  --existing-review-csv data/instruction_dictionaries/expression_review_approved_v2.csv \
  --reference-expression atomic-000011=atomic-000013=要素毎にkを乗じる \
  --reference-expression atomic-000011=atomic-000014=すべての値を2倍する \
  --reference-expression atomic-000011=atomic-000012=各データをkで引く
```

展開済みprompt、prompt hash、seed、モデル生応答は`targeted_reference_round_5_atomic_expression_raw_responses.jsonl`へ保存した。

### 4.9 3操作・温度上昇`round_6`

ゼロ抽出、k加算、順序反転を`round_4`と同じ参考例構成で生成した。最初の温度0.3版は意図と逆だったため使用せず、同じround6出力を上書きした。上書き後はランダム性を少し上げるため、`do_sample=true`を維持しつつ、従来の温度0.9から1.0へ上げた。seedは`20260929`で固定している。

- 設定: `config/qwen_atomic_expression_generation_targeted_reference_round_6.json`
- 対象: `atomic-000010`、`atomic-000011`、`atomic-000021`
- 目標: 各30件
- 最大試行数: 5
- Qwen応答: ゼロ抽出5回、k加算5回、順序反転3回の合計13回
- JSON解析成功: 13回
- 生成候補: 66件
- 30件到達: 順序反転1操作
- 30件未達: ゼロ抽出、k加算の2操作
- レビュー状態: 全66件が未判定
- 承認済み総数: 527件のまま

このラウンドは承認候補として使用しない方針とした。ただし、実施結果として候補JSONL、レビューCSV、raw response、statsは削除せず保持する。

| 操作ID | 別操作の参考例 | 生成候補 | 試行別採用数 |
|---|---|---:|---|
| `atomic-000010` | `round_4`と同じ指定filter表現3件 | 19 | 7、0、11、0、1 |
| `atomic-000011` | `round_4`と同じ指定map表現3件 | 17 | 1、2、10、4、0 |
| `atomic-000021` | なし | 30 | 19、0、11で到達 |

モデルは13応答で合計246組を返し、生成コードは66件を候補として採用した。過去候補JSONLとの完全一致は、`round_3`と12件、`round_4`と6件、`round_5`と4件ある。同じ候補が複数ラウンドに存在する場合を一度だけ数えると過去候補との重複は18件で、過去の全候補にもなかった表現は48件である。現在の承認済み実効表現との完全一致はない。

実行コマンドは次のとおりである。

```bash
uv run --group instruction-generation --python 3.12.12 python \
  scripts/instruction_generation/generate_atomic_expression_candidates.py \
  --config config/qwen_atomic_expression_generation_targeted_reference_round_6.json \
  --operation-id atomic-000010 \
  --operation-id atomic-000011 \
  --operation-id atomic-000021 \
  --max-attempts-per-operation 5 \
  --existing-review-csv data/instruction_dictionaries/expression_review_approved_v2.csv \
  --reference-expression atomic-000010=atomic-000002=奇数のみを残す \
  --reference-expression atomic-000010=atomic-000001=偶数だけを抽出する \
  --reference-expression atomic-000010=atomic-000002=奇数を選び出す \
  --reference-expression atomic-000011=atomic-000013=要素毎にkを乗じる \
  --reference-expression atomic-000011=atomic-000014=すべての値を2倍する \
  --reference-expression atomic-000011=atomic-000012=各データをkで引く
```

展開済みprompt、温度を含むsampling、prompt hash、seed、モデル生応答は`targeted_reference_round_6_atomic_expression_raw_responses.jsonl`へ保存した。

### 4.10 3操作・既存一覧なし`round_7`

従来の承認済み表現一覧へモデルが引っ張られることを避けるため、同一操作の既存表現をuser promptへ載せずに生成した。指定参考例は`round_4`と同じ6件を維持し、温度は従来値の0.9へ戻した。承認済み表現はモデルへ見せない一方、生成後の機械的な重複判定には使用している。再試行時は、今回のround7で新たに採用した候補だけをpromptへ載せた。

- 設定: `config/qwen_atomic_expression_generation_targeted_reference_round_7.json`
- 対象: `atomic-000010`、`atomic-000011`、`atomic-000021`
- 目標: 各30件
- 最大試行数: 5
- 温度: 0.9
- Qwen応答: 各5回、合計15回
- JSON解析成功: 10回（形式不正5回）
- 生成候補: 73件
- 30件到達: 順序反転1操作
- 30件未達: ゼロ抽出、k加算の2操作
- レビュー結果: 27件を承認、46件が未判定
- 承認済みへの追加: 重複1件を除く26件
- 承認済み総数: 527件から553件

| 操作ID | 別操作の参考例 | 生成候補 | 試行別採用数 |
|---|---|---:|---|
| `atomic-000010` | 指定filter表現3件 | 28 | 1、6、2、9、10 |
| `atomic-000011` | 指定map表現3件 | 15 | 0、0、0、10、5 |
| `atomic-000021` | なし | 30 | 0、0、14、10、6 |

3操作すべての初回promptで、既存表現欄が`（なし）`であることを生応答JSONLから確認した。過去候補JSONLとの完全一致はラウンド別に`round_3`と4件、`round_4`と7件、`round_5`と2件、`round_6`と3件ある。同じ候補を一度だけ数えると過去候補との重複は9件で、過去の全候補にもなかった表現は64件である。現在の承認済み実効表現との完全一致は、生成後のコード検査により0件である。

実行コマンドは次のとおりである。

```bash
uv run --group instruction-generation --python 3.12.12 python \
  scripts/instruction_generation/generate_atomic_expression_candidates.py \
  --config config/qwen_atomic_expression_generation_targeted_reference_round_7.json \
  --operation-id atomic-000010 \
  --operation-id atomic-000011 \
  --operation-id atomic-000021 \
  --max-attempts-per-operation 5 \
  --existing-review-csv data/instruction_dictionaries/expression_review_approved_v2.csv \
  --omit-existing-expressions-from-prompt \
  --reference-expression atomic-000010=atomic-000002=奇数のみを残す \
  --reference-expression atomic-000010=atomic-000001=偶数だけを抽出する \
  --reference-expression atomic-000010=atomic-000002=奇数を選び出す \
  --reference-expression atomic-000011=atomic-000013=要素毎にkを乗じる \
  --reference-expression atomic-000011=atomic-000014=すべての値を2倍する \
  --reference-expression atomic-000011=atomic-000012=各データをkで引く
```

展開済みprompt、参考例、sampling、prompt hash、seed、モデル生応答は`targeted_reference_round_7_atomic_expression_raw_responses.jsonl`へ保存した。statsの`existing_expressions_in_prompt`は`false`である。

## 5. 操作別の承認済み件数推移

最後の5列は各レビューCSVで`review_status`が空欄のまま残っている候補数であり、承認済み件数へ加算していない。

| ID | 操作 | 初回 | 専用追加・整理後 | 5試行版承認後 | `round_2`承認後 | 承認済み現在 | 未判定`round_3`候補 | 未判定`round_4`候補 | 未判定`round_5`候補 | 未判定`round_6`候補 | 未判定`round_7`候補 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `atomic-000001` | 偶数だけを残す | 13 | 13 | 14 | 23 | 21 | 0 | 0 | 0 | 0 | 0 |
| `atomic-000002` | 奇数だけを残す | 10 | 9 | 13 | 20 | 21 | 21 | 0 | 0 | 0 | 0 |
| `atomic-000003` | kより大きい値だけを残す | 11 | 11 | 29 | 29 | 29 | 0 | 0 | 0 | 0 | 0 |
| `atomic-000004` | k以上の値だけを残す | 12 | 12 | 16 | 25 | 25 | 0 | 0 | 0 | 0 | 0 |
| `atomic-000005` | kより小さい値だけを残す | 12 | 12 | 12 | 20 | 25 | 17 | 0 | 0 | 0 | 0 |
| `atomic-000006` | k以下の値だけを残す | 13 | 13 | 14 | 17 | 21 | 26 | 0 | 0 | 0 | 0 |
| `atomic-000007` | kの倍数だけを残す | 10 | 10 | 15 | 16 | 17 | 28 | 0 | 0 | 0 | 0 |
| `atomic-000008` | 正の値だけを残す | 12 | 12 | 14 | 16 | 20 | 26 | 0 | 0 | 0 | 0 |
| `atomic-000009` | 負の値だけを残す | 12 | 12 | 13 | 18 | 19 | 19 | 0 | 0 | 0 | 0 |
| `atomic-000010` | ゼロだけを残す | 8 | 8 | 9 | 10 | 12 | 30 | 25 | 0 | 19 | 25 |
| `atomic-000011` | 各要素にkを加える | 3 | 3 | 4 | 4 | 26 | 16 | 4 | 24 | 17 | 0 |
| `atomic-000012` | 各要素からkを引く | 16 | 16 | 28 | 28 | 28 | 0 | 0 | 0 | 0 | 0 |
| `atomic-000013` | 各要素にkを掛ける | 9 | 9 | 26 | 26 | 26 | 0 | 0 | 0 | 0 | 0 |
| `atomic-000014` | 各要素を2倍する | 22 | 22 | 22 | 22 | 22 | 0 | 0 | 0 | 0 | 0 |
| `atomic-000015` | 各要素を3倍する | 27 | 27 | 27 | 27 | 27 | 0 | 0 | 0 | 0 | 0 |
| `atomic-000016` | 各要素の符号を反転する | 20 | 20 | 20 | 20 | 20 | 27 | 0 | 0 | 0 | 0 |
| `atomic-000017` | 各要素の絶対値を取る | 19 | 19 | 24 | 24 | 24 | 0 | 0 | 0 | 0 | 0 |
| `atomic-000018` | 各要素を二乗する | 24 | 24 | 24 | 24 | 24 | 0 | 0 | 0 | 0 | 0 |
| `atomic-000019` | 値を昇順に並べる | 8 | 8 | 14 | 15 | 18 | 25 | 0 | 0 | 0 | 0 |
| `atomic-000020` | 値を降順に並べる | 17 | 17 | 24 | 24 | 24 | 0 | 0 | 0 | 0 | 0 |
| `atomic-000021` | 現在の要素順を反転する | 8 | 8 | 12 | 12 | 24 | 27 | 0 | 9 | 30 | 21 |
| `atomic-000022` | 先頭からk個を取る | 16 | 16 | 22 | 22 | 22 | 0 | 0 | 0 | 0 | 0 |
| `atomic-000023` | 末尾からk個を取る | 18 | 18 | 18 | 27 | 27 | 0 | 0 | 0 | 0 | 0 |
| `atomic-000024` | 先頭から1個おきに取る | 4 | 18 | 18 | 21 | 23 | 5 | 0 | 0 | 0 | 0 |
| **合計** |  | **324** | **337** | **432** | **490** | **545** | **267** | **29** | **33** | **66** | **46** |

## 6. 20件到達状況

現在の承認済み545件では、次の4操作が20件未満である。

| 操作ID | 操作 | 現在 | 20件までの不足 | 未判定`round_3`候補 | 未判定`round_4`候補 | 未判定`round_5`候補 | `round_6`記録のみ | 未判定`round_7`候補 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `atomic-000007` | kの倍数だけを残す | 17 | 3 | 28 | 0 | 0 | 0 | 0 |
| `atomic-000009` | 負の値だけを残す | 19 | 1 | 19 | 0 | 0 | 0 | 0 |
| `atomic-000010` | ゼロだけを残す | 12 | 8 | 30 | 25 | 0 | 19 | 25 |
| `atomic-000019` | 値を昇順に並べる | 18 | 2 | 25 | 0 | 0 | 0 | 0 |
| **合計** |  |  | **14** | **102** | **25** | **0** | **19** | **25** |

候補数はレビューCSVで`review_status`が空欄の行数である。`round_6`は実施記録として19件を表に残すが、今後の承認候補としては使用しない。それ以外の`round_3`、`round_4`、`round_5`、`round_7`には、現在20件未満の4操作について合計152行、完全一致を除くと144組がある。ただし、意味と日本語品質を確認して承認できた件数だけを承認済み総数へ加える。

## 7. 生成履歴を失わないための変更

予備試行で承認した21件の候補JSONLを上書きした経験から、現在は次の構成に変更している。

- ラウンドごとに異なる候補JSONL、raw response、レビューCSV、statsを使う。
- 承認済み本文は`expression_review_approved_v2.csv`へ保存する。
- 承認候補の完全な生成記録は`expression_review_approved_v2_candidates.jsonl`へ保存する。
- 統合には`merge_approved_expression_review.py`を使う。
- 統合時に、`approved`行に対応する候補IDが元JSONLに存在することを必須にする。
- 同じ操作ID・終止形・接続形の完全一致は二重登録しない。
- 人が本文を修正した場合、元候補をJSONLに残し、修正版をCSVの`edited_expression_ja`または`edited_connective_expression_ja`へ分離する。
- 承認済みCSVは`operation_id`のatomic番号順へ安定整列し、同じ操作内の確認順は維持する。
- 承認候補JSONLは承認済みCSVと同じ`expression_id`順へ並べる。CSVのヘッダーを除くデータ行NとJSONLのN行目が対応する。
- 個別レコードは両ファイルの`expression_id`を照合する。CSVの編集欄が空でなければ、`edited_expression_ja`と`edited_connective_expression_ja`を最終的な辞書表現として優先する。
- 最終レビューで`unused`になった8件は承認済みマスターと承認済み専用JSONLから除いた。元のラウンド別候補JSONLは保持しているため、除外候補の生成履歴も失われていない。
- GitHubには`release/`の最終表現CSVと対応する来歴JSONLだけを公開し、ラウンド別候補、レビューCSV、raw response、statsはローカル作業用として分離する。

現在は次の整合性を満たしている。

| 検査 | 結果 |
|---|---:|
| 承認済みCSV | 545件 |
| 承認候補JSONL | 545件 |
| CSVとJSONLのID集合 | 完全一致 |
| ID重複 | 0件 |
| 実効表現の完全一致重複 | 0件 |
| モデル、revision、seed、sampling、生成日時、試行番号、prompt hashの欠落 | 0件 |
| 公開CSV | 545件 |
| 公開来歴JSONL | 545件 |
| 公開CSVと公開JSONLの行順 | `expression_id`で完全一致 |

## 8. 関連ファイル

| ファイル | 内容 |
|---|---|
| `data/instruction_dictionaries/expression_review_approved_v2.csv` | ローカル作業用の承認済み表現545件 |
| `data/instruction_dictionaries/expression_review_approved_v2_candidates.jsonl` | ローカル作業用の承認済み545件の生成履歴 |
| `data/instruction_dictionaries/release/japanese_atomic_expressions.csv` | GitHub公開用の最終表現545件 |
| `data/instruction_dictionaries/release/japanese_atomic_expression_provenance.jsonl` | 最終表現545件と元候補の生成来歴 |
| `data/instruction_dictionaries/below_20_expression_review.csv` | 最大5試行版のレビュー結果 |
| `data/instruction_dictionaries/below_20_round_2_expression_review.csv` | `round_2`のレビュー結果 |
| `data/instruction_dictionaries/below_or_equal_21_round_3_expression_review.csv` | `approved`29件、未判定267件の`round_3`レビュー |
| `data/instruction_dictionaries/targeted_reference_round_4_expression_candidates.jsonl` | 3操作の追加候補40件と生成メタデータ |
| `data/instruction_dictionaries/targeted_reference_round_4_expression_review.csv` | 11件承認、29件未判定の`round_4`レビュー |
| `data/instruction_dictionaries/targeted_reference_round_4_atomic_expression_raw_responses.jsonl` | 15試行分の展開済みpromptとQwen生応答 |
| `data/instruction_dictionaries/targeted_reference_round_4_atomic_expression_generation_stats.json` | 参考操作、例数、試行数、生成件数の集計 |
| `data/instruction_dictionaries/targeted_reference_round_5_expression_candidates.jsonl` | k加算と順序反転の追加候補37件と生成メタデータ |
| `data/instruction_dictionaries/targeted_reference_round_5_expression_review.csv` | 4件承認、33件未判定の`round_5`レビュー |
| `data/instruction_dictionaries/targeted_reference_round_5_atomic_expression_raw_responses.jsonl` | 10試行分の展開済みpromptとQwen生応答 |
| `data/instruction_dictionaries/targeted_reference_round_5_atomic_expression_generation_stats.json` | round5の参考操作、例数、試行数、生成件数の集計 |
| `data/instruction_dictionaries/targeted_reference_round_6_expression_candidates.jsonl` | 温度1.0で生成した3操作の追加候補66件 |
| `data/instruction_dictionaries/targeted_reference_round_6_expression_review.csv` | 全66件が未判定の`round_6`レビュー |
| `data/instruction_dictionaries/targeted_reference_round_6_atomic_expression_raw_responses.jsonl` | 13試行分の展開済みpromptとQwen生応答 |
| `data/instruction_dictionaries/targeted_reference_round_6_atomic_expression_generation_stats.json` | round6の温度、参考操作、試行数、生成件数の集計 |
| `data/instruction_dictionaries/targeted_reference_round_7_expression_candidates.jsonl` | 既存一覧をpromptから外して生成した追加候補73件 |
| `data/instruction_dictionaries/targeted_reference_round_7_expression_review.csv` | 27件承認、46件未判定の`round_7`レビュー |
| `data/instruction_dictionaries/targeted_reference_round_7_atomic_expression_raw_responses.jsonl` | 15試行分の展開済みpromptとQwen生応答 |
| `data/instruction_dictionaries/targeted_reference_round_7_atomic_expression_generation_stats.json` | round7のprompt条件、参考操作、試行数、生成件数の集計 |
| `scripts/instruction_generation/merge_approved_expression_review.py` | CSVと生成履歴JSONLを同時に統合するスクリプト |
| `scripts/instruction_generation/prepare_approved_expression_release.py` | `unused`除去、整合性検査、公開用2ファイル作成 |

言い換えテスト専用表現を訓練へ混入させない方針は、[`japanese_instruction_generation.md`](../procedures/japanese_instruction_generation.md)に従う。
