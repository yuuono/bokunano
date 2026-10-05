# 条件A：Boku1-nanoとQwen3-0.6Bが失敗した例

2026年10月5日の保存済み実測を整理。条件Aは、同じ自然な日本語から両モデルがそれぞれ直接Pythonコードを生成する比較。CNL変換・補正は挟まない。本書は条件Aだけを扱う。モデルの再生成や採点条件の変更は行っていない。

Boku1-nanoは15M・1 epoch（15,735,168 parameters）、Qwen3-0.6BはONNX q4f16。両者ともWebGPU・greedy・T=0・1問1候補・会話履歴なし。Webデモ既定の5Mモデルの成績ではない。

## 1. 結果の見取り図

| 結果 | 問題数 |
| --- | ---: |
| 両モデルとも合格 | 10 |
| Boku1-nanoだけが不合格 | 9 |
| Qwen3-0.6Bだけが不合格 | 20 |
| 両モデルとも不合格 | 11 |

**Boku1-nanoは30/50合格・20問不合格、Qwen3-0.6Bは19/50合格・31問不合格。** 少なくとも片方が不合格の全40問を以下に掲載する。同じ11問で両方が不合格なので、モデル別不合格件数の合計は51件となる。

「不合格」は、固定した関数契約・許可構文・全179入力の検査を通らなかったという意味。別のプロンプトでも絶対に解けないという主張ではない。Qwenの3例（C04-03、C04-05、C10-03）は反転処理自体が正しく、引数契約や採点器の制限による不合格として区別する。

### モデルごとに目立った誤り

- **Boku1-nano:** 指示にないkによる抽出を加える、操作を余分に繰り返す、新しい言い回しから別操作を生成する。C10の言い換え5問はすべて不合格だった。
- **Qwen3-0.6B:** 複数操作の省略、反復回数の無視、先頭と末尾の混同。3操作と反復は各5問とも不合格。一方、基本的な値の変換は5問とも合格した。
- **両モデル共通:** k以上／未満／以下の境界や、絶対値を「0からの距離」と表した問題で失敗した。

これらは生成コードから観察した傾向であり、学習過程などの内部原因を特定したものではない。

### すぐ確認できる代表例

| 指示の要点 | Boku1-nano | Qwen3-0.6B | 詳細 |
| --- | --- | --- | --- |
| 各要素にkを足す | 先にkより大きい値を抽出してしまう | 合格 | [C03-01](#dev-c03-01) |
| 符号を反転する | 反転した後に二乗してしまう | 合格 | [C03-04](#dev-c03-04) |
| 奇数抽出→3倍→昇順 | 合格 | 3倍を省略し降順にする | [C07-01](#dev-c07-01) |
| kを足す操作を3回 | 合格 | 1回しか足さない | [C08-02](#dev-c08-02) |
| k以上を残す | kと等しい値を落とす | kと等しい値を落とす | [C02-02](#dev-c02-02) |
| 0からの距離に置き換える | 負の値だけ残して2倍 | k倍 | [C10-02](#dev-c10-02) |
| 今の順序を反転する | 合格 | 処理は正しいがk引数を欠く | [C04-03](#dev-c04-03) |

### 不合格理由（最初に検出された理由で集計）

| 理由 | Boku1-nano | Qwen3-0.6B |
| --- | ---: | ---: |
| 実行結果の不一致 | 16 | 19 |
| 関数契約・許可構文の検査で拒否 | 3 | 8 |
| Python構文エラー | 1 | 0 |
| 実行時例外 | 0 | 3 |
| 入力リストを変更 | 0 | 1 |

Bokuの「関数契約・許可構文」3件は未定義変数の検出。Qwenの同分類8件は引数不足3件、許可外の呼出し3件、lambda使用2件。許可外と判定されたコードには意味誤りも含まれ得るが、実行しなかったものに実測出力は付けない。

### 分類別の不合格数（各5問）

| 分類 | Boku1-nano | Qwen3-0.6B |
| --- | ---: | ---: |
| C01 基本的な抽出 | 1 | 1 |
| C02 kを使う条件 | 4 | 4 |
| C03 値の変換 | 3 | 0 |
| C04 順序の変更 | 0 | 5 |
| C05 切り出し | 4 | 3 |
| C06 2操作の合成 | 1 | 2 |
| C07 3操作の合成 | 1 | 5 |
| C08 同じ操作の反復 | 1 | 5 |
| C09 順序を取り違えやすい合成 | 0 | 4 |
| C10 未学習の言い回し | 5 | 2 |

## 2. プロンプトと採点の読み方

各問題の「日本語指示」は両モデルへ渡した共通部分。Bokuには専用の入出力形式、Qwenにはsolve(xs, k)・入力非破壊・許可構文などを指示するsystem messageとチャットテンプレートが付く。完全に同じ文字列のプロンプトではない。[実際の共通プロンプトと生成設定](dev50_20261005_results.md#4-実際のプロンプト)および各問のリンク先で、テンプレート適用後の全文を確認できる。

正解は保存済みの意味ASTを参照インタプリタで実行した値。各問179入力（境界・固定seedランダム・k条件・順序検査）を使用し、すべて一致した場合に合格とした。コードの文字列一致では採点していない。

以下の生成コードは採点対象として抽出したコード（単一のMarkdownフェンスを除去したもの）。修理や意味の補正はしていない。「読み取り」はコード読解による説明、「実測」は採点記録からの転記を表す。失敗入力は最初に検出されたものなので、両モデルで異なる場合がある。静的検査で止まった例には実測反例がない。

## 3. Boku1-nanoだけが不合格：9問

| 問題 | 指示 |
| --- | --- |
| [dev-C02-05](#dev-c02-05) | 整数リストxsと整数kが与えられます。kの倍数だけを選び出す処理をするsolve(xs, k)を作成し、結果をリストで返してください。 |
| [dev-C03-01](#dev-c03-01) | 整数リストxsと整数kが与えられます。各要素にkを足す処理をするsolve(xs, k)を作成し、結果をリストで返してください。 |
| [dev-C03-02](#dev-c03-02) | 整数リストxsと整数kが与えられます。各項目からkを引く処理をするsolve(xs, k)を作成し、結果をリストで返してください。 |
| [dev-C03-04](#dev-c03-04) | 整数リストxsが与えられます。値の符号を逆転する処理をするsolve(xs, k)を作成し、結果をリストで返してください。 |
| [dev-C05-01](#dev-c05-01) | 整数リストxsと整数kが与えられます。先頭k個を選ぶ処理をするsolve(xs, k)を作成し、結果をリストで返してください。 |
| [dev-C05-04](#dev-c05-04) | 整数リストxsと整数kが与えられます。頭k個を抜き出す処理をするsolve(xs, k)を作成し、結果をリストで返してください。 |
| [dev-C10-01](#dev-c10-01) | 整数リストxsを処理するsolve(xs, k)を作ってください。値を2で割った余りが0になる要素だけを、出てきた順のまま選び出す処理を行い、結果のリストを返してください。 |
| [dev-C10-04](#dev-c10-04) | solve(xs, k)をお願いします。整数リストxsについて、左端から数えてk番目までにある要素を、今の順番で取り出す。要素がk個に満たなければ全部を取り出す。結果をリストで返してください。 |
| [dev-C10-05](#dev-c10-05) | 整数リストxsを処理するsolve(xs, k)を作ってください。どの要素についても、その値から同じ整数kを差し引いた値に置き換える処理を行い、結果のリストを返してください。 |

### dev-C02-05

**日本語指示（原文）**

````text
整数リストxsと整数kが与えられます。kの倍数だけを選び出す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsと整数kを受け取り、kの倍数だけを残すsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c02-05)

#### Boku1-nano：不合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = [value for value in xs if k < value]
    result = [value for value in result if value % k == 0]
    return result
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: 倍数判定の前に、指示にない「kより大きい値だけ残す」を加える。0や負の倍数を落とす。

- 実測入力: `xs=[0]`, `k=1`
- 期待値: `[0]`
- 実際値: `[]`

#### Qwen3-0.6B：合格

````python
def solve(xs, k):
    result = []
    for num in xs:
        if num % k == 0:
            result.append(num)
    return result
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

### dev-C03-01

**日本語指示（原文）**

````text
整数リストxsと整数kが与えられます。各要素にkを足す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsと整数kを受け取り、各要素にkを加えるsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c03-01)

#### Boku1-nano：不合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = [value for value in xs if k < value]
    output: list[int] = []
    for value in result:
        output += [value + k]
    return output
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: 加算前に、指示にない「kより大きい値だけ残す」を加える。

- 実測入力: `xs=[0]`, `k=1`
- 期待値: `[1]`
- 実際値: `[]`

#### Qwen3-0.6B：合格

````python
def solve(xs, k):
    return [num + k for num in xs]
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

### dev-C03-02

**日本語指示（原文）**

````text
整数リストxsと整数kが与えられます。各項目からkを引く処理をするsolve(xs, k)を作成し、結果をリストで返してください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsと整数kを受け取り、各要素からkを引くsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c03-02)

#### Boku1-nano：不合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = [value for value in xs if k < value]
    output: list[int] = []
    for value in result:
        output += [value - k]
    return output
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: 減算前に、指示にない「kより大きい値だけ残す」を加える。

- 実測入力: `xs=[0]`, `k=1`
- 期待値: `[-1]`
- 実際値: `[]`

#### Qwen3-0.6B：合格

````python
def solve(xs, k):
    result = []
    for num in xs:
        result.append(num - k)
    return result
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

### dev-C03-04

**日本語指示（原文）**

````text
整数リストxsが与えられます。値の符号を逆転する処理をするsolve(xs, k)を作成し、結果をリストで返してください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsから各要素の符号を反転するsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c03-04)

#### Boku1-nano：不合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = []
    for value in xs:
        result += [-value]
    output: list[int] = []
    for value in result:
        output += [value * value]
    return output
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: 符号を反転した後に、指示にない二乗を行う。

- 実測入力: `xs=[1]`, `k=1`
- 期待値: `[-1]`
- 実際値: `[1]`

#### Qwen3-0.6B：合格

````python
def solve(xs, k):
    result = []
    for num in xs:
        result.append(-num)
    return result
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

### dev-C05-01

**日本語指示（原文）**

````text
整数リストxsと整数kが与えられます。先頭k個を選ぶ処理をするsolve(xs, k)を作成し、結果をリストで返してください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsと整数kを受け取り、先頭からk個を取るsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c05-01)

#### Boku1-nano：不合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = [value for value in xs if k < value]
    result = result[0:k]
    return result
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: 先頭k個の取り出し前に、指示にないkより大きい値の抽出を行う。

- 実測入力: `xs=[0]`, `k=1`
- 期待値: `[0]`
- 実際値: `[]`

#### Qwen3-0.6B：合格

````python
def solve(xs, k):
    return xs[:k]
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

### dev-C05-04

**日本語指示（原文）**

````text
整数リストxsと整数kが与えられます。頭k個を抜き出す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsと整数kを受け取り、先頭からk個を取るsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c05-04)

#### Boku1-nano：不合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = [value for value in xs if k < value]
    output: list[int] = list(reversed(result))
    result = []
    for value in output:
        result += [value * 2]
    return result
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: 先頭k個という指示に対して、kより大きい値の抽出・反転・2倍を生成する。

- 実測入力: `xs=[0]`, `k=1`
- 期待値: `[0]`
- 実際値: `[]`

#### Qwen3-0.6B：合格

````python
def solve(xs, k):
    return xs[:k]
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

### dev-C10-01

**日本語指示（原文）**

````text
整数リストxsを処理するsolve(xs, k)を作ってください。値を2で割った余りが0になる要素だけを、出てきた順のまま選び出す処理を行い、結果のリストを返してください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsから偶数だけを残すsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c10-01)

#### Boku1-nano：不合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    return [value * 3 for value in [value for value in xs if value < k][::2]
````

判定: **Python構文エラー**（`syntax_error`）。

読み取り: 閉じ角括弧が不足して構文エラー。出力には、指示にないk未満の抽出・間引き・3倍も含まれる。

検査エラー: `'[' was never closed (<unknown>, line 2)`。実行前に拒否されたため、実測の入力・返却値はない。

#### Qwen3-0.6B：合格

````python
def solve(xs, k):
    result = []
    for num in xs:
        if num % 2 == 0:
            result.append(num)
    return result
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

### dev-C10-04

**日本語指示（原文）**

````text
solve(xs, k)をお願いします。整数リストxsについて、左端から数えてk番目までにある要素を、今の順番で取り出す。要素がk個に満たなければ全部を取り出す。結果をリストで返してください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsと整数kを受け取り、先頭からk個を取るsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c10-04)

#### Boku1-nano：不合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    output: list[int] = []
    for value in result:
        if k < value:
            output += [value]
    output = output[0::2]
    return output
````

判定: **関数契約・許可構文の検査で拒否**（`contract_or_allowed_syntax`）。

読み取り: 未定義のresultを反復する。先頭k個ではなく、kとの比較と間引きを生成する。

検査エラー: `unsupported_name:result`。実行前に拒否されたため、実測の入力・返却値はない。

#### Qwen3-0.6B：合格

````python
def solve(xs, k):
    result = []
    for i in range(len(xs)):
        if i < k:
            result.append(xs[i])
    return result
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

### dev-C10-05

**日本語指示（原文）**

````text
整数リストxsを処理するsolve(xs, k)を作ってください。どの要素についても、その値から同じ整数kを差し引いた値に置き換える処理を行い、結果のリストを返してください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsと整数kを受け取り、各要素からkを引くsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c10-05)

#### Boku1-nano：不合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = []
    for value in xs:
        result += [value * 3]
    output: list[int] = []
    for value in result:
        output += [value - k]
    return output
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: kを引く前に、指示にない3倍を行う。

- 実測入力: `xs=[1]`, `k=1`
- 期待値: `[0]`
- 実際値: `[2]`

#### Qwen3-0.6B：合格

````python
def solve(xs, k):
    result = []
    for num in xs:
        result.append(num - k)
    return result
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

## 4. Qwen3-0.6Bだけが不合格：20問

| 問題 | 指示 |
| --- | --- |
| [dev-C02-01](#dev-c02-01) | 整数リストxsと整数kを受け取り、kを超える値を残すsolve関数を書いてください。 |
| [dev-C04-01](#dev-c04-01) | 整数リストxsから値を小さい順に並べるsolve関数を書いてください。 |
| [dev-C04-02](#dev-c04-02) | 整数リストxsから値を大きいほうから小さいほうへ並べるsolve関数を書いてください。 |
| [dev-C04-03](#dev-c04-03) | 整数リストxsから現在の並びをひっくりかえすsolve関数を書いてください。 |
| [dev-C04-04](#dev-c04-04) | 整数リストxsから小さい順に並べるsolve関数を書いてください。 |
| [dev-C04-05](#dev-c04-05) | 整数リストxsから順序を逆にするsolve関数を書いてください。 |
| [dev-C05-02](#dev-c05-02) | 整数リストxsと整数kを受け取り、最後のk個を取るsolve関数を書いてください。 |
| [dev-C06-03](#dev-c06-03) | 整数リストxsと整数kを受け取り、最後のk個をとって、現在の並びをひっくりかえすsolve関数を書いてください。 |
| [dev-C07-01](#dev-c07-01) | 整数リストxsから奇数だけを残し、各要素を三倍して、値を小さい順に並べるsolve関数を書いてください。 |
| [dev-C07-02](#dev-c07-02) | 整数リストxsと整数kを受け取り、正の値を選び出して、各要素にkを足して、最後のk個を取るsolve関数を書いてください。 |
| [dev-C07-03](#dev-c07-03) | 整数リストxsと整数kを受け取り、各要素の絶対値を取って、k以上の項目を残し、値を大きいほうから小さいほうへ並べるsolve関数を書いてください。 |
| [dev-C07-04](#dev-c07-04) | 整数リストxsと整数kを受け取り、現在の並びをひっくりかえして、先頭k個を選んで、各項目からkを引くsolve関数を書いてください。 |
| [dev-C08-01](#dev-c08-01) | 整数リストxsからすべての値を2倍して、すべての値を2倍するsolve関数を書いてください。 |
| [dev-C08-02](#dev-c08-02) | 整数リストxsと整数kを受け取り、各要素にkを足して、各要素にkを足して、各要素にkを足すsolve関数を書いてください。 |
| [dev-C08-03](#dev-c08-03) | 整数リストxsと整数kを受け取り、各数値からkを引き、各数値からkを引くsolve関数を書いてください。 |
| [dev-C08-04](#dev-c08-04) | 整数リストxsから各要素を三倍して、各要素を三倍して、各要素を三倍するsolve関数を書いてください。 |
| [dev-C09-02](#dev-c09-02) | 整数リストxsと整数kを受け取り、すべての数を二乗して、kを超える値を残すsolve関数を書いてください。 |
| [dev-C09-03](#dev-c09-03) | 整数リストxsと整数kを受け取り、先頭k個を選んで、値を小さい順に並べるsolve関数を書いてください。 |
| [dev-C09-04](#dev-c09-04) | 整数リストxsと整数kを受け取り、値を小さい順に並べて、最後のk個を取るsolve関数を書いてください。 |
| [dev-C09-05](#dev-c09-05) | 整数リストxsから値の符号を逆転して、正の値を選び出すsolve関数を書いてください。 |

### dev-C02-01

**日本語指示（原文）**

````text
整数リストxsと整数kを受け取り、kを超える値を残すsolve関数を書いてください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsと整数kを受け取り、kより大きい値だけを残すsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c02-01)

#### Boku1-nano：合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    result = []
    for x in xs:
        if k < x:
            result += [x]
    return result
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

#### Qwen3-0.6B：不合格

````python
def solve(xs, k):
    for num in xs:
        if num > k:
            xs.remove(num)
    return xs
````

判定: **関数契約・許可構文の検査で拒否**（`contract_or_allowed_syntax`）。

読み取り: 許可外のremoveで拒否。コードを読むと、残すべきkより大きい値を逆に削除し、入力自体も変更している。後者は実測判定ではなくコード読解。

検査エラー: `unsupported_call`。実行前に拒否されたため、実測の入力・返却値はない。

### dev-C04-01

**日本語指示（原文）**

````text
整数リストxsから値を小さい順に並べるsolve関数を書いてください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsから値を昇順に並べるsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c04-01)

#### Boku1-nano：合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    output: list[int] = sorted(xs, reverse=False)
    return output
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

#### Qwen3-0.6B：不合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    # オプションでkの値を指定
    if k == 0:
        return xs.copy()
    # オプションでkの値を指定
    if k == 1:
        return sorted(xs)
    # オプションでkの値を指定
    if k == 2:
        return sorted(xs, reverse=True)
    # オプションでkの値を指定
    if k == 3:
        return sorted(xs, key=lambda x: x)
    # オプションでkの値を指定
    if k == 4:
        return sorted(xs, key=lambda x: abs(x))
    # オプションでkの値を指定
    if k == 5:
        return sorted(xs, key=lambda x: x)
    # オプションでkの値を指定
    if k == 6:
        return sorted(xs, key=lambda x: abs(x))
    # オプションでkの値を指定
    if k == 7:
        return sorted(xs, key=lambda x: x)
    # オプションでkの値を指定
    if k == 8:
        return sorted(xs, key=lambda x: x)
    # オプションでkの値を指定
    if k == 9:
        return sorted(xs, key=lambda x: x)
    # オプションでkの値を指定
    if k == 10:
        return sorted(xs, key=lambda x: x)
    return xs.copy()
````

判定: **関数契約・許可構文の検査で拒否**（`contract_or_allowed_syntax`）。

読み取り: 許可外のlambdaで拒否。コード読解でも、kをソート方式の選択番号として扱い、常に昇順という指示に従っていない。

検査エラー: `unsupported_syntax:Lambda`。実行前に拒否されたため、実測の入力・返却値はない。

### dev-C04-02

**日本語指示（原文）**

````text
整数リストxsから値を大きいほうから小さいほうへ並べるsolve関数を書いてください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsから値を降順に並べるsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c04-02)

#### Boku1-nano：合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    # 降順に並べる
    output = sorted(xs)[::-1]
    return output
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

#### Qwen3-0.6B：不合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    # 1つずつ大きい値から小さい値へ並べる
    result = []
    for num in xs:
        result.insert(0, num)
    return result
````

判定: **関数契約・許可構文の検査で拒否**（`contract_or_allowed_syntax`）。

読み取り: 許可外のinsertで拒否。コード読解では元の順番を反転するだけで、降順ソートにはなっていない。

検査エラー: `unsupported_call`。実行前に拒否されたため、実測の入力・返却値はない。

### dev-C04-03

**日本語指示（原文）**

````text
整数リストxsから現在の並びをひっくりかえすsolve関数を書いてください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsから現在の要素順を反転するsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c04-03)

#### Boku1-nano：合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    # 現在の要素順を反転する
    result = list(reversed(xs))
    return result
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

#### Qwen3-0.6B：不合格

````python
def solve(xs):
    return xs[::-1]
````

判定: **関数契約・許可構文の検査で拒否**（`contract_or_allowed_syntax`）。

読み取り: 反転処理xs[::-1]自体は正しい。solve(xs)という1引数で、要求されたsolve(xs, k)の契約を満たさない。意味理解の失敗と断定しない。

検査エラー: `solve_xs_k_signature_required`。実行前に拒否されたため、実測の入力・返却値はない。

### dev-C04-04

**日本語指示（原文）**

````text
整数リストxsから小さい順に並べるsolve関数を書いてください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsから値を昇順に並べるsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c04-04)

#### Boku1-nano：合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    output: list[int] = sorted(xs, reverse=False)
    return output
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

#### Qwen3-0.6B：不合格

````python
def solve(xs, k):
    # オプションでkの値を指定
    if k == 0:
        return xs
    # オプションでkの値を指定
    if k == 1:
        return sorted(xs)
    # オプションでkの値を指定
    if k == 2:
        return sorted(xs, reverse=True)
    # オプションでkの値を指定
    if k == 3:
        return sorted(xs, key=lambda x: x)
    # オプションでkの値を指定
    if k == 4:
        return sorted(xs, key=lambda x: -x)
    # オプションでkの値を指定
    if k == 5:
        return sorted(xs, key=lambda x: abs(x))
    # オプションでkの値を指定
    if k == 6:
        return sorted(xs, key=lambda x: abs(x))
    # オプションでkの値を指定
    if k == 7:
        return sorted(xs, key=lambda x: abs(x))
    # オプションでkの値を指定
    if k == 8:
        return sorted(xs, key=lambda x: abs(x))
    # オプションでkの値を指定
    if k == 9:
        return sorted(xs, key=lambda x: abs(x))
    # オプションでkの値を指定
    if k == 10:
        return sorted(xs, key=lambda x: abs(x))
    return xs
````

判定: **関数契約・許可構文の検査で拒否**（`contract_or_allowed_syntax`）。

読み取り: 許可外のlambdaで拒否。kをソート方式の選択番号として扱う処理も指示にない。

検査エラー: `unsupported_syntax:Lambda`。実行前に拒否されたため、実測の入力・返却値はない。

### dev-C04-05

**日本語指示（原文）**

````text
整数リストxsから順序を逆にするsolve関数を書いてください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsから現在の要素順を反転するsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c04-05)

#### Boku1-nano：合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = xs[::-1]
    return result
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

#### Qwen3-0.6B：不合格

````python
def solve(xs):
    return list(reversed(xs))
````

判定: **関数契約・許可構文の検査で拒否**（`contract_or_allowed_syntax`）。

読み取り: list(reversed(xs))という反転処理自体は正しいが、solve(xs)という1引数で契約不一致。意味理解の失敗と断定しない。

検査エラー: `solve_xs_k_signature_required`。実行前に拒否されたため、実測の入力・返却値はない。

### dev-C05-02

**日本語指示（原文）**

````text
整数リストxsと整数kを受け取り、最後のk個を取るsolve関数を書いてください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsと整数kを受け取り、末尾からk個を取るsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c05-02)

#### Boku1-nano：合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    result = xs[-k:]
    return result
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

#### Qwen3-0.6B：不合格

````python
def solve(xs, k):
    return xs[:k]
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: 末尾k個という指示に対して、先頭k個xs[:k]を返す。

- 実測入力: `xs=[-5, -1, 0, 1, 5]`, `k=2`
- 期待値: `[1, 5]`
- 実際値: `[-5, -1]`

### dev-C06-03

**日本語指示（原文）**

````text
整数リストxsと整数kを受け取り、最後のk個をとって、現在の並びをひっくりかえすsolve関数を書いてください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsと整数kを受け取り、末尾からk個を取り、現在の要素順を反転するsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c06-03)

#### Boku1-nano：合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    # 末尾からk個を取る
    result: list[int] = xs[-k:]
    # 現在の要素順を反転する
    output: list[int] = list(reversed(result))
    return output
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

#### Qwen3-0.6B：不合格

````python
def solve(xs, k):
    # 1. 取り出す
    first_k = xs[:k]
    # 2. 反転
    reversed_list = list(reversed(first_k))
    # 3. 取り出す
    last_k = xs[k:]
    # 4. 合計
    return list(reversed_list + last_k)
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: 要求は末尾k個の反転だが、先頭k個を反転し、不要な残りxs[k:]を付け戻している。

- 実測入力: `xs=[-5, -1, 0, 1, 5]`, `k=2`
- 期待値: `[5, 1]`
- 実際値: `[-1, -5, 0, 1, 5]`

### dev-C07-01

**日本語指示（原文）**

````text
整数リストxsから奇数だけを残し、各要素を三倍して、値を小さい順に並べるsolve関数を書いてください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsから奇数だけを残し、各要素を3倍し、値を昇順に並べるsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c07-01)

#### Boku1-nano：合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = [x for x in xs if 0 != x % 2]
    output: list[int] = []
    for value in result:
        output += [value * 3]
    output = sorted(output, reverse=False)
    return output
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

#### Qwen3-0.6B：不合格

````python
def solve(xs, k):
    # 奇数だけを残すリスト
    filtered = [num for num in xs if num % 2 != 0]
    
    # 各要素を三倍して、値を小さい順に並べる
    sorted_list = sorted(filtered, reverse=True)
    
    return sorted_list
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: 3倍を省略し、昇順を降順に変更する。コメントの「三倍」「小さい順」と実装が一致しない。

- 実測入力: `xs=[1]`, `k=1`
- 期待値: `[3]`
- 実際値: `[1]`

### dev-C07-02

**日本語指示（原文）**

````text
整数リストxsと整数kを受け取り、正の値を選び出して、各要素にkを足して、最後のk個を取るsolve関数を書いてください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsと整数kを受け取り、正の値だけを残し、各要素にkを加え、末尾からk個を取るsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c07-02)

#### Boku1-nano：合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    # 正の値だけを残す
    result: list[int] = [value for value in xs if 0 < value]
    # 各要素にkを加える
    output: list[int] = []
    for x in result:
        output += [x + k]
    # 末尾からk個を取る
    output = output[-k:]
    return output
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

#### Qwen3-0.6B：不合格

````python
def solve(xs, k):
    result = []
    for i in range(len(xs)):
        if i < k:
            result.append(xs[i])
    return result
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: 正の値の抽出とk加算を省略し、末尾k個ではなく先頭k個を返す。

- 実測入力: `xs=[0]`, `k=1`
- 期待値: `[]`
- 実際値: `[0]`

### dev-C07-03

**日本語指示（原文）**

````text
整数リストxsと整数kを受け取り、各要素の絶対値を取って、k以上の項目を残し、値を大きいほうから小さいほうへ並べるsolve関数を書いてください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsと整数kを受け取り、各要素の絶対値を取り、k以上の値だけを残し、値を降順に並べるsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c07-03)

#### Boku1-nano：合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    # 各要素の絶対値を取る
    result: list[int] = [abs(x) for x in xs]
    # k以上の値だけを残す
    output: list[int] = [x for x in result if k <= x]
    # 降順に並べる
    output = sorted(output, reverse=True)
    return output
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

#### Qwen3-0.6B：不合格

````python
def solve(xs, k):
    # 長さが0以下またはkが0以下の場合、出力は空リスト
    if not xs or k <= 0:
        return []
    
    # 指定されたkの項目を残す
    selected = [x for x in xs if x >= 0]
    
    # 指定されたkの項目を大きいほうから小さいほうへ並べる
    selected.sort()
    
    return selected
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: kを用いる条件をx >= 0へ変更し、要求された処理を省略して昇順にする。

- 実測入力: `xs=[0]`, `k=1`
- 期待値: `[]`
- 実際値: `[0]`

### dev-C07-04

**日本語指示（原文）**

````text
整数リストxsと整数kを受け取り、現在の並びをひっくりかえして、先頭k個を選んで、各項目からkを引くsolve関数を書いてください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsと整数kを受け取り、現在の要素順を反転し、先頭からk個を取り、各要素からkを引くsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c07-04)

#### Boku1-nano：合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    # 現在の要素順を反転する
    result = list(reversed(xs))
    # 先頭からk個を取る
    result = result[0:k]
    # 各要素からkを引く
    output = [value - k for value in result]
    return output
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

#### Qwen3-0.6B：不合格

````python
def solve(xs, k):
    # 1. 1つずつ取り出す
    result = []
    for i in range(k):
        result.append(xs[i])
    # 2. 1つずつ取り出す
    result = result[::-1]
    return result
````

判定: **実行時例外**（`runtime_error`）。

読み取り: 反転→先頭k個→k減算の指示を、先頭k個→反転へ変更する。空入力でxs[0]へアクセスしてIndexError。

- 実測入力: `xs=[]`, `k=1`
- 期待値: `[]`
- 実際の例外: `IndexError: list index out of range`

### dev-C08-01

**日本語指示（原文）**

````text
整数リストxsからすべての値を2倍して、すべての値を2倍するsolve関数を書いてください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsから各要素を2倍し、各要素を2倍するsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c08-01)

#### Boku1-nano：合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = []
    for value in xs:
        result += [value * 2]
    output: list[int] = []
    for value in result:
        output += [value * 2]
    return output
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

#### Qwen3-0.6B：不合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    return [num * k for num in xs]
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: 2倍を2回（4倍）という指示を、k倍1回へ置き換える。

- 実測入力: `xs=[1]`, `k=1`
- 期待値: `[4]`
- 実際値: `[1]`

### dev-C08-02

**日本語指示（原文）**

````text
整数リストxsと整数kを受け取り、各要素にkを足して、各要素にkを足して、各要素にkを足すsolve関数を書いてください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsと整数kを受け取り、各要素にkを加え、各要素にkを加え、各要素にkを加えるsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c08-02)

#### Boku1-nano：合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    # 各要素にkを加える
    output: list[int] = [value + k for value in xs]
    # 各要素にkを加える
    result: list[int] = []
    for x in output:
        result += [x + k]
    # 各要素にkを加える
    output = []
    for value in result:
        output += [value + k]
    return output
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

#### Qwen3-0.6B：不合格

````python
def solve(xs, k):
    result = []
    for num in xs:
        result.append(num + k)
    return result
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: k加算3回のうち1回しか実行しない。

- 実測入力: `xs=[0]`, `k=1`
- 期待値: `[3]`
- 実際値: `[1]`

### dev-C08-03

**日本語指示（原文）**

````text
整数リストxsと整数kを受け取り、各数値からkを引き、各数値からkを引くsolve関数を書いてください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsと整数kを受け取り、各要素からkを引き、各要素からkを引くsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c08-03)

#### Boku1-nano：合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = []
    for value in xs:
        result += [value - k]
    output: list[int] = []
    for value in result:
        output += [value - k]
    return output
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

#### Qwen3-0.6B：不合格

````python
def solve(xs, k):
    for num in xs:
        xs[num] = xs[num] - k
    return xs
````

判定: **入力リストを変更**（`input_mutation`）。

読み取り: xs[num]へ代入して入力を変更する。減算も1回だけで、要素の値を添字に使う問題もある。採点は最初の入力変更で停止した。

- 実測入力: `xs=[0]`, `k=1`
- 期待値: `[-2]`
- 実際値: `[-1]`
- 入力リストの変更を検出したため不合格。

### dev-C08-04

**日本語指示（原文）**

````text
整数リストxsから各要素を三倍して、各要素を三倍して、各要素を三倍するsolve関数を書いてください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsから各要素を3倍し、各要素を3倍し、各要素を3倍するsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c08-04)

#### Boku1-nano：合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    # 各要素を3倍する
    result: list[int] = []
    for value in xs:
        result += [value * 3]
    # 各要素を3倍する
    output: list[int] = []
    for value in result:
        output += [value * 3]
    # 各要素を3倍する
    result = []
    for value in output:
        result += [value * 3]
    return result
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

#### Qwen3-0.6B：不合格

````python
def solve(xs, k):
    result = []
    for num in xs:
        result.append(num * k)
    return result
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: 3倍を3回（27倍）という指示を、k倍1回へ置き換える。

- 実測入力: `xs=[1]`, `k=1`
- 期待値: `[27]`
- 実際値: `[1]`

### dev-C09-02

**日本語指示（原文）**

````text
整数リストxsと整数kを受け取り、すべての数を二乗して、kを超える値を残すsolve関数を書いてください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsと整数kを受け取り、各要素を二乗し、kより大きい値だけを残すsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c09-02)

#### Boku1-nano：合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    # 各要素を二乗する
    result: list[int] = []
    for value in xs:
        result += [value * value]
    # kより大きい値だけを残す
    output: list[int] = [x for x in result if k < x]
    return output
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

#### Qwen3-0.6B：不合格

````python
def solve(xs, k):
    result = []
    for num in xs:
        if num * num > k:
            result.append(num)
        else:
            result.append(num * num)
    return result
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: 二乗後に条件を満たす値を抽出せず、条件成立時に元の値、不成立時に二乗値を残す。

- 実測入力: `xs=[0]`, `k=1`
- 期待値: `[]`
- 実際値: `[0]`

### dev-C09-03

**日本語指示（原文）**

````text
整数リストxsと整数kを受け取り、先頭k個を選んで、値を小さい順に並べるsolve関数を書いてください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsと整数kを受け取り、先頭からk個を取り、値を昇順に並べるsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c09-03)

#### Boku1-nano：合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = xs[0:k]
    output: list[int] = sorted(result, reverse=False)
    return output
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

#### Qwen3-0.6B：不合格

````python
def solve(xs, k):
    # 1. 長さがkより大きい場合、全部を取る
    if len(xs) < k:
        return xs
    
    # 2. 先頭k個を選ぶ
    first_k = xs[:k]
    
    # 3. 先頭k個の値を小さい順に並べる
    return sorted(first_k)
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: 要素数がk未満のとき、ソートせず元のリストを返してしまう。

- 実測入力: `xs=[-9, 89, -3, 80, -25, -78]`, `k=7`
- 期待値: `[-78, -25, -9, -3, 80, 89]`
- 実際値: `[-9, 89, -3, 80, -25, -78]`

### dev-C09-04

**日本語指示（原文）**

````text
整数リストxsと整数kを受け取り、値を小さい順に並べて、最後のk個を取るsolve関数を書いてください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsと整数kを受け取り、値を昇順に並べ、末尾からk個を取るsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c09-04)

#### Boku1-nano：合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    # 昇順に並べる
    output = sorted(xs)
    # 末尾からk個を取る
    output = output[-k:]
    return output
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

#### Qwen3-0.6B：不合格

````python
def solve(xs, k):
    # オプションでkを含む場合、リストの最後k個を削除
    if k <= 0:
        return xs
    # オプションでkを含む場合、リストの最後k個を削除
    return xs[:len(xs)-k] + xs[len(xs)-k:]
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: ソートを行わず、分割したxsの前半と後半を再結合し、元のリスト全体を返す。

- 実測入力: `xs=[-5, -1, 0, 1, 5]`, `k=2`
- 期待値: `[1, 5]`
- 実際値: `[-5, -1, 0, 1, 5]`

### dev-C09-05

**日本語指示（原文）**

````text
整数リストxsから値の符号を逆転して、正の値を選び出すsolve関数を書いてください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsから各要素の符号を反転し、正の値だけを残すsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c09-05)

#### Boku1-nano：合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    # 各要素の符号を反転する
    result: list[int] = [-x for x in xs]
    # 正の値だけを残す
    output: list[int] = [x for x in result if 0 < x]
    return output
````

実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。

#### Qwen3-0.6B：不合格

````python
def solve(xs, k):
    result = []
    for num in xs:
        if num > 0:
            result.append(num)
    return result
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: 符号反転を省略し、元の値が正かどうかだけで選ぶ。

- 実測入力: `xs=[1]`, `k=1`
- 期待値: `[]`
- 実際値: `[1]`

## 5. 両モデルとも不合格：11問

| 問題 | 指示 |
| --- | --- |
| [dev-C01-03](#dev-c01-03) | 整数リストxsが与えられます。正の値を選び出す処理をするsolve(xs, k)を作成し、結果をリストで返してください。 |
| [dev-C02-02](#dev-c02-02) | 整数リストxsと整数kが与えられます。k以上の項目を残す処理をするsolve(xs, k)を作成し、結果をリストで返してください。 |
| [dev-C02-03](#dev-c02-03) | 整数リストxsと整数kが与えられます。k未満の値のみを残す処理をするsolve(xs, k)を作成し、結果をリストで返してください。 |
| [dev-C02-04](#dev-c02-04) | 整数リストxsと整数kが与えられます。k以下の値のみを残す処理をするsolve(xs, k)を作成し、結果をリストで返してください。 |
| [dev-C05-03](#dev-c05-03) | 整数リストxsから先頭の要素から始めて隔番で取り出すsolve関数を書いてください。 |
| [dev-C05-05](#dev-c05-05) | 整数リストxsと整数kが与えられます。最後k個を切り取る処理をするsolve(xs, k)を作成し、結果をリストで返してください。 |
| [dev-C06-05](#dev-c06-05) | 整数リストxsからすべての数を二乗して、先頭の要素から始めて隔番で取り出すsolve関数を書いてください。 |
| [dev-C07-05](#dev-c07-05) | 整数リストxsと整数kを受け取り、先頭の要素から始めて隔番で取り出して、すべての値を2倍して、kを超える値を残すsolve関数を書いてください。 |
| [dev-C08-05](#dev-c08-05) | 整数リストxsからその時点の先頭の要素から始めて隔番で取り出して、その時点の先頭の要素から始めて隔番で取り出すsolve関数を書いてください。 |
| [dev-C10-02](#dev-c10-02) | 整数リストxsを処理するsolve(xs, k)を作ってください。各要素を数直線上での0からの距離に置き換える処理を行い、結果のリストを返してください。 |
| [dev-C10-03](#dev-c10-03) | 整数リストxsを処理するsolve(xs, k)を作ってください。今の末尾を最初にして、要素を末尾側から一つずつたどった並びにする処理を行い、結果のリストを返してください。 |

### dev-C01-03

**日本語指示（原文）**

````text
整数リストxsが与えられます。正の値を選び出す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsから正の値だけを残すsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c01-03)

#### Boku1-nano：不合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = [value for value in xs if value < k]
    output: list[int] = []
    for value in result:
        if value >= k:
            output += [value]
    return output
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: 正の値を選ぶ代わりに、k未満を抽出してからk以上を抽出する。両立しない条件なので空になる。

- 実測入力: `xs=[1]`, `k=1`
- 期待値: `[1]`
- 実際値: `[]`

#### Qwen3-0.6B：不合格

````python
def solve(xs, k):
    result = []
    for num in xs:
        if num > 0 and num <= k:
            result.append(num)
    return result
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: 正の値という条件に、指示にないnum <= kを追加して大きな正数を落とす。

- 実測入力: `xs=[-5, -1, 0, 1, 5]`, `k=2`
- 期待値: `[1, 5]`
- 実際値: `[1]`

### dev-C02-02

**日本語指示（原文）**

````text
整数リストxsと整数kが与えられます。k以上の項目を残す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsと整数kを受け取り、k以上の値だけを残すsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c02-02)

#### Boku1-nano：不合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = []
    for x in xs:
        if k < x:
            result += [x]
    output: list[int] = []
    for value in result:
        if value >= k:
            output += [value]
    return output
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: 最初の抽出がk < xで、kと等しい要素を落とす。後段の>=では取り戻せない。

- 実測入力: `xs=[1]`, `k=1`
- 期待値: `[1]`
- 実際値: `[]`

#### Qwen3-0.6B：不合格

````python
def solve(xs, k):
    result = []
    for num in xs:
        if num > k:
            result.append(num)
    return result
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: k以上をkより大きいに取り違え、等しい値を落とす。

- 実測入力: `xs=[1]`, `k=1`
- 期待値: `[1]`
- 実際値: `[]`

### dev-C02-03

**日本語指示（原文）**

````text
整数リストxsと整数kが与えられます。k未満の値のみを残す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsと整数kを受け取り、kより小さい値だけを残すsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c02-03)

#### Boku1-nano：不合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = [value for value in xs if value > k]
    output: list[int] = []
    for value in result:
        if k < value:
            output += [value]
    return output
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: k未満という指示に対して、kより大きい値を抽出する。大小が逆。

- 実測入力: `xs=[0]`, `k=1`
- 期待値: `[0]`
- 実際値: `[]`

#### Qwen3-0.6B：不合格

````python
def solve(xs, k):
    result = []
    for num in xs:
        if num > k:
            continue
        result.append(num)
    return result
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: kより大きい値だけを除外するため、kと等しい値が残る。「未満」と「以下」の混同。

- 実測入力: `xs=[1]`, `k=1`
- 期待値: `[]`
- 実際値: `[1]`

### dev-C02-04

**日本語指示（原文）**

````text
整数リストxsと整数kが与えられます。k以下の値のみを残す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsと整数kを受け取り、k以下の値だけを残すsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c02-04)

#### Boku1-nano：不合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = [value for value in xs if k < value]
    result = [value for value in result if k >= value]
    return result
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: kより大きい値を抽出した後、k以下を抽出するため空になる。

- 実測入力: `xs=[0]`, `k=1`
- 期待値: `[0]`
- 実際値: `[]`

#### Qwen3-0.6B：不合格

````python
def solve(xs, k):
    result = []
    for num in xs:
        if num > 0 and k > 0:
            result.append(num)
    return result
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: k以下の比較を行わず、num > 0 and k > 0で正数を選ぶ。

- 実測入力: `xs=[0]`, `k=1`
- 期待値: `[0]`
- 実際値: `[]`

### dev-C05-03

**日本語指示（原文）**

````text
整数リストxsから先頭の要素から始めて隔番で取り出すsolve関数を書いてください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsから先頭から1個おきに取るsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c05-03)

#### Boku1-nano：不合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = xs[::2]
    output: list[int] = result[::2]
    return output
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: 1個おきの取り出しを2回行う。要求はxs[::2]だが、実質xs[::4]になる。

- 実測入力: `xs=[0, 0, 0]`, `k=3`
- 期待値: `[0, 0]`
- 実際値: `[0]`

#### Qwen3-0.6B：不合格

````python
def solve(xs):
    result = []
    for num in xs:
        result.append(num)
    return result
````

判定: **関数契約・許可構文の検査で拒否**（`contract_or_allowed_syntax`）。

読み取り: 1引数で契約不一致。コード読解でも間引かず、全要素をコピーしている。

検査エラー: `solve_xs_k_signature_required`。実行前に拒否されたため、実測の入力・返却値はない。

### dev-C05-05

**日本語指示（原文）**

````text
整数リストxsと整数kが与えられます。最後k個を切り取る処理をするsolve(xs, k)を作成し、結果をリストで返してください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsと整数kを受け取り、末尾からk個を取るsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c05-05)

#### Boku1-nano：不合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = [value for value in xs if k < value]
    result = result[-k:]
    return result
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: 末尾k個の取り出し前に、指示にないkより大きい値の抽出を行う。

- 実測入力: `xs=[0]`, `k=1`
- 期待値: `[0]`
- 実際値: `[]`

#### Qwen3-0.6B：不合格

````python
def solve(xs, k):
    return xs[:k]
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: 末尾k個という指示に対して、先頭k個xs[:k]を返す。

- 実測入力: `xs=[-5, -1, 0, 1, 5]`, `k=2`
- 期待値: `[1, 5]`
- 実際値: `[-5, -1]`

### dev-C06-05

**日本語指示（原文）**

````text
整数リストxsからすべての数を二乗して、先頭の要素から始めて隔番で取り出すsolve関数を書いてください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsから各要素を二乗し、先頭から1個おきに取るsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c06-05)

#### Boku1-nano：不合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    # 各要素を二乗する
    result: list[int] = []
    for value in xs:
        result += [value ** 2]
    # 先頭から1個おきに取る
    result = result[0::2]
    # 先頭から1個おきに取る
    result = result[::2]
    return result
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: 二乗後の1個おきの取り出しを、要求より1回多く行う。

- 実測入力: `xs=[0, 0, 0]`, `k=3`
- 期待値: `[0, 0]`
- 実際値: `[0]`

#### Qwen3-0.6B：不合格

````python
def solve(xs, k):
    result = []
    for i in range(k):
        result.append(xs[i] ** 2)
    return result
````

判定: **実行時例外**（`runtime_error`）。

読み取り: 二乗して1個おきに取る代わりに、先頭k個を二乗する。空入力への添字参照でIndexError。

- 実測入力: `xs=[]`, `k=1`
- 期待値: `[]`
- 実際の例外: `IndexError: list index out of range`

### dev-C07-05

**日本語指示（原文）**

````text
整数リストxsと整数kを受け取り、先頭の要素から始めて隔番で取り出して、すべての値を2倍して、kを超える値を残すsolve関数を書いてください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsと整数kを受け取り、先頭から1個おきに取り、各要素を2倍し、kより大きい値だけを残すsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c07-05)

#### Boku1-nano：不合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    return [value for value in [value * 2 for value in xs][::2] if k < x]
````

判定: **関数契約・許可構文の検査で拒否**（`contract_or_allowed_syntax`）。

読み取り: 内包表記の変数はvalueなのに、条件式で未定義のxを参照する。静的検査で停止した。

検査エラー: `unsupported_name:x`。実行前に拒否されたため、実測の入力・返却値はない。

#### Qwen3-0.6B：不合格

````python
def solve(xs, k):
    result = []
    for num in xs:
        if num * 2 > k:
            result.append(num)
        else:
            result.append(num * 2)
    return result
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: 間引きを省略し、条件を満たす場合は2倍する前の値、満たさない場合は2倍した値を残す。抽出になっていない。

- 実測入力: `xs=[0]`, `k=1`
- 期待値: `[]`
- 実際値: `[0]`

### dev-C08-05

**日本語指示（原文）**

````text
整数リストxsからその時点の先頭の要素から始めて隔番で取り出して、その時点の先頭の要素から始めて隔番で取り出すsolve関数を書いてください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsから先頭から1個おきに取り、先頭から1個おきに取るsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c08-05)

#### Boku1-nano：不合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    # 現在の要素順を反転する
    result = list(reversed(xs))
    # 先頭から1個おきに取る
    result = result[0::2]
    return result
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: 1個おきの取り出し2回という指示を、反転→1個おき1回へ変更する。

- 実測入力: `xs=[0, 0, 0]`, `k=3`
- 期待値: `[0]`
- 実際値: `[0, 0]`

#### Qwen3-0.6B：不合格

````python
def solve(xs, k):
    result = []
    for i in range(k):
        result.append(xs[i])
    return result
````

判定: **実行時例外**（`runtime_error`）。

読み取り: 1個おき2回を先頭k個の取得に取り違える。空入力でIndexError。

- 実測入力: `xs=[]`, `k=1`
- 期待値: `[]`
- 実際の例外: `IndexError: list index out of range`

### dev-C10-02

**日本語指示（原文）**

````text
整数リストxsを処理するsolve(xs, k)を作ってください。各要素を数直線上での0からの距離に置き換える処理を行い、結果のリストを返してください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsから各要素の絶対値を取るsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c10-02)

#### Boku1-nano：不合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = []
    for value in xs:
        if value < 0:
            result += [value]
    result = [value * 2 for value in result]
    return result
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: 「0からの距離」（絶対値）を、負の値だけ抽出して2倍する処理へ取り違える。

- 実測入力: `xs=[0]`, `k=1`
- 期待値: `[0]`
- 実際値: `[]`

#### Qwen3-0.6B：不合格

````python
def solve(xs, k):
    result = []
    for num in xs:
        result.append(num * k)
    return result
````

判定: **実行結果の不一致**（`output_mismatch`）。

読み取り: 「0からの距離」（絶対値）をk倍へ取り違える。

- 実測入力: `xs=[-1]`, `k=10`
- 期待値: `[1]`
- 実際値: `[-10]`

### dev-C10-03

**日本語指示（原文）**

````text
整数リストxsを処理するsolve(xs, k)を作ってください。今の末尾を最初にして、要素を末尾側から一つずつたどった並びにする処理を行い、結果のリストを返してください。
````

**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**

````text
整数リストxsから現在の要素順を反転するsolve関数を書いてください。
````

[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#dev-c10-03)

#### Boku1-nano：不合格

````python
def solve(xs: list[int], k: int) -> list[int]:
    output: list[int] = []
    for value in result:
        output += [value * 3]
    output = output[::-1]
    return output
````

判定: **関数契約・許可構文の検査で拒否**（`contract_or_allowed_syntax`）。

読み取り: 未定義のresultを反復しており、さらに指示にない3倍が入る。静的検査で停止した。

検査エラー: `unsupported_name:result`。実行前に拒否されたため、実測の入力・返却値はない。

#### Qwen3-0.6B：不合格

````python
def solve(xs, k):
    result = []
    for i in range(len(xs)):
        result.insert(0, xs[i])
    return result
````

判定: **関数契約・許可構文の検査で拒否**（`contract_or_allowed_syntax`）。

読み取り: insert(0, ...)で順序を反転するアルゴリズム自体は正しい。固定した許可呼出しにinsertがなく拒否された採点上の制約であり、反転ができない証拠にはしない。

検査エラー: `unsupported_call`。実行前に拒否されたため、実測の入力・返却値はない。

## 6. 元データと再生成

- [全体集計（条件A・B）](dev50_20261005_results.md)
- [全50問の実プロンプト・生出力（条件A・B）](dev50_20261005_details.md)
- [固定問題JSONL](../../../data/benchmarks/browser_100/dev50.jsonl)
- [採点記録JSONL](../../../data/benchmarks/browser_100/runs/dev50-20261005/scored.jsonl)
- [生の推論記録JSONL](../../../data/benchmarks/browser_100/runs/dev50-20261005/raw_inference.jsonl)

過去の実行記録は追跡可能性のためそのまま保存。本書はcondition=Aの100件だけを抽出して作成した。

````bash
.venv/bin/python scripts/model/report_browser_condition_a_failures.py
````

