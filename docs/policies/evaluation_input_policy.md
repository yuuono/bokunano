# 評価入力の生成・分離方針

## 目的

validation、通常テスト、言い換えテスト、組合せ汎化、反復汎化、境界値テストで使用する`xs`と`k`を、訓練コード検証入力から分離して決定的に生成する。評価入力は最終レコードの`tests`からIDで参照し、学習プロンプトへ含めない。

## 入力条件

すべての入力は参照インタプリタの公開仕様に従う。

- `xs`は長さ0〜20の整数リスト
- `xs`の各値は-100〜100
- `k`は1〜10
- 参照実行後も呼出し元の`xs`が変更されない
- 参照出力は整数リスト

## 6集合

| 集合 | `split` | `test_suite` | `input_set` | ケース数・方式 |
|---|---|---|---|---|
| validation | `val` | `null` | `build` | seed `2026092601`の層化ランダム64件 |
| normal | `test` | `normal` | `hidden` | seed `2026092602`の層化ランダム64件 |
| compositional | `test` | `compositional` | `hidden` | seed `2026092603`の層化ランダム64件 |
| paraphrase | `test` | `paraphrase` | `hidden` | seed `2026092604`の単独操作用層化ランダム64件 |
| repetition | `test` | `repetition` | `hidden` | seed `2026092605`の層化ランダム64件 |
| boundary | `test` | `boundary` | `boundary` | 共通境界30件と抽出AST固有ケース |

validationはvalidation loss監視と生成コードの調整用なので`input_set=build`とする。ただし、訓練コード候補の作成時に使った41件とは完全一致させない。normal、compositional、paraphrase、repetitionはそれぞれ別のhidden集合を持ち、同じ入力対を集合間で共有しない。

反復汎化では、すでに生成した全文指示と同じく訓練用表現辞書を使う。新しい日本語表現を評価軸にせず、専用hidden入力によって同一操作を隣接反復する意味構造だけを評価する。

## 層化ランダム入力

各ランダム集合は固定seedで長さ2〜20、値-100〜100、`k` 1〜10の候補を作る。空リストと1要素はboundaryへ分離する。

単純な一様乱数だけにせず、採用順に次の8特徴を循環させる。

1. 0、負数、正数を含む
2. `k-1`、`k`、`k+1`を含む
3. `k`の正負の倍数と非倍数を含む
4. 重複値を含む
5. -100と100を含む
6. 偶数・奇数・正負を含む
7. 入力がすでに昇順
8. 入力がすでに降順

生成した5集合のケースは、訓練コード検証で使用した境界9件＋seed 0のランダム32件、および先に生成した評価集合と`xs`・`k`の完全一致がない場合だけ採用する。

## 境界値入力

boundaryはnormalと同じ1,202意味ASTを使用し、日本語指示と正解コードもnormalから再利用する。違いは実行入力だけにする。

### 共通境界30件

全normal ASTへ次の種類を共通に適用する。

- 空リスト
- 1要素
- 長さ20
- `k=1`と`k=10`
- リスト長が`k`の直前・同値・直後
- 全要素0、全要素同値、正数のみ、負数のみ
- 値域の下限-100と上限100
- 昇順、降順、回文、重複、偶奇、0混在
- 全要素が`k`の倍数、全要素が非倍数

### 抽出AST固有ケース

normal意味ASTに`filter`が含まれる場合は、共通30件に加えて意味ASTごとに一件を作る。最初の`filter`より前の非抽出操作を適用した結果が非空で、その`filter`を適用すると全要素が除外されることを参照インタプリタで確認する。

候補は仕様内の1要素入力とし、`spec_id`、入力値、`k`から作るSHA-256順で探索する。build入力、各ランダム評価集合、共通境界との完全一致を避ける。ASTごとに意味が異なるため、異なるASTの固有ケース同士は同じ`xs`・`k`でもよい。`filter`を含まないASTにはこのケースを付けない。

前段操作の結果によって最初の`filter`がすべての到達可能要素を必ず通過させる場合は、全要素不合格ケースを作れない。例えば「二乗→符号反転→`k`未満抽出」ではfilter直前が常に0以下で、`k`は1以上なので必ず通過する。この場合は不可能な入力を捏造せず、-100〜100の全1要素入力と`k=1〜10`を探索したこと、対象filter、理由を`unreachable_filter_asts`へ保存する。固有ケース数と到達不能記録数の合計をfilter含有AST数と一致させる。

## 期待出力

同じ入力でも意味ASTによって期待出力が異なるため、入力manifestへ全AST分の期待出力を複製しない。評価時に`reference_interpreter.py`へ意味AST、`xs`、`k`を渡して期待出力を計算する。

生成時には次を全件実行して確認する。

- validation 1,202 AST × 64入力
- normal 1,202 AST × 64入力
- compositional 670 AST × 64入力
- paraphrase 24単独操作AST × 64入力
- repetition 1,152 AST × 64入力
- boundary 1,202 AST × 共通30入力
- boundaryの抽出AST × 各固有入力1件

## 保存先

```text
data/evaluation_inputs/
├── validation_inputs.json
├── normal_hidden_inputs.json
├── compositional_hidden_inputs.json
├── paraphrase_hidden_inputs.json
├── repetition_hidden_inputs.json
├── boundary_inputs.json
└── evaluation_input_stats.json
```

各manifestには`test_set_id`、分割、`test_suite`、`input_set`、生成器版、seed、ケースID、`xs`、`k`、特徴タグを保存する。boundaryには共通ケースとAST固有ケースを分けて保存する。

## 再現方法

```bash
uv run --python 3.12.12 python \
  scripts/validation/generate_evaluation_input_sets.py \
  --config config/evaluation_input_generation.json
```

再生成時は設定、意味AST、訓練コード検証入力のSHA-256を記録し、処理前後で入力が変わっていないことを確認する。
