# 日本語指示生成手順書

## 1. 目的

検証済みの意味ASTとPythonコードに、日本語の指示文を付けるための手順を定める。

中心となる作業は、次の3段階である。

1. 24種類の単純操作について、日本語表現の辞書を作る
2. 作成者本人が各表現を確認し、使用する表現を確定する
3. 承認済み辞書の表現を意味ASTの操作順に組み合わせ、訓練データ用の指示文を作る

その後、必要な一部の指示文だけを教師モデルで言い換える。

### 現在の進捗（2026年9月24日）

- [x] Qwen3で24操作それぞれ30件、合計720件の表現候補を生成した
- [x] 終止形と接続形の組として720件を出力した
- [x] 作成者本人が初回候補と追加生成候補を確認した
- [x] 545件の承認済み表現を確定した
- [x] 人手選定により`train=522件`、`test_only=23件`へ分けた
- [x] 承認済み辞書から277,420件のルール生成指示を作成した
- [ ] 必要な一部の指示だけをQwen3で全文言い換えする

候補生成の実行環境、設定、検証結果は、[`japanese_atomic_expression_generation_results.md`](../results/japanese_atomic_expression_generation_results.md)に記録している。

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
uv run --group instruction-generation --python 3.12.12 python scripts/instruction_generation/generate_atomic_expression_candidates.py \
  --config config/qwen_atomic_expression_generation.json \
  --validate-config
```

設定では、実際の読込元を次のローカルディレクトリに固定している。

```text
/home/ono_yusuke/Qwen3-4B-AWQ
```

`config.json`、tokenizerファイル、safetensors重みがこのディレクトリに揃っていることを設定検査で確認する。実生成はCUDA対応環境で行う。

RTX 5090環境で確認済みの実行時バージョンは次のとおりである。`pyproject.toml`の`instruction-generation` dependency groupへ直接依存を固定し、推移依存を`uv.lock`へ記録する。初回実行前に`uv sync --group instruction-generation`で環境を復元する。

| 項目 | バージョン |
|---|---|
| Python | 3.12.12（uv管理版、Tritonのコンパイルに必要なヘッダーを含む） |
| PyTorch | 2.13.0 |
| Transformers | 4.51.3 |
| AutoAWQ | 0.2.9 |
| Accelerate | 1.15.0 |
| Triton | 3.7.1 |

システムのPython 3.12.3には`Python.h`がなく、Tritonの実行時コンパイルに失敗したため使用しない。また、PyTorch 2.6.0はRTX 5090のCUDA capability `sm_120`に対応していない。TransformersはAutoAWQ 0.2.9とのAPI互換性を保つため4.51.3へ固定する。

```bash
uv run --group instruction-generation --python 3.12.12 python scripts/instruction_generation/generate_atomic_expression_candidates.py \
  --config config/qwen_atomic_expression_generation.json
```

Qwen3は`enable_thinking=false`で使用する。標準設定では各操作30件、合計720件の候補を生成する。この30件は各操作で最終的に20件以上を人間承認するための候補母数であり、30件をそのまま採用する目標ではない。

現在の生成設定は、seed `20260923`、`max_new_tokens=2048`、`temperature=0.9`、`top_p=0.95`、`top_k=50`、`repetition_penalty=1.1`、1操作当たり最大20試行である。再試行時も30件を要求し、既存候補と重複しない不足分だけを採用する。1回目で一部操作が目標未達になった場合は、`--resume`で既存候補を保持し、不足操作だけを別seedで追加生成できる。

#### 候補30件の決まり方

各操作の30件は、教師モデルが一度に返した候補から品質順に選んだ30件ではない。生成器は、次の手順で人間確認前の候補を蓄積する。

1. `--existing-review-csv`を指定しない初回は生成済み表現を「なし」として、教師モデルへ30件の生成を要求する。指定した場合は、CSVから現在の`operation_id`に対応する既存表現を取り出し、初回から既存表現一覧として渡す。
2. 応答全体をJSONとして解析する。JSON構造またはキーが不正な場合は、その応答から一件も採用せず、次の試行へ進む。
3. 解析できた各組について、改行、文字数、禁止文字列、終止形と接続形の語尾、終止形と接続形が同一でないことを機械検査する。
4. 検査を通過した組のうち、確認CSVの既存例または今回すでに蓄積した候補と終止形、もしくは終止形・接続形の組が完全一致しないものを、モデルの出力順に追加する。
5. 次の試行では、確認CSVの既存例と、それまでに追加した新規候補をuser promptの「すでに生成済み」の一覧へ入れる。解析失敗または形式検査不合格になった組は、この一覧へ入れない。
6. 蓄積数が30件へ達した時点で、その応答に残りの候補があっても採用を終了する。設定または`--max-attempts-per-operation`で指定した最大試行回数後も30件に届かなければ、目標未達として集計へ記録する。

再試行時も要求件数は不足数ではなく常に30件である。例えば24件を蓄積済みの場合も30件を要求し、既存24件と完全一致せず形式検査を通過した候補を先頭から6件だけ追加する。`--resume`を指定した場合は、前回保存した候補と試行回数を引き継ぎ、同じ方法で不足分を追加する。

この段階の重複判定は文字列の完全一致だけであり、意味的に同じ表現や表面的に近い表現をまとめる処理は行わない。また、機械検査は意味の正しさ、日本語の自然さ、候補間の実質的な多様性を保証しない。したがって、出力される30件は「形式検査と完全一致重複除外を通過して先に蓄積された候補30件」であり、承認済み表現または品質上の上位30件ではない。意味と日本語品質は後続の人間確認で判定する。

既存の確認CSVを除外元として使う場合は、次のように指定する。

```bash
uv run --group instruction-generation --python 3.12.12 python scripts/instruction_generation/generate_atomic_expression_candidates.py \
  --config config/qwen_atomic_expression_generation_every_other.json \
  --operation-id atomic-000024 \
  --existing-review-csv data/instruction_dictionaries/expression_review_approved_v2.csv \
  --overwrite
```

生成器はCSVの`operation_id`で対象操作を対応付けるため、`atomic-000024`の生成には同じIDの行だけを使用する。`review_status`にかかわらず元の終止形・接続形を既存例として扱い、人間修正版があれば修正版も追加する。これらはプロンプトと重複判定にだけ使用し、設定した新規候補の目標数には含めず、出力候補へもコピーしない。CSV先頭にExcel由来の`Column1`行がある場合も、実際の`operation_id`ヘッダーを探して読み込む。

同じ専用出力先に前回の候補がある状態では、`--existing-review-csv`だけを追加しても上書きしない。設定した件数を新たに生成し直す場合は上記のように`--overwrite`を、前回の未達分だけを補う場合は`--resume`を指定する。標準設定は1操作30件だが、特定操作だけの追加生成では`target_candidates_per_operation`を最大100件まで指定できる。`qwen_atomic_expression_generation_every_other.json`では追加生成用に50件を指定している。

操作ごとの最大試行回数は設定JSONの`max_attempts_per_operation`を既定値とし、今回の実行だけ変える場合は`--max-attempts-per-operation`を指定する。例えば`--max-attempts-per-operation 1`では各操作について教師モデルを一度だけ呼び出す。一度の応答から形式検査と重複除外を通過した候補が30件未満なら、追加試行せず、別出力と集計へ実件数および目標未達を記録する。複数の操作だけを一括生成する場合は、`--operation-id`を操作ごとに繰り返して指定する。

既存の候補出力を明示的に置き換えて再生成する場合だけ、次のように`--overwrite`を付ける。

```bash
uv run --group instruction-generation --python 3.12.12 python scripts/instruction_generation/generate_atomic_expression_candidates.py \
  --config config/qwen_atomic_expression_generation.json \
  --overwrite
```

`model_id`、`model_path`、`revision`は別の情報である。

- `model_id`: 生成物へ出典として記録するモデル名。現在値は`Qwen/Qwen3-4B-AWQ`
- `model_path`: Transformersが実際に読み込むローカル重みの絶対パス。現在値は`/home/ono_yusuke/Qwen3-4B-AWQ`
- `revision`: ローカル重みを取得したモデル版を表す40桁のコミットID。現在の固定値は`74d4bd2bd4bff9cafc9345221320bffb08b406a3`

正式生成ではHubからモデルを取得せず、`local_files_only=true`を必須とする。`main`や短縮ハッシュは禁止し、ローカル重みを取得した完全なコミットIDを設定へ残す。保存する`teacher_revision`にはこの固定コミットIDを、集計ファイルの`model_path`には実際の読込元を記録する。

clone先では設定JSONを書き換えず、同じrevisionのモデルを任意の絶対パスへ配置し、`--model-path`でその場所を指定する。

```bash
uv sync --group instruction-generation
uv run --group instruction-generation --python 3.12.12 python \
  scripts/instruction_generation/generate_atomic_expression_candidates.py \
  --config config/qwen_atomic_expression_generation.json \
  --model-path /absolute/path/to/Qwen3-4B-AWQ
```

この指定は今回の実行だけ`model.model_path`を置き換える。モデルID、revision、seed、sampling、prompt、操作定義、生成器バージョンはリポジトリの固定値を使う。実行時に使用した絶対パスもstatsへ記録する。候補生成後の`approved`または`unused`判定は人間による実験工程であり、自動再現の対象には含めない。

非thinkingモードを指定していても、出力に`<think>`または`</think>`タグが一つでも含まれた場合は、その応答全体を拒否する。該当応答は表現候補にも生出力記録にも保存しない。

候補は、同じ意味を持つ終止形と接続形の組にする。

```text
expression_ja: 偶数の要素だけを残す
connective_expression_ja: 偶数の要素だけを残し
```

`expression_ja`は最終操作として文末へ置く動詞基本形、`connective_expression_ja`は後続操作へつなぐ連用形またはて形とする。接続形には読点を含めず、ルール生成器が結合位置に付ける。プロンプトでは個別の禁止文字を列挙せず、「中国語の漢字や中国語表現を使わない」とだけ指示する。生成器も中国語の個別文字リストでは除外せず、採否は人間確認で決める。

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
  "connective_expression_ja": "k以上の要素に絞り込み",
  "review_status": "pending",
  "teacher_model": "Qwen/Qwen3-4B-AWQ",
  "teacher_revision": "...",
  "prompt_hash": "..."
}
```

候補生成時点では、訓練データに使用しない。

2026年9月21日の正式生成結果は、[`japanese_atomic_expression_generation_results.md`](../results/japanese_atomic_expression_generation_results.md)に記録する。

## 4. 手順2: 作成者が表現を確認する

### 4.1 確認画面または一覧を作る

操作ごとに、次の項目を並べて確認できるようにする。

| 項目 | 内容 |
|---|---|
| 操作ID | `atomic-000004`など |
| 意味AST | `{"filter":["ge_k"]}`など |
| 正準な意味 | `k`以上の値だけを残す |
| 終止形候補 | `k`以上の要素に絞り込む |
| 接続形候補 | `k`以上の要素に絞り込み |
| 確認結果 | 承認、修正、不使用 |

確認用の形式は、CSV、スプレッドシート、簡単な確認画面のどれでもよい。確認後はJSONLへ戻せるように、`expression_id`を変更しない。

標準スクリプトは`data/instruction_dictionaries/expression_review.csv`を出力する。終止形を直す場合は`edited_expression_ja`、接続形を直す場合は`edited_connective_expression_ja`へ記入する。使用する行は`review_status`へ`approved`、使用しない行は`unused`を記入する。承認行には`reviewer`と`reviewed_at`も記入する。`dictionary`区分は候補の承認とは別工程で人手選定結果から一括付与するため、この段階では空欄でよい。

### 4.2 確認する内容

各組について、次の4点を確認する。

1. 意味ASTと同じ処理を表しているか
2. 日本語として自然で、単独で意味が分かるか
3. 終止形が基本的に動詞で終わっているか
4. 接続形が同じ意味を保ち、後続操作へ自然につながるか

旧方式の生成では、簡体字・中国語混入、比較境界の意味変更、不自然な日本語が実際に見つかった。今回の720件は生成後の内容検査を行っていないため、機械的に正しいとみなさず、終止形と接続形の両方を人が確認する。

特に、次の意味を混同しないようにする。

- 「`k`より大きい」と「`k`以上」
- 「`k`より小さい」と「`k`以下」
- 「各要素から`k`を引く」と「`k`から各要素を引く」
- 「値を降順に並べる」と「現在の並び順を逆にする」
- 「先頭から`k`個」と「末尾から`k`個」
- 「1個おきに取る」と「偶数だけを取る」

さらに、日本語以外の文字や表現が混ざっていないかを確認する。今回検出した`筛`、`滤`、`负`、`减`、`个`、`项`、`离`のような簡体字、`每个数值减去k`のような中国語、`olan`のような他言語を含む候補は、そのまま承認しない。

修正した表現は、修正後の文をもう一度確認してから承認する。

### 4.3 承認済み辞書を確定する

承認した表現だけを`approved_expressions.jsonl`へ保存する。

```json
{
  "expression_id": "expr-candidate-...",
  "operation_id": "atomic-000004",
  "operation_ast": {"filter": ["ge_k"]},
  "canonical_meaning_ja": "k以上の値だけを残す",
  "must_preserve_ja": "k以上の整数だけを選ぶ。元の要素順は変えない。",
  "expression_ja": "k以上の要素に絞り込む",
  "connective_expression_ja": "k以上の要素に絞り込み",
  "dictionary": "train",
  "dictionary_selection_method": "human_reviewed",
  "human_edited": false,
  "generation_record": {},
  "dictionary_version": "..."
}
```

24操作のそれぞれについて、最終的に10〜30種類の承認済み表現を用意する。足りない場合は追加候補を作り、同じ手順で確認する。

確認後、まず[`publishing_japanese_expression_dictionary.md`](publishing_japanese_expression_dictionary.md)の手順で公開CSVと来歴JSONLを作る。その2ファイルを入力として、次を実行し、承認済み辞書を分割する。

```bash
uv run --python 3.12.12 python scripts/instruction_generation/build_approved_expression_dictionary.py \
  --config config/build_approved_expression_dictionary.json \
  --overwrite
```

### 4.4 訓練用とテスト専用に分ける

承認済み表現は、使用前に次の2辞書へ分ける。

- `train`: 訓練、検証、通常テスト、組合せ汎化テスト、境界値テストで使用する
- `test_only`: 言い換えテストだけで使用する

`test_only`へ入れた表現は、訓練用指示文や訓練用プロンプトへ入れない。

最終承認した545件のうち、作成者が言い換えテスト用として人手選定した23件を`test_only`、残り522件を`train`とする。語句一致、乱数、操作ごとの先頭行などでは自動選定しない。23件の`expression_id`は設定JSONへ固定し、終止形と接続形を常に同じ区分で扱う。

選定表現、辞書外9件との違い、再現手順、検査条件は、[`japanese_paraphrase_test_policy.md`](../policies/japanese_paraphrase_test_policy.md)を正とする。辞書外9件は承認済み545件に混ぜず、`paraphrase_test_external_expressions.jsonl`へ人手作成表現として分離する。候補は23件と9件の合計32件だが、指定表記と異なる旧表現2件を除き、評価採用30件で全24操作を覆う。

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
- 言い換えテスト: 採用した30件の`test_only`表現をそれぞれ対応する単独操作ASTへ1件ずつ割り当てる

選択した`expression_id`は、意味ASTと同じ順番で記録する。

言い換え評価は2・3操作の結合を行わない。表現1件につき1操作の全文指示を1文作るため、合計30文になる。終止形だけを本文に使用し、接続形は辞書情報として保持する。詳細は[`japanese_paraphrase_test_policy.md`](../policies/japanese_paraphrase_test_policy.md)を正とする。

### 5.3 操作順を保って結合する

番号付き指示は生成器のデバッグと意味確認にだけ使用し、最終訓練データには保存しない。最終指示は、最後以外の操作に`connective_expression_ja`、最後の操作に`expression_ja`を使って自然な一文へ結合する。

1操作の場合は終止形を使用する。

```text
整数リストxsから{op1_final}solve関数を書いてください。
```

2操作の場合は、1番目を接続形にする。

```text
整数リストxsから{op1_connective}、{op2_final}solve関数を書いてください。
```

3操作の場合は、最初の二つを接続形にする。読点はルール生成器が必要な結合位置へ付ける。

```text
整数リストxsから{op1_connective}、{op2_connective}、{op3_final}solve関数を書いてください。
```

入力に`k`を使う操作が含まれる場合は、「整数リストxsと整数kを受け取り」など、入力契約と一致する外側テンプレートを選ぶ。操作順と結合はルールベースで固定し、Qwenには任せない。

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

辞書から次の組を選ぶ。

```text
op1 final: k以上の値だけを残す
op1 connective: k以上の値だけを残し
op2 final: 各要素を2倍する
op2 connective: それぞれを2倍して
op3 final: 降順に並べる
op3 connective: 降順に並べて
```

生成する指示文は次のとおりである。

```text
整数リストxsと整数kを受け取り、k以上の値だけを残し、それぞれを2倍して、降順に並べるsolve関数を書いてください。
```

### 5.5 複数の指示文を作る

同じ意味ASTでも、各操作について選ぶ辞書表現を変えることで複数の指示文を作れる。

ただし、辞書内の全表現を無制限に直積で組み合わせない。1つの意味ASTから作る件数の上限を20件とし、固定seed、`spec_id`、正規化意味ASTから決めた直積上の開始位置と歩幅で固有全文を選ぶ。同じ全文は除外し、20件未満しか作れないASTを同じ文で水増ししない。

選択は固定seedを使って再現可能にする。train、validation、normal、compositional、repetitionの13,872意味ASTを対象とし、`train`表現522件だけを使用する。normalの指示は境界値テストでも再利用する。`test_only`を使う言い換えテストは、単独操作だけの30文を作る別工程とする。詳細は[`rule_generated_instruction_policy.md`](../policies/rule_generated_instruction_policy.md)を正とする。

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

生JSONLは277,420件、約287 MiBになったためGitへ直接置かない。固定メタデータで圧縮し、train用192,900件と評価用84,520件の2つのZIPだけをGit管理する。実行件数とハッシュは[`rule_generated_instruction_results.md`](../results/rule_generated_instruction_results.md)に記録する。

## 6. 手順4: 一部だけ教師モデルで言い換える

ルール生成した指示文の一部だけを、Qwen3で文全体として言い換える。

### 6.1 この工程を行う理由

この工程は追加の独自仕様ではなく、[`boku1-nano.md`の「日本語指示の生成」4番](../../boku1-nano.md#日本語指示の生成)にある「一部についてのみ、教師モデルに文全体の言い換えを行わせる」に対応する。

承認済み表現辞書で変化するのは、基本的に「偶数だけを残す／偶数だけを残し」などの各操作部分である。外側の文テンプレートや操作同士の接続方法はルール生成器が作るため、そのままではすべての指示文が似た文型になりやすい。

そこで、一部のルール生成指示についてだけ、次のような文全体の違いを追加する。

- 自然な一文の語順や文型を変える
- 接続形を保ったまま別の自然な接続表現へ変える
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
- 実行結果: [`instruction_paraphrase_generation_results.md`](../results/instruction_paraphrase_generation_results.md)

全文言い換えの元文は、`split=train`かつ`dictionary=train`のルール生成指示だけから選ぶ。validationおよび`test_suite`を持つ全テスト集合は対象にしない。

訓練用9,646意味ASTのそれぞれについて、対応するルール生成指示から10件を重複なしで選び、各元文を1件ずつ全文言い換えする。したがって、言い換え元の合計は次の96,460件である。

```text
9,646意味AST × 10指示 = 96,460元文
```

選択は実行ごとの非決定的な乱数にはしない。固定した`generator_seed`、`spec_id`、`instruction_id`からSHA-256を計算し、意味AST内でハッシュ順が小さい10件を選ぶ。これにより、各意味AST内ではランダム相当の選択を行いながら、同じ入力とseedから同じ96,460件を再現できる。10件未満しかない意味ASTが一つでもあれば生成前に停止する。

Qwenのsamplingは`temperature=0.9`、`top_p=0.8`、`top_k=20`とする。元文1件につき候補1件を要求し、自動採用はしない。実行時は固定選択順の96件を一つのバッチとして処理し、`generator_seed + batch_start`をバッチseedにする。したがって厳密な再現には、入力、モデルrevision、sampling値だけでなく`batch_size=96`も固定する。生成上限は、JSON object内の日本語一文を十分格納できる`max_new_tokens=256`とする。

長時間実行中に中断しても完了済み情報を失わないよう、候補JSONLと生応答JSONLは生成済みレコードを逐次追記し、正常終了時に全件を正規順で書き直す。Qwenが所定JSONの最後の閉じ二重引用符だけを単一引用符にする既知の出力（`']}`）は、先頭schemaと末尾が完全一致する場合だけ`"]}`へ補正する。元の生応答は変更せず保存し、`parse_repaired=true`を記録する。それ以外の不正JSONを推測で修復しない。

`data/instructions/rule_generated_instructions.jsonl`を作成した後、CUDA対応環境で次を実行する。ここでも同じ`/home/ono_yusuke/Qwen3-4B-AWQ`のローカル重みだけを読み込む。

```bash
uv run --group instruction-generation --python 3.12.12 python scripts/instruction_generation/generate_instruction_paraphrase_candidates.py \
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

生成後のファイルは、次の区分で扱う。

- `teacher_paraphrase_raw_responses.jsonl`: Qwenの未変更応答を持つモデル生データ。編集しない
- `teacher_paraphrase_candidates.jsonl`: 生応答を解析・形式検査した候補データ。直接編集しない
- `teacher_paraphrase_review.csv`: 元文と候補を並べた人手レビュー用ファイル。このファイルへ判定を記入する
- `teacher_paraphrase_generation_stats.json`: 実行条件と除外理由の集計。編集しない

詳細な対応関係と実行件数は、[`instruction_paraphrase_generation_results.md`](../results/instruction_paraphrase_generation_results.md#41-どれが生データか)を参照する。

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

- [x] 24種類の操作を一覧化した
- [x] 各操作についてQwen3で表現候補を作った
- [x] 候補を操作別に確認できる一覧へ出力した
- [x] 作成者本人が各表現を確認した
- [x] 各操作について10〜30種類の承認済み表現を確保した
- [x] 承認済み表現を`train`と`test_only`へ分けた
- [x] 辞書のバージョンを固定した

### ルール生成

- [x] 意味ASTから操作列を順番どおりに取り出した
- [x] 各操作に対応する承認済み表現を選んだ
- [x] 2番目以降の操作を「その結果」に適用する形で接続した
- [x] 1つの意味ASTから作る指示数の上限を適用した
- [x] 表現の使用回数が偏っていないことを確認した
- [x] 使用した表現IDとテンプレートIDを保存した

### 教師言い換えと最終結合

- [x] ルール生成指示の一部だけを教師モデルで言い換えた
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
