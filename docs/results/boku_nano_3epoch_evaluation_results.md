# Boku Nano 3エポックモデル評価結果

## 報告対象

2026年9月26日に、3エポック学習済みモデルを固定済みの5テスト、合計84,550件で評価した。本書は、[Boku Nanoモデル評価方針](../policies/boku_nano_model_evaluation_policy.md)に従い、最終テストの集合別成績、不合格内容、診断値、再現条件を報告する。

学習中のvalidation lossは最適化状況を監視する値であり、この最終テストには含めない。学習損失とvalidation lossは[3エポック学習結果](boku_nano_three_epoch_training_results.md)に分離して記録している。

Syntax-valid率、Safe-AST率、Signature-valid率、Executable率、pass@5、GPUメモリ、tokens/s、およびランダム初期モデルとの比較は[追加評価指標・ランダム初期モデル比較結果](boku_nano_evaluation_metrics_and_random_baseline.md)に記録している。

## 結論

| 項目 | 結果 |
|---|---:|
| 評価件数 | 84,550件 |
| 合格 | 84,434件 |
| 不合格 | 116件 |
| 全体参考合格率 | 99.8628% |
| 正常終了 | 84,550件 |
| タイムアウト | 0件 |
| 実行時間 | 940.872秒 |

全体では84,434 / 84,550件が合格した。ただし、テストごとに件数と目的が異なるため、全体合格率は参考値とし、正式な判断には次のテスト別合格率を用いる。

- 通常テスト、組合せ汎化テスト、境界値テストは99.97%以上だった。
- 日本語言い換えテストは80.0000%で、未学習表現30件中6件を解釈できなかった。
- 同一操作の反復テストは99.5530%だったが、不合格116件のうち103件、88.8%を占めた。
- 最優先の改善対象は同一操作の反復、次点は未学習の日本語言い換えである。

## 評価仕様

### テストの名称と目的

文書上の名称は日本語へ統一する。再実行時に指定する内部識別子だけを併記する。

| テスト名 | 内部識別子 | 件数 | 評価対象 | 実行入力 |
|---|---|---:|---|---|
| 通常テスト | `normal` | 24,040 | 訓練に含まれない通常テスト用意味ASTと指示への汎化 | 専用hidden入力64件 |
| 組合せ汎化テスト | `compositional` | 13,400 | 訓練から隔離した5操作対の未知の組合せへの汎化 | 専用hidden入力64件 |
| 日本語言い換えテスト | `paraphrase` | 30 | 訓練に使っていない日本語表現30件の理解 | 単独操作用hidden入力64件 |
| 同一操作の反復テスト | `repetition` | 23,040 | 同じ操作が2回または3回隣接する構造への汎化 | 反復専用hidden入力64件 |
| 境界値テスト | `boundary` | 24,040 | 空、単一要素、極値、重複、`k`境界などへの耐性 | 共通30件と対象filter固有1件 |

通常テストと境界値テストは、同じ意味ASTと日本語指示に異なる実行入力を与える。日本語言い換えテストは単独操作だけを対象とし、組合せ汎化テストや同一操作の反復テストとは評価軸を分離している。

### 合格条件

生成コードが次の条件をすべて満たしたレコードだけを合格とした。

1. Pythonとして構文解析できる。
2. 許可済みのAST、演算、組み込み関数だけを使う。
3. `solve(xs: list[int], k: int) -> list[int]`の固定signatureを持つ。
4. 対応する全hidden入力で参照インタプリタと同じ結果を返す。
5. 入力`xs`を変更せず、整数だけを含むlistを返す。
6. 1生成コードに対する全入力の実行が5秒以内に完了する。

主要指標はテストごとのレコード合格率である。参照コードとの完全文字列一致は、同じ機能を持つ別実装も正解とするため診断値としてのみ扱う。

## テスト別結果

| テスト名 | 合格 | 不合格 | 合格率 | 参照コード完全一致 | EOS終了 | タイムアウト |
|---|---:|---:|---:|---:|---:|---:|
| 通常テスト | 24,038 / 24,040 | 2 | 99.9917% | 25 | 24,040 | 0 |
| 組合せ汎化テスト | 13,397 / 13,400 | 3 | 99.9776% | 13 | 13,400 | 0 |
| 日本語言い換えテスト | 24 / 30 | 6 | 80.0000% | 0 | 30 | 0 |
| 同一操作の反復テスト | 22,937 / 23,040 | 103 | 99.5530% | 23 | 23,040 | 0 |
| 境界値テスト | 24,038 / 24,040 | 2 | 99.9917% | 25 | 24,040 | 0 |
| 合計・参考値 | 84,434 / 84,550 | 116 | 99.8628% | 86 | 84,550 | 0 |

各テストの予定件数と評価済み件数は一致し、全レコードがEOSで正常終了した。最大生成token数到達、context上限到達、タイムアウトによる終了はなかった。

通常テストと境界値テストで失敗した2件は、同じ日本語指示から生成された同じコードである。両テストで別の入力を使って再評価したため、集計上は4件の不合格となる。この重複を除くと不合格生成は114件、失敗した意味仕様は47種類である。

## 操作数別結果

| テスト名 | 操作数 | 合格 | 不合格 | 合格率 |
|---|---:|---:|---:|---:|
| 通常テスト | 2 | 1,078 / 1,080 | 2 | 99.8148% |
| 通常テスト | 3 | 22,960 / 22,960 | 0 | 100.0000% |
| 組合せ汎化テスト | 2 | 198 / 200 | 2 | 99.0000% |
| 組合せ汎化テスト | 3 | 13,199 / 13,200 | 1 | 99.9924% |
| 日本語言い換えテスト | 1 | 24 / 30 | 6 | 80.0000% |
| 同一操作の反復テスト | 2 | 470 / 480 | 10 | 97.9167% |
| 同一操作の反復テスト | 3 | 22,467 / 22,560 | 93 | 99.5878% |
| 境界値テスト | 2 | 1,078 / 1,080 | 2 | 99.8148% |
| 境界値テスト | 3 | 22,960 / 22,960 | 0 | 100.0000% |

## 不合格の内訳

### 失敗形式

| 失敗形式 | 件数 |
|---|---:|
| 実行結果の不一致 | 112 |
| Python構文エラー | 4 |
| タイムアウト | 0 |
| EOS未生成 | 0 |

構文エラー4件は、日本語言い換えテストの偶数・奇数表現で2件、同一操作の反復テストの`ascending → ascending`で2件だった。それ以外は構文、安全性、signature検査を通過したが、hidden入力で参照結果と一致しなかった。

### 通常テスト

不合格は24,040件中2件で、いずれも2操作だった。

| 意味仕様 | 期待操作 | 生成上の誤り |
|---|---|---|
| `combined-000411` | `abs → descending` | 正しい降順処理の後に余分な昇順sortを追加 |
| `combined-000564` | `every_other → add_k` | 正しい2操作の後に`x == 0`フィルタを追加 |

未学習の通常意味ASTに対する汎化はほぼできているが、まれに指示にない処理を追加する。

### 組合せ汎化テスト

不合格は13,400件中3件で、2操作が2件、3操作が1件だった。

| 意味仕様 | 期待操作 | 生成上の誤り |
|---|---|---|
| `combined-000057` | `odd → add_k` | `add_k`を2回適用 |
| `combined-000115` | `ge_k → take_last_k` | `>= k`を`> k`として生成 |
| `combined-002555` | `ge_k → take_first_k → take_last_k` | `>= k`を`> k`として生成 |

未知の操作組合せはほぼ構成できている。残る弱点は、操作の余分な重複と`>=`、`>`の境界比較の取り違えである。

### 日本語言い換えテスト

不合格は30件中6件だった。

| 意味仕様 | 未学習の日本語表現 | 生成上の誤り |
|---|---|---|
| `filter:even` | 2で割り切れる値を残す | 不正な内包表記を生成し構文エラー |
| `filter:even` | 奇数を除く | 意味を反転し、奇数を残した |
| `filter:odd` | 2で割り切れない値を残す | 不正な内包表記を生成し構文エラー |
| `filter:odd` | 偶数を除く | 意味を反転し、偶数を残した |
| `map:square` | その数と自らをかける | 二乗ではなく`value * k`を生成 |
| `slice:take_first_k` | 最初のk個を取り出す | 先頭ではなく末尾`xs[-k:]`を返した |

弱点は、否定表現による偶奇の指定、説明的な二乗表現、先頭と末尾の方向表現である。

評価した30プロンプトは合計438トークンで、未知トークンは0件、未知トークン率は0.0000%だった。したがって、6件の失敗は未知トークンへの置換では説明できず、表現の意味解釈またはコード生成の失敗と判断する。

### 同一操作の反復テスト

不合格は23,040件中103件で、全不合格の88.8%を占めた。反復対象の操作別内訳は次のとおりで、103件すべてを説明する。

| 反復対象の操作 | 不合格レコード | 意味仕様 | 主な誤り |
|---|---:|---:|---|
| `order:descending` | 62 | 18 | 2回目以降を昇順へ変える、または降順を維持できない |
| `order:reverse` | 17 | 8 | 3回反転を2回へ短縮し、元順序へ戻す |
| `slice:every_other` | 8 | 3 | 3回適用すべきところを2回で止める |
| `filter:lt_k` | 7 | 5 | 2回目を`ge_k`など反対条件へ変える |
| `slice:take_last_k` | 4 | 1 | 前段の`ge_k`を`gt_k`へ変える |
| `order:ascending` | 3 | 2 | 余分な括弧による構文エラー、または反復の崩れ |
| `slice:take_first_k` | 2 | 1 | 同じsliceの反復を維持できない |

意味的に等価な簡略化は合格になる機能評価だが、これら103件は簡略化後の結果が参照結果と一致しなかった。特に順序操作の反復回数を保つ能力が弱い。

代表例は次のとおりである。

- `descending → descending`で、1回目は降順、2回目を昇順として生成し、最終結果が昇順になった。
- `reverse → reverse → reverse`で反転を2回しか生成せず、期待される逆順ではなく元順序を返した。
- `every_other → every_other → every_other`で2回しか適用せず、8要素おきではなく4要素おきになった。
- `lt_k → lt_k`で2回目を`k <= x`へ反転し、結果を空にした。

### 境界値テスト

不合格は24,040件中2件で、通常テストと同じ`combined-000411`、`combined-000564`だった。境界値入力だけで新たに失敗したレコードはなく、通常入力からの性能低下もなかった。

## 改善優先順位

1. 同一操作の反復を優先する。特に降順、現在順反転、先頭から1個おきの切り出しについて、2回・3回の操作を途中で別操作へ変えたり省略したりしない訓練例を補う。
2. 日本語言い換えを改善する。評価表現そのものは訓練へ混入させず、否定による偶奇、二乗の説明、先頭・末尾を表す別の未重複表現を訓練側へ追加する。
3. `>=`と`>`の比較境界、および指示にない処理を追加しないことを補強する。

通常テスト、組合せ汎化テスト、境界値テストは高水準であり、改善効果の確認では全体合格率よりも、日本語言い換えテストと同一操作の反復テストの個別合格率を優先する。

## 再現条件

| 項目 | 固定値 |
|---|---|
| 学習状態 | `training_manifest.json`の`status: completed`、3エポック |
| モデル | `data/models/boku_nano_bpe_2048` |
| モデルSHA-256 | `5623f066cc47ef58790e56d5a62fe9a258d502569995a7aff6c65558c622cf0e` |
| tokenizer SHA-256 | `6840a392e8fcae1083be06842774fa912a1797217c7033944ba2d87f1c227293` |
| 評価ZIP SHA-256 | `5b05b76202920f532cb379481d1cfab4adad74e936bdff518cb8b1750b33f0a1` |
| 評価設定SHA-256 | `a17c9e51f4beda44aeaeda04f7805204926b46c645dd8586ec0ea62bfe480e17` |
| prompt | `<|bos|><|task|>\n{instruction_ja}\n<|code|>\n` |
| decoding | samplingなしのgreedy decoding |
| 最大生成長 | 160トークン |
| context length | 256トークン |
| batch / buffer | 64 / 1,024 |
| 計算 | CUDA、bfloat16 |
| 実行環境 | Python 3.12.12、PyTorch 2.13.0+cu130 |
| 評価器 | version 1 |

評価の前後で評価ZIPのSHA-256が一致しており、評価データは変更されていない。

### 固定入力

| テスト名 | テスト集合ID | 入力SHA-256 |
|---|---|---|
| 通常テスト | `normal-hidden-v1-seed-2026092602-cases-64` | `303b4d412910bb663a0faa2320ef2bec4f28cbeb6a464d370ddd5370fc6cda73` |
| 組合せ汎化テスト | `compositional-hidden-v1-seed-2026092603-cases-64` | `b208f78d8d99011a5ce158e9ee4275fb763a2a68db28ec5f3eaef9cc0af9a951` |
| 日本語言い換えテスト | `paraphrase-hidden-v1-seed-2026092604-cases-64` | `2880b2b834bc157261543b66c4f334acfeb8a3e96ca4aadbce40b265c1943c83` |
| 同一操作の反復テスト | `repetition-hidden-v1-seed-2026092605-cases-64` | `60510519431c68cbafa4ec591293e865a335db4dad7fc271f4a2cafb5d77ab33` |
| 境界値テスト | `boundary-v1-shared-30-plus-filter-targeted` | `8def08f589f58b03cf87c9eaea9d7fdcfec71d90d0de9508058a93bb89fa9a39` |

## 同一操作の反復テストで失敗した全仕様

| 仕様ID | 不合格 | 操作列 |
|---|---:|---|
| `repetition-001149` | 9 | `reverse → reverse → reverse` |
| `repetition-000020` | 8 | `descending → descending` |
| `repetition-000906` | 8 | `ge_k → descending → descending` |
| `repetition-000904` | 6 | `gt_k → descending → descending` |
| `repetition-000908` | 6 | `lt_k → descending → descending` |
| `repetition-001152` | 6 | `every_other → every_other → every_other` |
| `repetition-001148` | 5 | `descending → descending → descending` |
| `repetition-000922` | 4 | `sub_k → descending → descending` |
| `repetition-001044` | 4 | `ge_k → take_last_k → take_last_k` |
| `repetition-000899` | 3 | `descending → descending → even` |
| `repetition-000900` | 3 | `even → descending → descending` |
| `repetition-000912` | 3 | `multiple_of_k → descending → descending` |
| `repetition-000930` | 3 | `negate → descending → descending` |
| `repetition-000019` | 2 | `ascending → ascending` |
| `repetition-000250` | 2 | `take_first_k → lt_k → lt_k` |
| `repetition-000254` | 2 | `every_other → lt_k → lt_k` |
| `repetition-000910` | 2 | `le_k → descending → descending` |
| `repetition-000914` | 2 | `positive → descending → descending` |
| `repetition-000916` | 2 | `negative → descending → descending` |
| `repetition-000924` | 2 | `mul_k → descending → descending` |
| `repetition-000936` | 2 | `ascending → descending → descending` |
| `repetition-000948` | 2 | `odd → reverse → reverse` |
| `repetition-000998` | 2 | `ge_k → take_first_k → take_first_k` |
| `repetition-000216` | 1 | `ge_k → lt_k → lt_k` |
| `repetition-000235` | 1 | `lt_k → lt_k → mul_const:3` |
| `repetition-000244` | 1 | `ascending → lt_k → lt_k` |
| `repetition-000878` | 1 | `mul_k → ascending → ascending` |
| `repetition-000919` | 1 | `descending → descending → add_k` |
| `repetition-000923` | 1 | `descending → descending → mul_k` |
| `repetition-000935` | 1 | `descending → descending → ascending` |
| `repetition-000950` | 1 | `gt_k → reverse → reverse` |
| `repetition-000954` | 1 | `lt_k → reverse → reverse` |
| `repetition-000956` | 1 | `le_k → reverse → reverse` |
| `repetition-000958` | 1 | `multiple_of_k → reverse → reverse` |
| `repetition-000980` | 1 | `square → reverse → reverse` |
| `repetition-000989` | 1 | `reverse → reverse → every_other` |
| `repetition-001088` | 1 | `gt_k → every_other → every_other` |
| `repetition-001124` | 1 | `reverse → every_other → every_other` |
| 合計 | 103 | 38意味仕様 |

## 成果物

| 内容 | パス |
|---|---|
| 全体実行記録 | `data/evaluations/boku_nano_bpe_2048/evaluation_manifest.json` |
| 通常テスト生結果 | `data/evaluations/boku_nano_bpe_2048/normal_results.jsonl` |
| 組合せ汎化テスト生結果 | `data/evaluations/boku_nano_bpe_2048/compositional_results.jsonl` |
| 日本語言い換えテスト生結果 | `data/evaluations/boku_nano_bpe_2048/paraphrase_results.jsonl` |
| 同一操作の反復テスト生結果 | `data/evaluations/boku_nano_bpe_2048/repetition_results.jsonl` |
| 境界値テスト生結果 | `data/evaluations/boku_nano_bpe_2048/boundary_results.jsonl` |

生結果の各不合格レコードには、`record_id`、`spec_id`、生成コード、最初に失敗した入力、期待値、実値を保存している。hidden入力を公開文書へ複製せず、詳細調査はローカルの生結果で行う。
