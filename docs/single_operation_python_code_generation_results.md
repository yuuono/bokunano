# 単一操作のPythonコード候補生成結果

## 実行内容

2026年9月20日に、[`config/python_code_generation.json`](../config/python_code_generation.json)を生成スクリプトから読み、24種類の単一操作ASTごとに検証済み固有コードを20件生成した。日本語指示はまだ生成していない。

```bash
uv run python scripts/generate_python_code_candidates.py \
  --config config/python_code_generation.json
```

## 結果

- 対象の単一操作AST: 24件
- 1 AST当たりの目標: 20件
- 生成・実行検証したコード: 480件
- 参照インタプリタと全入力で一致: 480件
- 完全重複除外後のコード候補: 480件
- 不採用: 0件
- 目標未達: 0 AST

## 参照インタプリタとの照合

480件の各生成コードについて、境界値入力9件と固定seed 0のランダム入力32件の合計41件を実行した。同じ意味AST、`xs`、`k`で参照インタプリタを実行し、戻り値が完全一致することを確認した。

あわせて、次を全コードで確認した。

- `ast.parse`に成功する
- 許可した構文、関数呼び出し、定数だけを使う
- `solve(xs: list[int], k: int) -> list[int]`のシグネチャを守る
- 戻り値が整数だけを含むリストである
- 入力リスト`xs`を変更しない
- 5秒の制限時間内に完了する

## 完全重複の確認範囲

今回生成した480件内で、`code_hash`がすべて異なり、生成コード全文もすべて異なることを確認した。

組合せ汎化テスト側の生成コードとの完全一致比較は、まだ行っていない。その比較は、2操作・3操作の構造的変種を生成した後、日本語指示を作る前に行う。

## 操作別の結果

| `spec_id` | 単一操作 | 列挙可能な変種 | 実行検証 | 検証合格 | 完全重複除外後 |
|---|---|---:|---:|---:|---:|
| `combined-000001` | `{"filter":["even"]}` | 72 | 20 | 20 | 20 |
| `combined-000002` | `{"filter":["odd"]}` | 72 | 20 | 20 | 20 |
| `combined-000003` | `{"filter":["gt_k"]}` | 72 | 20 | 20 | 20 |
| `combined-000004` | `{"filter":["ge_k"]}` | 72 | 20 | 20 | 20 |
| `combined-000005` | `{"filter":["lt_k"]}` | 72 | 20 | 20 | 20 |
| `combined-000006` | `{"filter":["le_k"]}` | 72 | 20 | 20 | 20 |
| `combined-000007` | `{"filter":["multiple_of_k"]}` | 72 | 20 | 20 | 20 |
| `combined-000008` | `{"filter":["positive"]}` | 72 | 20 | 20 | 20 |
| `combined-000009` | `{"filter":["negative"]}` | 72 | 20 | 20 | 20 |
| `combined-000010` | `{"filter":["zero"]}` | 72 | 20 | 20 | 20 |
| `combined-000011` | `{"map":["add_k"]}` | 36 | 20 | 20 | 20 |
| `combined-000012` | `{"map":["sub_k"]}` | 36 | 20 | 20 | 20 |
| `combined-000013` | `{"map":["mul_k"]}` | 36 | 20 | 20 | 20 |
| `combined-000014` | `{"map":["mul_const",2]}` | 36 | 20 | 20 | 20 |
| `combined-000015` | `{"map":["mul_const",3]}` | 36 | 20 | 20 | 20 |
| `combined-000016` | `{"map":["negate"]}` | 36 | 20 | 20 | 20 |
| `combined-000017` | `{"map":["abs"]}` | 36 | 20 | 20 | 20 |
| `combined-000018` | `{"map":["square"]}` | 72 | 20 | 20 | 20 |
| `combined-000019` | `{"order":"ascending"}` | 20 | 20 | 20 | 20 |
| `combined-000020` | `{"order":"descending"}` | 20 | 20 | 20 | 20 |
| `combined-000021` | `{"order":"reverse"}` | 20 | 20 | 20 | 20 |
| `combined-000022` | `{"slice":["take_first_k"]}` | 20 | 20 | 20 | 20 |
| `combined-000023` | `{"slice":["take_last_k"]}` | 20 | 20 | 20 | 20 |
| `combined-000024` | `{"slice":["every_other"]}` | 20 | 20 | 20 | 20 |

## 生成形式の内訳

| 分類 | 値 | 件数 |
|---|---|---:|
| `code_style` | `expression_comprehension`（内包表記・組み込み関数・スライスの結果を直接`return`する形式） | 67 |
| `code_style` | `staged_comprehension`（内包表記・組み込み関数・スライスの結果を一時変数に代入してから`return`する形式） | 255 |
| `code_style` | `staged_loop`（通常の`for`ループで結果を作る形式） | 158 |
| レイアウト | 1行`return` | 67 |
| レイアウト | 複数行 | 413 |
| コメント | なし | 239 |
| コメント | あり | 241 |
| ローカル型注釈 | なし | 269 |
| ローカル型注釈 | あり | 211 |

この内訳は、各ASTで固定seedの順位付けに従い、最初に検証を通過した20件を確保した結果である。最終訓練データの形式分布を確定した結果ではない。

## 出力ファイル

| ファイル | 内容 |
|---|---|
| `data/python_code_candidates.jsonl` | 検証済みコード候補480件 |
| `data/rejected_python_codes.jsonl` | 不採用候補0件 |
| `data/python_code_generation_stats.json` | 設定、全体集計、操作別集計 |

実行時の設定JSONのSHA-256は`a17097c66a148758fa8e87c7c08f97245b48029b5e8c48735444c136fc6287e4`である。
