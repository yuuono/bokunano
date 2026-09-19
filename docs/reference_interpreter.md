# 参照インタプリタ

## 目的

意味ASTが表す処理を直接実行し、正しい出力を計算する参照インタプリタを作成した。

参照インタプリタは `reference_interpreter.py` に実装している。入力として意味AST、整数リスト `xs`、整数 `k`を受け取り、結果の整数リストを返す。

参照インタプリタは、学習対象となるPythonコードの生成器とは実装経路を分離している。コード文字列やPython ASTを生成せず、`eval`、`exec`、`compile`も使用しない。コード生成器のテンプレート、操作対応表、補助関数は共有せず、意味ASTから値を直接計算する。

生成対象の`solve`関数では、import、属性アクセス、`while`、Python組み込み関数`map`などを許可しない。参照側では、これら生成対象外の仕組みを利用して要素の選択、集約、順序変更、切り出しを実行する。参照側で使用した表現を理由に、学習用コードの候補を除外することはない。

代表的な実装経路の違いは次のとおりである。

| 操作 | 参照インタプリタ | 生成コードで使用できる表現の例 |
|---|---|---|
| 抽出 | `itertools.compress`、Python組み込み関数`map`、`operator` | 内包表記、`for`ループ、条件式 |
| 変換 | 複数イテラブルを受け取るPython組み込み関数`map`、`operator` | 内包表記、`for`ループ、算術式 |
| 昇順 | `heapify`後に`heappop`を反復 | `sorted` |
| 降順 | 符号反転、`heapify`、`heappop` | `sorted(..., reverse=True)`、`sorted(...)[::-1]` |
| 現在順の反転 | `deque.pop` | `[::-1]`、`reversed` |
| 先頭・1個おき | `itertools.islice` | スライス |
| 末尾`k`個 | `deque(maxlen=k)` | `[-k:]` |

`heapq.nsmallest`と`heapq.nlargest`は、要素数と取得数が等しい場合に内部で`sorted`へ委譲するため使用しない。参照側では、`heapify`したヒープが空になるまで`heappop`を繰り返す。

`operator.add`と`+`のような基本整数演算は、同じPython整数演算に基づく信頼プリミティブとして扱う。`operator`の使用目的は、生成コードと関数や式テンプレートを共有せず、参照側の集約処理を`compress`やPython組み込み関数`map`で構成することである。独立性は主に、要素の選択、集約、順序、境界、操作列の適用経路で確保する。

```python
from reference_interpreter import interpret

semantic_ast = {
    "sequence": [
        {"filter": ["ge_k"]},
        {"map": ["mul_const", 2]}
    ]
}

result = interpret(semantic_ast, [1, 3, 5], 3)
assert result == [6, 10]
```

`sequence`内の操作は、配列の先頭から順番に実行する。入力された`xs`は変更せず、新しいリストを結果として返す。

## 24個の操作

参照インタプリタは、`data/atomic_semantic_asts.jsonl`で定義した次の24操作に対応している。

| 分類 | 意味ASTのキー | 対応する操作 |
|---|---|---|
| 抽出 | `filter` | `even`、`odd`、`gt_k`、`ge_k`、`lt_k`、`le_k`、`multiple_of_k`、`positive`、`negative`、`zero` |
| 変換 | `map` | `add_k`、`sub_k`、`mul_k`、`mul_const 2`、`mul_const 3`、`negate`、`abs`、`square` |
| 並べ替え | `order` | `ascending`、`descending`、`reverse` |
| 切り出し | `slice` | `take_first_k`、`take_last_k`、`every_other` |

`ascending`と`descending`は値を基準に並べ替える。`reverse`は値を比較せず、現在のリストの順序を反転する。

`take_first_k`は先頭から最大`k`個、`take_last_k`は末尾から最大`k`個を取得する。リストの長さが`k`より短い場合は、リスト全体を返す。`every_other`は位置0、2、4、……の要素を取得する。

## 入力条件

参照インタプリタは次の入力条件を確認する。

- `xs`は長さ0〜20のリスト
- `xs`の各要素は−100〜100の整数
- `k`は1〜10の整数

意味AST内の変換によって、途中の値や出力値が−100〜100を超えることは許可する。−100〜100という制限は、関数へ最初に渡す`xs`に対する条件である。

## 矛盾・冗長なAST

矛盾するASTや冗長なASTも訓練候補に残す方針のため、参照インタプリタでは除外しない。

例えば、次のASTは常に空リストを返すが、通常の意味ASTとして実行する。

```json
{
  "sequence": [
    {"filter": ["even"]},
    {"filter": ["odd"]}
  ]
}
```

同様に、`ascending`の後に`descending`を行うような冗長なASTも、そのまま順番に実行する。

## 実行確認

確認プログラム `scripts/verify_reference_interpreter.py` を作成した。

最初にPython構文木を検査し、4個の操作ハンドラが規定した参照経路を使用していることを確認する。内包表記、スライス、ラムダ、直接の算術演算子、`sorted`、`reversed`、`abs`、`heapq.nsmallest`、`heapq.nlargest`が操作ハンドラへ入った場合は検証を失敗させる。

その後、24個の単独操作について、あらかじめ定義した期待結果と参照インタプリタの出力が一致することを確認する。また、1〜3操作を組み合わせた12,720件すべてについて、8種類の入力を使って次を確認する。

- 例外が発生せず実行できる
- 出力が整数リストになる
- 入力された`xs`を変更しない
- 操作数別の件数が24件、552件、12,144件になる

実行方法は次のとおりである。

```bash
python3 scripts/verify_reference_interpreter.py
```

実行確認の結果、24個の単独操作はすべて期待結果と一致した。また、組み合わせASTは次の全件を実行できた。

| 操作数 | 確認件数 |
|---|---:|
| 1個 | 24 |
| 2個 | 552 |
| 3個 | 12,144 |
| 合計 | 12,720 |
