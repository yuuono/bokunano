# データレコードの作成・管理方針

## 目的

意味AST、生成Pythonコード、日本語指示、テスト、検証結果を追跡可能な形で保存する。

1つの意味ASTから複数のコードと日本語指示を作るため、`spec_id`だけでは個々のレコードを識別できない。意味AST、コード候補、最終学習レコードを別の段階として管理し、それぞれに一意なIDを付ける。

最終学習レコードでは、`boku1-nano.md`の「データレコード」に示した項目をすべて保存する。コード生成時点で存在しない日本語・教師モデル関係の項目は、最終レコードを組み立てる段階で追加する。

## レコードの3段階

```text
意味ASTレコード
    ↓ Pythonコード生成・検証
コード候補レコード
    ↓ 生成コードの完全重複を除外
    ↓ 日本語指示生成・結合
最終データレコード
```

日本語指示は、訓練側と評価側の生成コードの完全重複を除外した後に作る。完全重複の判定に日本語指示は使わない。

- 意味ASTレコード: 問題の意味、分割、テスト集合を管理する
- コード候補レコード: 1つの意味ASTから生成した個々のPythonコードを管理する
- 最終データレコード: 日本語指示、コード、テスト、生成履歴を結合する

## IDの役割

### `spec_id`

意味ASTを識別する既存IDである。同じ意味ASTから生成した複数のコードは、同じ`spec_id`を持つ。

### `style_id`

構造的変種を識別するIDである。確定した`style_spec`を、辞書キー昇順、区切り文字`,`と`:`のJSONへ正規化し、そのSHA-256から決定する。

```text
style-<正規化style_specのSHA-256>
```

候補選択より先に`style_spec`を確定し、その後に`style_id`を計算する。候補を決定的に順位付けする場合は、次の値を使用する。

```text
SHA-256(semantic_hash + "\0" + style_id + "\0" + generator_seed)
```

### `code_id`

同じ意味ASTから生成した個々のコード候補を識別するIDである。異なる`style_spec`から偶然同じコード文字列が生成された場合も、重複除外前の候補を別々に追跡できるようにする。

```text
code-<SHA-256(spec_id + "\0" + style_id + "\0" + rewrite_idの正規化値 + "\0" + reference_code)>
```

`rewrite_id`がない場合はJSONの`null`を正規化値として使う。除外記録、完全重複確認、最終レコードからの逆引きに使用するため、省略しない。コード文字列自体の一致判定には`code_id`ではなく`code_hash`と文字列全体を使用する。

### `record_id`

日本語指示とコードを結合した最終レコードを識別する。

```text
record-<SHA-256(code_id + "\0" + instruction_ja + "\0" + test_suite + "\0" + testsの正規化JSON)>
```

### `family_id`

同じ元問題から派生した`normal`、`paraphrase`、`boundary`を結び付けるIDである。この3集合では同じ値を使用する。

```text
family-<semantic_hash>
```

`family_id`は最終レコードすべてに保存する。同じ意味ASTから派生したレコードは、splitや日本語表現にかかわらず同じ`family_id`を持つ。

## 意味ASTレコード

```json
{
  "spec_id": "combined-000001",
  "semantic_ast": {
    "sequence": [
      {"filter": ["even"]}
    ]
  },
  "split": "train",
  "test_suite": null
}
```

すべての意味ASTレコードで、`spec_id`と`semantic_ast`を必須とする。訓練・検証への分割後と各評価集合のレコードでは`test_suite`も必須とし、訓練・検証では`null`、評価集合では評価集合名を保存する。

意味ASTレコード自体に`semantic_hash`は保存しない。コード候補を作る段階で`semantic_ast`から計算し、コード候補と最終レコードに保存する。

訓練、検証、通常テストへ分割した意味ASTレコードでは`split`も必須とする。組合せ汎化と反復汎化の抽出・生成ファイルでは、`test_suite`がそれぞれ`compositional`、`repetition`であるため、`split: "test"`を重複して保存しない。コード候補を作る段階で、`test_suite`が`null`でなく`split`が省略されている場合に限り、`split: "test"`を設定する。

正式な訓練・検証コード候補は、分割が完了した意味ASTレコードから生成する。分割前の操作一覧である`data/semantic_asts/atomic_semantic_asts.jsonl`を、そのまま正式なコード候補生成の入力には使用しない。

24種類の1操作ASTは、意味ASTの分割方針ですべて訓練へ割り当てられている。そのため、この24件から作る正式なコード候補は`data/semantic_asts/train_semantic_asts.jsonl`内の1操作レコードを入力とし、すべて`split: "train"`、`test_suite: null`とする。ここでの`test_suite: null`は項目の欠落ではなく、訓練用なので評価テスト集合に属さないことを表す。

## コード候補レコード

```json
{
  "code_id": "code-...",
  "spec_id": "combined-000001",
  "semantic_ast": {
    "sequence": [
      {"filter": ["even"]}
    ]
  },
  "reference_code": "def solve(xs: list[int], k: int) -> list[int]:\n    return [x for x in xs if x % 2 == 0]\n",
  "code_style": "expression_comprehension",
  "style_id": "style-...",
  "style_spec": {
    "collection_form": "list_comprehension",
    "temporary_form": "direct_return",
    "name_set": "short",
    "layout": "single_return",
    "comments": "none",
    "local_annotations": false,
    "square_form": null,
    "descending_form": null,
    "reverse_form": null
  },
  "rewrite_id": null,
  "split": "train",
  "test_suite": null,
  "semantic_hash": "...",
  "code_hash": "...",
  "generator_version": "...",
  "generator_seed": 0,
  "verification": {
    "syntax_ok": true,
    "ast_safe": true,
    "signature_ok": true,
    "tests_passed": true,
    "input_unchanged": true,
    "timeout": false
  }
}
```

### `code_style`と`style_spec`

元のデータレコードで要求している`code_style`は残す。`code_style`は集計用の大分類、`style_spec`は詳細な変種情報とする。

`code_style`の初期値は次のいずれかとする。

| `code_style` | 判定条件 | 代表例 |
|---|---|---|
| `expression_comprehension` | 一時変数を使わず、処理結果の式を直接`return`する | `return [x for x in xs if ...]`、`return sorted(xs)`、`return xs[:k]` |
| `staged_comprehension` | 処理結果を一時変数へ代入してから`return`し、通常の`for`ループを使わない | `result = [x for x in xs if ...]`、`result = sorted(xs)`、`result = xs[:k]` |
| `staged_loop` | 処理結果用の一時変数と通常の`for`ループを使う | `result = []`の後に`for`で結果を追加する |
| `mixed` | 複数操作の中で、内包表記と通常の`for`ループの両方を使う | 1段目が内包表記、2段目が通常の`for`ループ |

`expression_comprehension`と`staged_comprehension`の`comprehension`はラベル名の一部だが、現在の判定条件では、内包表記だけでなく`sorted`、`reversed`、スライスによる式も含む。したがって、`code_style`だけから内包表記の使用有無を判断してはいけない。内包表記、通常の`for`ループ、組み込み関数、スライスの区別には`style_spec.collection_form`と`style_spec.operation_styles`を使用する。

`code_style`は集計用の大分類であり、コメント、型注釈、変数名、比較式の左右、`sorted`やスライスの具体的な書き方までは表さない。それらは`style_spec`で確認する。

該当しない変種軸も省略せず`null`にする。

### 候補の採用順序

1. 意味ASTと両立する`style_spec`候補を上限付きで列挙する。
2. `style_spec`から`style_id`を決定する。
3. Pythonコードを生成する。
4. 構文、安全性、シグネチャ、実行結果を検証する。
5. コード文字列の完全重複を除外する。
6. 形式別の偏りを調整する。

処理集計には`candidate_count`、`verified_count`、`deduplicated_count`、`selected_count`を保存する。

## 訓練データの均等選抜

[課題文の「データの検証と選抜」](../../boku1-nano.md#データの検証と選抜)に従い、検証を通過したレコードから単純な均等抽出を行う。基準は次の5項目だけとする。

- 操作数1、2、3
- 各演算子の出現頻度
- コード形式
- 日本語テンプレート
- 1つの意味ASTから採用する例数の上限

課題文の「最大20例など」は上限値の例示であり、20件を固定値にはしない。実行前に`max_records_per_semantic_ast`を設定し、その値をデータ作成条件と集計結果に保存する。

### 数え方

各項目は次の単位で数える。

- 操作数: `semantic_ast.sequence`に含まれる操作の個数で、1、2、3に分類する。
- 演算子: レコードの意味ASTに現れる24種類の単独操作を数える。同じ操作が複数回現れる場合は、その出現回数を数える。
- コード形式: `code_style`の大分類と、`style_spec`に保存した各変種をそれぞれ数える。
- 日本語テンプレート: 日本語指示の生成時に付けたテンプレート識別子ごとに数える。
- 意味AST: `semantic_hash`ごとの採用数を数え、`max_records_per_semantic_ast`を超えないようにする。

コード形式の集計対象には、内包表記・`for`ループ、一時変数、変数名、レイアウト、コメント、ローカル型注釈、降順・逆順の表現を含める。ある意味ASTでは使用できない形式を、不足分を埋めるためだけに生成しない。

### 選抜手順

1. 構文、安全性、シグネチャ、実行時間、長さ、参照インタプリタとの一致を検証する。
2. [完全重複除外方針](code_duplicate_exclusion_policy.md)に従って、完全に同じPythonコードを除外する。
3. `semantic_hash`ごとに候補をまとめ、1つの意味ASTから`max_records_per_semantic_ast`を超える候補を採用しない。
4. 操作数、演算子、コード形式、日本語テンプレートの現在の採用数を集計する。
5. 各分類で採用数が少ない値を含むレコードを優先して、順番に1件ずつ選ぶ。
6. 1件選ぶたびに全分類の採用数を更新し、再び不足している値から選ぶ。
7. 複数候補が同順位の場合だけ、固定seedとレコードのハッシュで順序を決める。

ある分類だけを最初にすべて選び終えてから次の分類を調整すると、後から直せない偏りが生じる。そのため、4分類の集計を毎回更新しながら選ぶ。課題文は4分類間の優先順位を指定していないため、「演算子を常に最優先する」などの固定順位は設けない。

同じ意味ASTのコードと日本語指示を無制限に直積で結合しない。検証・重複除外後に設定した上限へ届かない意味ASTは、得られた件数だけを採用する。意味のないコメントや未承認の変数名を追加して上限まで水増ししない。

### 固有データと学習中の延べ使用回数

[課題文](../../boku1-nano.md#データの検証と選抜)では、操作数1、2、3を「同数にする」ではなく「均等に近づける」としている。

最終的な固有レコード数は、意味ASTの件数だけでは決められない。各意味ASTから得られる検証済みコードの数、日本語指示の承認済みテンプレート、コードの完全重複除外、`max_records_per_semantic_ast`をすべて反映した後に確定する。したがって、意味ASTの件数だけを根拠に「1・2・3操作を同数にできる」または「同数にできない」と事前に断定しない。実際にコードと日本語指示を結合した候補を作り、検証と重複除外を終えた時点の件数を使って、どこまで均等に近づけられるかを判断する。

すべての訓練用意味ASTを最低1回使うことを別の要件にする場合は、その要件を均等抽出とは分けて記録する。課題文の5項目だけから、全意味ASTの使用を必須条件とはしない。

課題文は同じデータを複数epoch使用することを認め、固有トークン数と学習中に見た延べトークン数を分けて報告するよう求めている。そのため、次を混同しない。

1. 完全重複除外と設定した上限を通過した固有訓練レコード
2. 学習中に各固有レコードを使用した延べ回数

固有レコードを複製して別の`record_id`を付けることはしない。学習時に同じ固有レコードを再度使用した場合は、延べ使用回数として記録する。

学習時の各epochまたは固定長の学習区間でも、固有レコードの選抜と同じ4分類を集計し、分布を均等に近づける。ここでも4分類間に固定の優先順位は設けず、各分類で使用回数が少ない値を含むレコードを順番に抽出する。

この均等抽出は訓練データだけに適用する。検証と各テスト集合は固定したレコードを使用し、モデルの成績に合わせて分布や問題を入れ替えない。

### 保存する集計

固有訓練データと学習時の延べ使用回数について、それぞれ次を保存する。

- 操作数1、2、3のレコード数
- 24演算子それぞれの出現回数
- `code_style`と`style_spec`の各値の出現回数
- 日本語テンプレートごとの出現回数
- 意味ASTごとの固有レコード数と延べ使用回数
- 固有トークン数と学習中に使用した延べトークン数

均等化の結果は、完全一致だけでなく、各分類の最小値、最大値、差、比率を記録する。構造上同数にできない場合は、黙って除外せず理由を記録する。

## 最終データレコード

日本語指示と検証済みコードを結合した最終レコードでは、次の項目を必須とする。

```json
{
  "record_id": "record-...",
  "family_id": "family-...",
  "code_id": "code-...",
  "spec_id": "combined-000001",
  "semantic_ast": {},
  "instruction_ja": "整数リストxsから偶数だけを残すsolve関数を書いてください。",
  "reference_code": "def solve(xs: list[int], k: int) -> list[int]:\n    ...\n",
  "tests": [],
  "difficulty": 1,
  "code_style": "expression_comprehension",
  "style_id": "style-...",
  "style_spec": {},
  "rewrite_id": null,
  "split": "train",
  "test_suite": null,
  "dictionary": "train",
  "input_set": "build",
  "instruction_source": "rule",
  "semantic_hash": "...",
  "code_hash": "...",
  "text_hash": "...",
  "teacher_model": null,
  "teacher_revision": null,
  "prompt_hash": null,
  "generator_version": "...",
  "generator_seed": 0,
  "verification": {
    "syntax_ok": true,
    "ast_safe": true,
    "signature_ok": true,
    "tests_passed": true,
    "input_unchanged": true,
    "timeout": false
  }
}
```

## 元の必須項目との対応

| 項目 | 方針 |
|---|---|
| `spec_id` | 必須。意味ASTを識別する |
| `semantic_ast` | 必須。元の意味ASTを変更せず保存する |
| `instruction_ja` | 必須。モデルへ与える日本語指示 |
| `reference_code` | 必須。モデルに生成させる正解Pythonコード |
| `tests` | 必須。内部検証用のケースまたはテストケース参照を保存する |
| `difficulty` | 必須。初期値は意味ASTの操作数1〜3とする |
| `code_style` | 必須。集計用の大分類を保存する |
| `semantic_hash` | 必須。意味ASTの重複確認に使用する |
| `text_hash` | 必須。日本語指示の重複確認に使用する |
| `teacher_model` | 必須。教師未使用時は`null` |
| `teacher_revision` | 必須。教師未使用時は`null` |
| `prompt_hash` | 必須。教師未使用時は`null` |
| `verification` | 必須。各検査結果を保存する |

## 分割とテスト集合

次の項目を最終レコードへ必ず引き継ぐ。

```yaml
split: train | val | test
test_suite: null | normal | paraphrase | compositional | boundary | repetition
dictionary: train | test_only
input_set: build | hidden | boundary
```

- `train`と`val`では`test_suite`を`null`にする
- `paraphrase`では`dictionary`を`test_only`にする
- `normal`と`compositional`では`input_set`を`hidden`にする
- `paraphrase`では`normal`と同じhidden入力を使用する
- `boundary`では`input_set`を`boundary`にする
- `normal`、`paraphrase`、`boundary`では同じ`family_id`を使用する

`tests`は内部検証・評価用であり、通常の学習プロンプトへ含めない。hidden入力を訓練データやモデル入力へ混入させてはいけない。

## 日本語指示と教師情報

ルールベースだけで日本語指示を生成した場合は、教師関係の項目を省略せず`null`にする。

```json
{
  "instruction_source": "rule",
  "teacher_model": null,
  "teacher_revision": null,
  "prompt_hash": null
}
```

教師モデルによる言い換えを使用した場合は、少なくとも次を保存する。

```json
{
  "instruction_source": "teacher",
  "teacher_model": "...",
  "teacher_revision": "...",
  "prompt_hash": "...",
  "teacher_quantization": "...",
  "teacher_library_version": "...",
  "teacher_seed": 0,
  "teacher_generated_at": "...",
  "teacher_sampling": {}
}
```

教師モデルを使用したのに、モデル名、revision、プロンプトのいずれかが不明なレコードは採用しない。

## ハッシュの計算

- `semantic_hash`: `semantic_ast`をキー昇順・区切り文字`,`と`:`のJSONへ正規化し、UTF-8バイト列のSHA-256を計算する
- `code_hash`: 保存する`reference_code`のUTF-8バイト列をそのままSHA-256へ入力する
- `text_hash`: 保存する`instruction_ja`のUTF-8バイト列をそのままSHA-256へ入力する
- `prompt_hash`: 教師へ渡したsystem promptとuser promptを実際の区切り込みで保存し、UTF-8バイト列のSHA-256を計算する

コードと日本語では、ハッシュ計算時だけの空白除去やUnicode置換を行わない。

## 検証結果と不採用記録

`verification`には、`syntax_ok`、`ast_safe`、`signature_ok`、`tests_passed`、`input_unchanged`、`timeout`を保存する。

不採用レコードでは、不採用理由と照合先を`code_id`で記録する。

```json
{
  "code_id": "code-...",
  "spec_id": "combined-000001",
  "code_hash": "...",
  "reason": "test_code_exact_duplicate",
  "matched_code_id": "code-...",
  "matched_spec_id": "combined-000999"
}
```

## 保存ファイル

| ファイル | 内容 |
|---|---|
| `data/code_candidates/single_operation/python_code_candidates.jsonl` | 訓練用1操作の未選抜コード候補 |
| `data/code_candidates/train/two_operation/python_code_candidates.jsonl` | 訓練用2操作の未選抜コード候補 |
| `data/code_candidates/train/three_operation/python_code_candidates.jsonl` | 訓練用3操作の未選抜コード候補 |
| `data/code_candidates/compositional/two_operation/python_code_candidates.jsonl` | 組合せ汎化用2操作のコード候補 |
| `data/code_candidates/compositional/three_operation/python_code_candidates.jsonl` | 組合せ汎化用3操作のコード候補 |
| `data/code_candidates/selected/verified_python_codes.jsonl` | 検証・重複除外・最大件数選抜を通過したコード |
| 各コード候補ディレクトリの`rejected_python_codes.jsonl` | 不採用コードと理由 |
| `data/final/final_dataset_records.jsonl` | 日本語指示とコードを結合した最終レコード |

hidden入力を別管理する場合は、公開またはモデル入力用のファイルへ実データを複製せず、テストケースIDだけを保存する。

## 最終確認

保存前に少なくとも次を機械的に確認する。

1. `spec_id`、`code_id`、`record_id`が、それぞれの対象範囲で一意である。
2. `code_id`からコード候補を、`spec_id`から意味ASTを逆引きできる。
3. 最終レコードに元の必須項目がすべて存在する。
4. 教師未使用時の教師項目が欠落ではなく`null`になっている。
5. `split`と`test_suite`の組み合わせが規定どおりである。
6. `normal`、`paraphrase`、`boundary`が同じ`family_id`を持つ。
7. 各ハッシュを再計算して保存値と照合できる。
8. 採用レコードの全`verification`項目が合格条件を満たす。
9. hidden入力が訓練プロンプトまたは訓練用入力へ含まれていない。
10. 完全重複除外の対象と結果を`code_id`で追跡できる。
