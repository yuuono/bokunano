# 日本語指示生成手順書

## 1. 目的

検証済みの意味ASTとPythonコードに、日本語の指示文を付けるための手順を定める。

中心となる作業は、次の3段階である。

1. 24種類の単純操作について、日本語表現の辞書を作る
2. 作成者本人が各表現を確認し、使用する表現を確定する
3. 承認済み辞書の表現を意味ASTの操作順に組み合わせ、訓練データ用の指示文を作る

その後、必要な一部の指示文だけを教師モデルで言い換える。

## 2. 入力と成果物

### 入力

- [`atomic_semantic_asts.md`](../specifications/atomic_semantic_asts.md)で定義した24種類の単純操作
- 分割済みの意味AST
- 検証と完全重複除外が完了したPythonコード候補

### 成果物

```text
表現候補
  ↓ 作成者が確認
承認済み表現辞書
  ↓ 意味AST順に組み合わせる
ルール生成指示
  ↓ 一部だけ言い換えて再確認
承認済み教師言い換え
  ↓ 検証済みコードと結合
最終訓練・評価データ
```

保存先は、次の構成を基本とする。

```text
data/
├── instruction_dictionaries/
│   ├── expression_candidates.jsonl
│   └── approved_expressions.jsonl
├── instructions/
│   ├── rule_generated_instructions.jsonl
│   └── approved_teacher_paraphrases.jsonl
└── final/
    └── final_dataset_records.jsonl
```

## 3. 手順1: 単純操作の表現辞書を作る

### 3.1 対象操作

次の24操作を、それぞれ独立して扱う。

| 分類 | 操作数 | 例 |
|---|---:|---|
| 抽出 | 10 | 偶数だけを残す、`k`以上だけを残す |
| 変換 | 8 | `k`を加える、2倍する、絶対値を取る |
| 並べ替え | 3 | 昇順、降順、現在順の反転 |
| 切り出し | 3 | 先頭`k`個、末尾`k`個、1個おき |

正式な操作一覧と意味は、[`atomic_semantic_asts.md`](../specifications/atomic_semantic_asts.md)を正とする。

### 3.2 Qwen3で表現候補を作る

各操作について、Qwen3に10〜30種類の日本語表現を生成させる。

使用する実装とプロンプトは次のとおりである。

- 実行スクリプト: `scripts/instruction_generation/generate_atomic_expression_candidates.py`
- 共通Qwen呼び出し: `scripts/instruction_generation/qwen_teacher.py`
- system prompt: `prompts/japanese_instruction_generation/atomic_expression_system.txt`
- user prompt: `prompts/japanese_instruction_generation/atomic_expression_user.txt`
- 実行設定: `config/qwen_atomic_expression_generation.json`
- 24操作の正準な意味: `config/japanese_atomic_operations.json`

最初に、モデルを読み込まず設定を確認する。

```bash
uv run python scripts/instruction_generation/generate_atomic_expression_candidates.py \
  --config config/qwen_atomic_expression_generation.json \
  --validate-config
```

実生成はCUDA対応環境で行う。

```bash
uv run scripts/instruction_generation/generate_atomic_expression_candidates.py \
  --config config/qwen_atomic_expression_generation.json
```

Qwen3は`enable_thinking=false`で使用する。標準設定では各操作20件、合計480件の候補を生成する。

`model_id`と`revision`は別の情報である。

- `model_id`: 使用するモデルの名前。例: `Qwen/Qwen3-4B-AWQ`
- `revision`: そのモデルのどの版を使うかを表す40桁のコミットID。現在の固定値は`74d4bd2bd4bff9cafc9345221320bffb08b406a3`

`main`もTransformersへ渡せるrevision名ではあるが、モデル提供者が更新すると参照内容が変わる。そのため、正式生成では`main`や短縮ハッシュを禁止し、完全なコミットIDを設定してからモデルを読み込む。保存する`teacher_revision`には、実際に読み込まれたコミットIDを記録する。

非thinkingモードを指定していても、出力に`<think>`または`</think>`タグが一つでも含まれた場合は、その応答全体を拒否する。該当応答は表現候補にも生出力記録にも保存しない。

候補は、後で他の操作と接続できる短い表現にする。

```text
偶数の要素だけを残す
2で割り切れる値のみを選ぶ
奇数の要素を取り除く
```

候補には、次の内容を含めない。

- `solve`関数全体への指示
- 「まず」「次に」など、操作位置を固定する言葉
- 対象以外の操作
- Pythonコードや実装方法

`k`を使用する操作では、`k`との関係が分かる表現にする。

```text
各要素にkを加える
k以上の値だけを残す
末尾からk個を取り出す
```

### 3.3 表現候補を保存する

候補は、1表現につき1レコードで保存する。

```json
{
  "expression_id": "expr-candidate-...",
  "operation_id": "atomic-000004",
  "operation_ast": {"filter": ["ge_k"]},
  "canonical_meaning_ja": "k以上の値だけを残す",
  "expression_ja": "k以上の要素に絞り込む",
  "review_status": "pending",
  "teacher_model": "Qwen/Qwen3-4B-AWQ",
  "teacher_revision": "...",
  "prompt_hash": "..."
}
```

候補生成時点では、訓練データに使用しない。

## 4. 手順2: 作成者が表現を確認する

### 4.1 確認画面または一覧を作る

操作ごとに、次の項目を並べて確認できるようにする。

| 項目 | 内容 |
|---|---|
| 操作ID | `atomic-000004`など |
| 意味AST | `{"filter":["ge_k"]}`など |
| 正準な意味 | `k`以上の値だけを残す |
| 表現候補 | `k`以上の要素に絞り込む |
| 確認結果 | 承認、修正、不使用 |

確認用の形式は、CSV、スプレッドシート、簡単な確認画面のどれでもよい。確認後はJSONLへ戻せるように、`expression_id`を変更しない。

標準スクリプトは`data/instruction_dictionaries/expression_review.csv`を出力する。使用する行は`review_status`へ`approved`、使用しない行は`unused`を記入する。承認行には`dictionary`、`reviewer`、`reviewed_at`も記入する。

### 4.2 確認する内容

各表現について、次の3点を確認する。

1. 意味ASTと同じ処理を表しているか
2. 日本語として自然で、単独で意味が分かるか
3. 他の操作と前後に接続できる形になっているか

特に、次の意味を混同しないようにする。

- 「`k`より大きい」と「`k`以上」
- 「`k`より小さい」と「`k`以下」
- 「各要素から`k`を引く」と「`k`から各要素を引く」
- 「値を降順に並べる」と「現在の並び順を逆にする」
- 「先頭から`k`個」と「末尾から`k`個」
- 「1個おきに取る」と「偶数だけを取る」

修正した表現は、修正後の文をもう一度確認してから承認する。

### 4.3 承認済み辞書を確定する

承認した表現だけを`approved_expressions.jsonl`へ保存する。

```json
{
  "expression_id": "expr-...",
  "operation_id": "atomic-000004",
  "operation_ast": {"filter": ["ge_k"]},
  "expression_ja": "k以上の要素に絞り込む",
  "dictionary": "train",
  "approved_by": "...",
  "approved_at": "...",
  "source_candidate_id": "expr-candidate-..."
}
```

24操作のそれぞれについて、最終的に10〜30種類の承認済み表現を用意する。足りない場合は追加候補を作り、同じ手順で確認する。

確認後、次を実行して承認済み辞書を作る。

```bash
uv run python scripts/instruction_generation/build_approved_expression_dictionary.py \
  --config config/build_approved_expression_dictionary.json
```

### 4.4 訓練用とテスト専用に分ける

承認済み表現は、使用前に次の2辞書へ分ける。

- `train`: 訓練、検証、通常テスト、組合せ汎化テスト、境界値テストで使用する
- `test_only`: 言い換えテストだけで使用する

`test_only`へ入れた表現は、訓練用指示文や訓練用プロンプトへ入れない。

辞書を確定したら、内容ハッシュまたはバージョンを付ける。以後の指示文には、使用した辞書のバージョンを記録する。

## 5. 手順3: 辞書を組み合わせて指示文を作る

### 5.1 意味ASTから操作列を取り出す

単独操作と複数操作を、生成器内では次の配列として扱う。

```text
単独操作: [operation]
複数操作: semantic_ast.sequence
```

`sequence`の先頭から順番に処理する。生成器は操作の並べ替え、削除、統合を行わない。

### 5.2 各操作に対応する辞書表現を選ぶ

意味AST内の各操作について、同じ`operation_ast`を持つ承認済み表現を1件選ぶ。

- 言い換えテスト以外: `train`辞書から選ぶ
- 言い換えテスト: `test_only`辞書から選ぶ

選択した`expression_id`は、意味ASTと同じ順番で記録する。

### 5.3 操作順を保って結合する

1操作の場合は、その表現をそのまま使用する。

```text
1. {op1}
```

2操作の場合は、2番目の操作が1番目の結果に適用されることを明記する。

```text
1. {op1}
2. その結果に対して、{op2}
```

3操作の場合も同様に接続する。

```text
1. {op1}
2. その結果に対して、{op2}
3. その結果に対して、{op3}
```

外側の文テンプレートは、例えば次のようにする。

```text
整数リストxsと整数kを受け取り、以下の処理を上から順に行って、結果の整数リストを返すsolve関数を書いてください。
{operations}
```

### 5.4 結合例

意味ASTが次の場合を考える。

```json
{
  "sequence": [
    {"filter": ["ge_k"]},
    {"map": ["mul_const", 2]},
    {"order": "descending"}
  ]
}
```

辞書から次の表現を選ぶ。

```text
op1: k以上の値だけに絞る
op2: 各要素を2倍する
op3: 値の大きい順に並べ替える
```

生成する指示文は次のとおりである。

```text
整数リストxsと整数kを受け取り、以下の処理を上から順に行って、結果の整数リストを返すsolve関数を書いてください。
1. k以上の値だけに絞る
2. その結果に対して、各要素を2倍する
3. その結果に対して、値の大きい順に並べ替える
```

### 5.5 複数の指示文を作る

同じ意味ASTでも、各操作について選ぶ辞書表現を変えることで複数の指示文を作れる。

ただし、辞書内の全表現を無制限に直積で組み合わせない。1つの意味ASTから作る件数の上限を先に決め、各表現の使用回数が偏らないように選ぶ。

選択は固定seedを使って再現可能にする。

### 5.6 生成結果を保存する

```json
{
  "instruction_id": "instruction-rule-...",
  "spec_id": "combined-...",
  "semantic_ast": {},
  "instruction_ja": "...",
  "instruction_source": "rule",
  "dictionary": "train",
  "dictionary_version": "...",
  "expression_ids": ["expr-...", "expr-..."],
  "sentence_template_id": "sentence-...",
  "generator_version": "...",
  "generator_seed": 0,
  "teacher_model": null,
  "teacher_revision": null,
  "prompt_hash": null,
  "text_hash": "..."
}
```

保存前に、意味ASTの操作数と`expression_ids`の数が一致し、各表現の`operation_ast`が同じ位置の操作と一致することを機械的に確認する。

## 6. 手順4: 一部だけ教師モデルで言い換える

ルール生成した指示文の一部だけを、Qwen3で文全体として言い換える。

### 6.1 この工程を行う理由

この工程は追加の独自仕様ではなく、[`boku1-nano.md`の「日本語指示の生成」4番](../../boku1-nano.md#日本語指示の生成)にある「一部についてのみ、教師モデルに文全体の言い換えを行わせる」に対応する。

承認済み表現辞書で変化するのは、基本的に「偶数だけを残す」などの各操作部分である。外側の文テンプレートや操作同士の接続方法はルール生成器が作るため、そのままではすべての指示文が似た文型になりやすい。

そこで、一部のルール生成指示についてだけ、次のような文全体の違いを追加する。

- 箇条書きを自然な一文または複数文へ変える
- 「その結果に対して」を別の自然な接続表現へ変える
- 操作順を保ったまま、語順や文末表現を変える

この工程で新しい問題、意味AST、正解コードを作るわけではない。元の意味ASTと正解コードは固定したまま、日本語の文型だけを増やす。

全文言い換えを全件へ適用しない理由は、教師モデルが比較境界や操作順を変える危険があるためである。大部分は意味を機械的に保証しやすいルール生成文として残し、一部だけを言い換え、作成者本人が元文と比較して承認する。

また、この全文言い換えは、`test_only`辞書を使用する言い換えテストとは別の処理である。

- 承認済み表現辞書: 単純操作の短い表現を増やす
- ルール生成器: 辞書表現を意味AST順に結合する
- 教師による全文言い換え: 結合後の文全体の文型を一部だけ増やす
- 言い換えテスト: 訓練に使っていない`test_only`表現で評価する

### 6.2 「初学者向け解説」とこの工程の関係

「初学者向け解説」は、生成済みPythonコードについて「この行で偶数だけを選び、次の行で昇順に並べています」などと学習者向けに説明する文章を指す。これは、プログラムを書くよう求める日本語指示文そのものではない。

現在作成している`instruction_ja`から`reference_code`を生成させる訓練データには、初学者向け解説を使用しない。表現辞書、ルール生成指示、教師による全文言い換えのいずれにも混ぜず、現在の実装対象外とする。将来、コード解説用の別データセットを作る場合だけ、独立した工程と保存先を定めて生成する。

要件にある「最終的な指示文または解説文だけを保存する」のうち、今回関係するのは「最終的な指示文」だけである。「解説文」は将来別目的で教師モデルを使う場合を含めた表現であり、今回の日本語指示生成工程の成果物ではない。

### 6.3 実行方法

使用する実装とプロンプトは次のとおりである。

- 実行スクリプト: `scripts/instruction_generation/generate_instruction_paraphrase_candidates.py`
- system prompt: `prompts/japanese_instruction_generation/paraphrase_system.txt`
- user prompt: `prompts/japanese_instruction_generation/paraphrase_user.txt`
- 実行設定: `config/qwen_instruction_paraphrase_generation.json`

`data/instructions/rule_generated_instructions.jsonl`を作成した後、CUDA対応環境で次を実行する。

```bash
uv run scripts/instruction_generation/generate_instruction_paraphrase_candidates.py \
  --config config/qwen_instruction_paraphrase_generation.json
```

### 6.4 教師へ渡す情報と人間確認

教師モデルには、次を一緒に渡す。

- 元のルール生成指示
- 意味AST
- 操作の正しい順番
- `xs`、`k`、定数など、変更してはいけない情報

教師モデルの出力は自動採用しない。作成者本人が、次の3点を並べて確認する。

1. 意味AST
2. 元のルール生成指示
3. 教師モデルによる言い換え

意味と操作順が同じであることを確認できた文だけを採用する。

採用時は、元の指示ID、教師モデル名、revision、`prompt_hash`を保存する。

```json
{
  "instruction_id": "instruction-teacher-...",
  "source_instruction_id": "instruction-rule-...",
  "instruction_ja": "...",
  "instruction_source": "teacher",
  "teacher_model": "Qwen/Qwen3-4B-AWQ",
  "teacher_revision": "...",
  "prompt_hash": "...",
  "approved_by": "...",
  "approved_at": "...",
  "text_hash": "..."
}
```

## 7. 検証済みコードと結合する

承認済み指示と検証済みコードを、`spec_id`と`semantic_hash`で対応付ける。

結合するときは、次を確認する。

1. 指示文とコードが同じ意味ASTに属している。
2. 言い換えテスト以外では`train`辞書を使用している。
3. 言い換えテストでは`test_only`辞書を使用している。
4. ルール生成指示の教師関係項目が`null`になっている。
5. 教師言い換えではモデル名、revision、`prompt_hash`が記録されている。

同じ意味ASTの全コードと全指示を無制限に組み合わせず、最終データの上限と均等選抜方針に従って必要な件数だけを選ぶ。

最終レコードの形式は、[`data_record_policy.md`](../policies/data_record_policy.md)に従う。

## 8. 実施順チェックリスト

### 表現辞書

- [ ] 24種類の操作を一覧化した
- [ ] 各操作についてQwen3で表現候補を作った
- [ ] 候補を操作別に確認できる一覧へ出力した
- [ ] 作成者本人が各表現を確認した
- [ ] 各操作について10〜30種類の承認済み表現を確保した
- [ ] 承認済み表現を`train`と`test_only`へ分けた
- [ ] 辞書のバージョンを固定した

### ルール生成

- [ ] 意味ASTから操作列を順番どおりに取り出した
- [ ] 各操作に対応する承認済み表現を選んだ
- [ ] 2番目以降の操作を「その結果」に適用する形で接続した
- [ ] 1つの意味ASTから作る指示数の上限を適用した
- [ ] 表現の使用回数が偏っていないことを確認した
- [ ] 使用した表現IDとテンプレートIDを保存した

### 教師言い換えと最終結合

- [ ] ルール生成指示の一部だけを教師モデルで言い換えた
- [ ] 作成者本人が元文と教師言い換えを比較した
- [ ] 承認済み言い換えだけを採用した
- [ ] 指示文と検証済みコードを同じ意味ASTで結合した
- [ ] `test_only`表現が訓練データへ入っていないことを確認した
- [ ] 最終レコードの必須項目とハッシュを確認した

## 9. 完了条件

次をすべて満たしたら、日本語指示生成を完了とする。

1. 24操作すべてに10〜30種類の承認済み表現がある。
2. すべての表現を作成者本人が確認している。
3. 訓練用とテスト専用の辞書が分離されている。
4. すべてのルール生成指示が意味ASTの操作順を保っている。
5. 教師言い換えは一部だけに使われ、採用文を作成者本人が確認している。
6. 各指示文から、使用した辞書表現と元の意味ASTを追跡できる。
7. 承認済み指示と検証済みコードを正しく結合できている。
