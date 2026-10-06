# 条件Aの追加評価：5M・1epoch／1M・3epoch

実施日: 2026年10月5日。同じ開発用50問で追加評価し、既存の15M・Qwenと比較する。問題や生成コードの補正、得点に合わせた問題選別、失敗後の再生成は行っていない。

[既存の失敗例一覧へ戻る](dev50_20261005_condition_a_failures.md)

## 1. 結果

| モデル | 合格 / 50問 | 正答率 | 不合格 |
| --- | ---: | ---: | ---: |
| Boku1-nano 15M・1epoch | 30/50 | 60% | 20 |
| Boku1-nano 5M・1epoch | 28/50 | 56% | 22 |
| Boku1-nano 1M・3epoch | 29/50 | 58% | 21 |
| Qwen3-0.6B | 19/50 | 38% | 31 |

15MとQwenは前回の条件Aの実測を再掲し、5M・1epochと1M・3epochだけを追加実行した。条件Bは追加評価していない。50問の固定集合・各1候補での結果であり、1Mのほうが5Mより一般に優れるとは結論しない。サイズに加えて学習epoch数も異なる。

### 分類別の合格数（各5問）

| 分類 | 15M・1epoch | 5M・1epoch | 1M・3epoch | Qwen3-0.6B |
| --- | ---: | ---: | ---: | ---: |
| C01 基本的な抽出 | 4 | 3 | 3 | 4 |
| C02 kを使う条件 | 1 | 1 | 1 | 1 |
| C03 値の変換 | 2 | 2 | 2 | 5 |
| C04 順序の変更 | 5 | 3 | 3 | 0 |
| C05 切り出し | 1 | 0 | 1 | 2 |
| C06 2操作の合成 | 4 | 5 | 4 | 3 |
| C07 3操作の合成 | 4 | 5 | 5 | 0 |
| C08 同じ操作の反復 | 4 | 4 | 5 | 0 |
| C09 順序を取り違えやすい合成 | 5 | 5 | 5 | 1 |
| C10 未学習の言い回し | 0 | 0 | 0 | 3 |

5M・1MともにC07（3操作）は5/5で、15Mが落としたC07-05も合格した。一方、C10（新しい言い回し）は両モデル0/5。5MはC05（切り出し）0/5、1Mは同分類1/5だった。

### 追加モデルの不合格理由

| 理由 | 5M・1epoch | 1M・3epoch |
| --- | ---: | ---: |
| 実行結果の不一致 | 20 | 18 |
| 契約・許可構文の検査で拒否 | 2 | 1 |
| Python構文エラー | 0 | 2 |
| 実行時例外 | 0 | 0 |

関数契約・許可構文の不合格は、5Mの2件が未定義変数、1Mの1件が空出力（C10-03、関数なし）を静的に検出したもの。全100生成はEOSで終了し、生成上限到達や基盤エラーはなかった。Qwenの契約・許可構文による不合格を意味誤りと区別する扱いは前回のまま維持する。

### 追加モデルが失敗した問題

**Boku1-nano 5M・1epoch：22問**

[C01-03](dev50_20261005_additional_models.md#dev-c01-03)、[C01-05](dev50_20261005_additional_models.md#dev-c01-05)、[C02-02](dev50_20261005_additional_models.md#dev-c02-02)、[C02-03](dev50_20261005_additional_models.md#dev-c02-03)、[C02-04](dev50_20261005_additional_models.md#dev-c02-04)、[C02-05](dev50_20261005_additional_models.md#dev-c02-05)、[C03-01](dev50_20261005_additional_models.md#dev-c03-01)、[C03-02](dev50_20261005_additional_models.md#dev-c03-02)、[C03-04](dev50_20261005_additional_models.md#dev-c03-04)、[C04-02](dev50_20261005_additional_models.md#dev-c04-02)、[C04-03](dev50_20261005_additional_models.md#dev-c04-03)、[C05-01](dev50_20261005_additional_models.md#dev-c05-01)、[C05-02](dev50_20261005_additional_models.md#dev-c05-02)、[C05-03](dev50_20261005_additional_models.md#dev-c05-03)、[C05-04](dev50_20261005_additional_models.md#dev-c05-04)、[C05-05](dev50_20261005_additional_models.md#dev-c05-05)、[C08-05](dev50_20261005_additional_models.md#dev-c08-05)、[C10-01](dev50_20261005_additional_models.md#dev-c10-01)、[C10-02](dev50_20261005_additional_models.md#dev-c10-02)、[C10-03](dev50_20261005_additional_models.md#dev-c10-03)、[C10-04](dev50_20261005_additional_models.md#dev-c10-04)、[C10-05](dev50_20261005_additional_models.md#dev-c10-05)

**Boku1-nano 1M・3epoch：21問**

[C01-03](dev50_20261005_additional_models.md#dev-c01-03)、[C01-05](dev50_20261005_additional_models.md#dev-c01-05)、[C02-02](dev50_20261005_additional_models.md#dev-c02-02)、[C02-03](dev50_20261005_additional_models.md#dev-c02-03)、[C02-04](dev50_20261005_additional_models.md#dev-c02-04)、[C02-05](dev50_20261005_additional_models.md#dev-c02-05)、[C03-01](dev50_20261005_additional_models.md#dev-c03-01)、[C03-02](dev50_20261005_additional_models.md#dev-c03-02)、[C03-04](dev50_20261005_additional_models.md#dev-c03-04)、[C04-02](dev50_20261005_additional_models.md#dev-c04-02)、[C04-05](dev50_20261005_additional_models.md#dev-c04-05)、[C05-01](dev50_20261005_additional_models.md#dev-c05-01)、[C05-03](dev50_20261005_additional_models.md#dev-c05-03)、[C05-04](dev50_20261005_additional_models.md#dev-c05-04)、[C05-05](dev50_20261005_additional_models.md#dev-c05-05)、[C06-05](dev50_20261005_additional_models.md#dev-c06-05)、[C10-01](dev50_20261005_additional_models.md#dev-c10-01)、[C10-02](dev50_20261005_additional_models.md#dev-c10-02)、[C10-03](dev50_20261005_additional_models.md#dev-c10-03)、[C10-04](dev50_20261005_additional_models.md#dev-c10-04)、[C10-05](dev50_20261005_additional_models.md#dev-c10-05)

### 具体的な違い

- **C03-01「各要素にkを足す」:** 5Mは加算後に不要な3倍を追加。`xs=[0], k=1`で期待`[1]`に対し`[3]`。1Mは符号反転→偶数抽出へ取り違え、同じ入力で`[0]`。
- **C05-03「先頭から1個おき」:** 5Mは取り出した値をさらに2倍し、`xs=[1], k=1`で期待`[1]`に対し`[2]`。1Mは閉じ角括弧不足で構文エラー。
- **C07-05「1個おき→2倍→kより大きい値」:** 追加した両モデルは全179ケースで合格。15Mは未定義の`x`を参照し不合格だった。

[全50問×追加2モデルの実プロンプト・生出力・採点・実測反例](dev50_20261005_additional_models.md)

## 2. 比較条件と実行来歴

- 条件Aのみ。自然な日本語をBoku専用プロンプトへ直接入力。正解CNL・意味ASTをモデルへ渡さない。
- greedy、T=0、会話履歴なし、1問1候補、系列長上限256（入力＋出力）。既存BPEの同じtokenizerを使用。
- 15Mの条件Aと、全50問のプロンプト全文・入力token ID列が一致することを確認。変更はモデルの重み・構成・epoch数。
- 問題SHA-256、採点器SHA-256、全179テスト入力ファイルの一致を確認。採点器の変更なし。
- ブラウザ推論は追加2モデルを順番に実行し、各モデルの終了後に解放。採点は同端末のPython子プロセス。
- 実行器にはモデル・条件を選択する設定を追加。Bokuのtoken生成処理は前回と同じ。実行時のソースhashを別runに保存。
- 50問は15Mを対象に作成した同一開発集合。5M・1Mそれぞれの実学習指示との重複検査は今回追加実施しておらず、全問が未学習とは主張しない。

問題SHA-256: `ba24af53978a61f3002834f9bd4914f40516eaa181b18d67cfe8cac1f5d91954`

### Boku1-nano 5M・1epoch

- model_id: `5m-1epoch`、5,065,472 parameters、ONNX 20,560,021 bytes。
- モデルSHA-256: `5e71bc0ef680408eab5fb5c0f3ff450e492d7edf0230bde7ef830fd92c54f1a7`
- tokenizer SHA-256: `6840a392e8fcae1083be06842774fa912a1797217c7033944ba2d87f1c227293`
- 開始UTC: `2026-10-05T11:25:01.119Z`、完了UTC: `2026-10-05T11:25:08.118Z`
- 生成時間合計: 6.57秒、中央値: 0.126秒（初回ロード除外）。
- 速度は単回の観測値。負荷・キャッシュ状態などを統制した速度比較ではない。

````json
{
  "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36",
  "gpu": {
    "vendor": "apple",
    "architecture": "metal-3",
    "device": "",
    "description": ""
  }
}
````

### Boku1-nano 1M・3epoch

- model_id: `1m-3epoch`、1,016,704 parameters、ONNX 4,233,585 bytes。
- モデルSHA-256: `b882366c28977b2a88d5e71997db82bf3c8b28707d8c58a9772339a3a7b68bb3`
- tokenizer SHA-256: `6840a392e8fcae1083be06842774fa912a1797217c7033944ba2d87f1c227293`
- 開始UTC: `2026-10-05T11:25:29.698Z`、完了UTC: `2026-10-05T11:25:34.843Z`
- 生成時間合計: 4.34秒、中央値: 0.091秒（初回ロード除外）。
- 速度は単回の観測値。負荷・キャッシュ状態などを統制した速度比較ではない。

````json
{
  "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36",
  "gpu": {
    "vendor": "apple",
    "architecture": "metal-3",
    "device": "",
    "description": ""
  }
}
````

## 3. 全50問・4モデルの合否

| 問題 | 日本語指示 | 15M・1epoch | 5M・1epoch | 1M・3epoch | Qwen3-0.6B |
| --- | --- | --- | --- | --- | --- |
| [dev-C01-01](#dev-c01-01) | 整数リストxsから偶数を選んで残すsolve関数を書いてください。 | ○ | ○ | ○ | ○ |
| [dev-C01-02](#dev-c01-02) | 整数リストxsから奇数を残すようにするsolve関数を書いてください。 | ○ | ○ | ○ | ○ |
| [dev-C01-03](#dev-c01-03) | 整数リストxsが与えられます。正の値を選び出す処理をするsolve(xs, k)を作成し、結果をリストで返してください。 | × | × | × | × |
| [dev-C01-04](#dev-c01-04) | 整数リストxsから負の値を残すsolve関数を書いてください。 | ○ | ○ | ○ | ○ |
| [dev-C01-05](#dev-c01-05) | 整数リストxsが与えられます。ゼロを選び出す処理をするsolve(xs, k)を作成し、結果をリストで返してください。 | ○ | × | × | ○ |
| [dev-C02-01](#dev-c02-01) | 整数リストxsと整数kを受け取り、kを超える値を残すsolve関数を書いてください。 | ○ | ○ | ○ | × |
| [dev-C02-02](#dev-c02-02) | 整数リストxsと整数kが与えられます。k以上の項目を残す処理をするsolve(xs, k)を作成し、結果をリストで返してください。 | × | × | × | × |
| [dev-C02-03](#dev-c02-03) | 整数リストxsと整数kが与えられます。k未満の値のみを残す処理をするsolve(xs, k)を作成し、結果をリストで返してください。 | × | × | × | × |
| [dev-C02-04](#dev-c02-04) | 整数リストxsと整数kが与えられます。k以下の値のみを残す処理をするsolve(xs, k)を作成し、結果をリストで返してください。 | × | × | × | × |
| [dev-C02-05](#dev-c02-05) | 整数リストxsと整数kが与えられます。kの倍数だけを選び出す処理をするsolve(xs, k)を作成し、結果をリストで返してください。 | × | × | × | ○ |
| [dev-C03-01](#dev-c03-01) | 整数リストxsと整数kが与えられます。各要素にkを足す処理をするsolve(xs, k)を作成し、結果をリストで返してください。 | × | × | × | ○ |
| [dev-C03-02](#dev-c03-02) | 整数リストxsと整数kが与えられます。各項目からkを引く処理をするsolve(xs, k)を作成し、結果をリストで返してください。 | × | × | × | ○ |
| [dev-C03-03](#dev-c03-03) | 整数リストxsと整数kを受け取り、すべての要素をk倍するsolve関数を書いてください。 | ○ | ○ | ○ | ○ |
| [dev-C03-04](#dev-c03-04) | 整数リストxsが与えられます。値の符号を逆転する処理をするsolve(xs, k)を作成し、結果をリストで返してください。 | × | × | × | ○ |
| [dev-C03-05](#dev-c03-05) | 整数リストxsからすべての数を二乗するsolve関数を書いてください。 | ○ | ○ | ○ | ○ |
| [dev-C04-01](#dev-c04-01) | 整数リストxsから値を小さい順に並べるsolve関数を書いてください。 | ○ | ○ | ○ | × |
| [dev-C04-02](#dev-c04-02) | 整数リストxsから値を大きいほうから小さいほうへ並べるsolve関数を書いてください。 | ○ | × | × | × |
| [dev-C04-03](#dev-c04-03) | 整数リストxsから現在の並びをひっくりかえすsolve関数を書いてください。 | ○ | × | ○ | × |
| [dev-C04-04](#dev-c04-04) | 整数リストxsから小さい順に並べるsolve関数を書いてください。 | ○ | ○ | ○ | × |
| [dev-C04-05](#dev-c04-05) | 整数リストxsから順序を逆にするsolve関数を書いてください。 | ○ | ○ | × | × |
| [dev-C05-01](#dev-c05-01) | 整数リストxsと整数kが与えられます。先頭k個を選ぶ処理をするsolve(xs, k)を作成し、結果をリストで返してください。 | × | × | × | ○ |
| [dev-C05-02](#dev-c05-02) | 整数リストxsと整数kを受け取り、最後のk個を取るsolve関数を書いてください。 | ○ | × | ○ | × |
| [dev-C05-03](#dev-c05-03) | 整数リストxsから先頭の要素から始めて隔番で取り出すsolve関数を書いてください。 | × | × | × | × |
| [dev-C05-04](#dev-c05-04) | 整数リストxsと整数kが与えられます。頭k個を抜き出す処理をするsolve(xs, k)を作成し、結果をリストで返してください。 | × | × | × | ○ |
| [dev-C05-05](#dev-c05-05) | 整数リストxsと整数kが与えられます。最後k個を切り取る処理をするsolve(xs, k)を作成し、結果をリストで返してください。 | × | × | × | × |
| [dev-C06-01](#dev-c06-01) | 整数リストxsから偶数を選んで残して、すべての値を2倍するsolve関数を書いてください。 | ○ | ○ | ○ | ○ |
| [dev-C06-02](#dev-c06-02) | 整数リストxsから負の値を残して、各要素の絶対値を取るsolve関数を書いてください。 | ○ | ○ | ○ | ○ |
| [dev-C06-03](#dev-c06-03) | 整数リストxsと整数kを受け取り、最後のk個をとって、現在の並びをひっくりかえすsolve関数を書いてください。 | ○ | ○ | ○ | × |
| [dev-C06-04](#dev-c06-04) | 整数リストxsと整数kを受け取り、すべての要素をk倍して、値を降順に整理するsolve関数を書いてください。 | ○ | ○ | ○ | ○ |
| [dev-C06-05](#dev-c06-05) | 整数リストxsからすべての数を二乗して、先頭の要素から始めて隔番で取り出すsolve関数を書いてください。 | × | ○ | × | × |
| [dev-C07-01](#dev-c07-01) | 整数リストxsから奇数だけを残し、各要素を三倍して、値を小さい順に並べるsolve関数を書いてください。 | ○ | ○ | ○ | × |
| [dev-C07-02](#dev-c07-02) | 整数リストxsと整数kを受け取り、正の値を選び出して、各要素にkを足して、最後のk個を取るsolve関数を書いてください。 | ○ | ○ | ○ | × |
| [dev-C07-03](#dev-c07-03) | 整数リストxsと整数kを受け取り、各要素の絶対値を取って、k以上の項目を残し、値を大きいほうから小さいほうへ並べるsolve関数を書いてください。 | ○ | ○ | ○ | × |
| [dev-C07-04](#dev-c07-04) | 整数リストxsと整数kを受け取り、現在の並びをひっくりかえして、先頭k個を選んで、各項目からkを引くsolve関数を書いてください。 | ○ | ○ | ○ | × |
| [dev-C07-05](#dev-c07-05) | 整数リストxsと整数kを受け取り、先頭の要素から始めて隔番で取り出して、すべての値を2倍して、kを超える値を残すsolve関数を書いてください。 | × | ○ | ○ | × |
| [dev-C08-01](#dev-c08-01) | 整数リストxsからすべての値を2倍して、すべての値を2倍するsolve関数を書いてください。 | ○ | ○ | ○ | × |
| [dev-C08-02](#dev-c08-02) | 整数リストxsと整数kを受け取り、各要素にkを足して、各要素にkを足して、各要素にkを足すsolve関数を書いてください。 | ○ | ○ | ○ | × |
| [dev-C08-03](#dev-c08-03) | 整数リストxsと整数kを受け取り、各数値からkを引き、各数値からkを引くsolve関数を書いてください。 | ○ | ○ | ○ | × |
| [dev-C08-04](#dev-c08-04) | 整数リストxsから各要素を三倍して、各要素を三倍して、各要素を三倍するsolve関数を書いてください。 | ○ | ○ | ○ | × |
| [dev-C08-05](#dev-c08-05) | 整数リストxsからその時点の先頭の要素から始めて隔番で取り出して、その時点の先頭の要素から始めて隔番で取り出すsolve関数を書いてください。 | × | × | ○ | × |
| [dev-C09-01](#dev-c09-01) | 整数リストxsと整数kを受け取り、偶数を選んで残して、各要素にkを足すsolve関数を書いてください。 | ○ | ○ | ○ | ○ |
| [dev-C09-02](#dev-c09-02) | 整数リストxsと整数kを受け取り、すべての数を二乗して、kを超える値を残すsolve関数を書いてください。 | ○ | ○ | ○ | × |
| [dev-C09-03](#dev-c09-03) | 整数リストxsと整数kを受け取り、先頭k個を選んで、値を小さい順に並べるsolve関数を書いてください。 | ○ | ○ | ○ | × |
| [dev-C09-04](#dev-c09-04) | 整数リストxsと整数kを受け取り、値を小さい順に並べて、最後のk個を取るsolve関数を書いてください。 | ○ | ○ | ○ | × |
| [dev-C09-05](#dev-c09-05) | 整数リストxsから値の符号を逆転して、正の値を選び出すsolve関数を書いてください。 | ○ | ○ | ○ | × |
| [dev-C10-01](#dev-c10-01) | 整数リストxsを処理するsolve(xs, k)を作ってください。値を2で割った余りが0になる要素だけを、出てきた順のまま選び出す処理を行い、結果のリストを返してください。 | × | × | × | ○ |
| [dev-C10-02](#dev-c10-02) | 整数リストxsを処理するsolve(xs, k)を作ってください。各要素を数直線上での0からの距離に置き換える処理を行い、結果のリストを返してください。 | × | × | × | × |
| [dev-C10-03](#dev-c10-03) | 整数リストxsを処理するsolve(xs, k)を作ってください。今の末尾を最初にして、要素を末尾側から一つずつたどった並びにする処理を行い、結果のリストを返してください。 | × | × | × | × |
| [dev-C10-04](#dev-c10-04) | solve(xs, k)をお願いします。整数リストxsについて、左端から数えてk番目までにある要素を、今の順番で取り出す。要素がk個に満たなければ全部を取り出す。結果をリストで返してください。 | × | × | × | ○ |
| [dev-C10-05](#dev-c10-05) | 整数リストxsを処理するsolve(xs, k)を作ってください。どの要素についても、その値から同じ整数kを差し引いた値に置き換える処理を行い、結果のリストを返してください。 | × | × | × | ○ |

## 4. 追加2モデルの全プロンプト・生成結果

「生出力」は修正せず掲載。「採点」には最初に失敗した入力・期待値・実際値または例外を掲載する。静的検査で拒否したものには実測反例がない。合格は179ケースでの一致であり、全入力での正しさの証明ではない。

### dev-C01-01

**日本語指示:**

````text
整数リストxsから偶数を選んで残すsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsから偶数だけを残すsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c01-01)

#### Boku1-nano 5M・1epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsから偶数を選んで残すsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result = []
    for value in xs:
        if value % 2 == 0:
            result += [value]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C01-01",
  "category_id": "C01",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.168秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsから偶数を選んで残すsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output = [value for value in xs if value % 2 == 0]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C01-01",
  "category_id": "C01",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.109秒。

### dev-C01-02

**日本語指示:**

````text
整数リストxsから奇数を残すようにするsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsから奇数だけを残すsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c01-02)

#### Boku1-nano 5M・1epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsから奇数を残すようにするsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = []
    for x in xs:
        if 0 != x % 2:
            result += [x]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C01-02",
  "category_id": "C01",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.147秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsから奇数を残すようにするsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output = []
    for x in xs:
        if 0 != x % 2:
            output += [x]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C01-02",
  "category_id": "C01",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.105秒。

### dev-C01-03

**日本語指示:**

````text
整数リストxsが与えられます。正の値を選び出す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsから正の値だけを残すsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c01-03)

#### Boku1-nano 5M・1epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsが与えられます。正の値を選び出す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = [value for value in xs if value > k]
    output: list[int] = []
    for x in result:
        output += [x ** 2]
    result = [value for value in output if value > 0]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C01-03",
  "category_id": "C01",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 2,
  "xs": [
    1
  ],
  "k": 1,
  "expected": [
    1
  ],
  "actual": "[]"
}
````

終了: `eos`。生成時間: 0.216秒。

#### Boku1-nano 1M・3epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsが与えられます。正の値を選び出す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output = [value for value in xs if 0 == value % k]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C01-03",
  "category_id": "C01",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 1,
  "xs": [
    0
  ],
  "k": 1,
  "expected": [],
  "actual": "[0]"
}
````

終了: `eos`。生成時間: 0.068秒。

### dev-C01-04

**日本語指示:**

````text
整数リストxsから負の値を残すsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsから負の値だけを残すsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c01-04)

#### Boku1-nano 5M・1epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsから負の値を残すsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output: list[int] = [value for value in xs if value < 0]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C01-04",
  "category_id": "C01",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.104秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsから負の値を残すsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = [value for value in xs if 0 > value]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C01-04",
  "category_id": "C01",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.058秒。

### dev-C01-05

**日本語指示:**

````text
整数リストxsが与えられます。ゼロを選び出す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsからゼロだけを残すsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c01-05)

#### Boku1-nano 5M・1epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsが与えられます。ゼロを選び出す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = [value for value in xs if value > k]
    output: list[int] = []
    for x in result:
        output += [x ** 2]
    result = [value for value in output if 0 != value % 2]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C01-05",
  "category_id": "C01",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 1,
  "xs": [
    0
  ],
  "k": 1,
  "expected": [
    0
  ],
  "actual": "[]"
}
````

終了: `eos`。生成時間: 0.230秒。

#### Boku1-nano 1M・3epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsが与えられます。ゼロを選び出す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output = [value for value in xs if value % 2 == 0]
    result = []
    for value in output:
        if value < k:
            result += [value]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C01-05",
  "category_id": "C01",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 6,
  "xs": [
    5,
    4,
    3,
    2,
    1
  ],
  "k": 5,
  "expected": [],
  "actual": "[4, 2]"
}
````

終了: `eos`。生成時間: 0.086秒。

### dev-C02-01

**日本語指示:**

````text
整数リストxsと整数kを受け取り、kを超える値を残すsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsと整数kを受け取り、kより大きい値だけを残すsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c02-01)

#### Boku1-nano 5M・1epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、kを超える値を残すsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output: list[int] = []
    for value in xs:
        if value > k:
            output += [value]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C02-01",
  "category_id": "C02",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.128秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、kを超える値を残すsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = [value for value in xs if k < value]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C02-01",
  "category_id": "C02",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.060秒。

### dev-C02-02

**日本語指示:**

````text
整数リストxsと整数kが与えられます。k以上の項目を残す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsと整数kを受け取り、k以上の値だけを残すsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c02-02)

#### Boku1-nano 5M・1epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kが与えられます。k以上の項目を残す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = xs[::-1]
    result = [x for x in result if x > k]
    output = []
    for value in result:
        output += [value * 3]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C02-02",
  "category_id": "C02",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 2,
  "xs": [
    1
  ],
  "k": 1,
  "expected": [
    1
  ],
  "actual": "[]"
}
````

終了: `eos`。生成時間: 0.167秒。

#### Boku1-nano 1M・3epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kが与えられます。k以上の項目を残す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result = []
    for value in xs:
        result += [-value]
    output = []
    for value in result:
        if value % 2 == 0:
            output += [value]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C02-02",
  "category_id": "C02",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 1,
  "xs": [
    0
  ],
  "k": 1,
  "expected": [],
  "actual": "[0]"
}
````

終了: `eos`。生成時間: 0.096秒。

### dev-C02-03

**日本語指示:**

````text
整数リストxsと整数kが与えられます。k未満の値のみを残す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsと整数kを受け取り、kより小さい値だけを残すsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c02-03)

#### Boku1-nano 5M・1epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kが与えられます。k未満の値のみを残す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = xs[::-1]
    output: list[int] = []
    for value in result:
        output += [value * 3]
    result = [value for value in output if value > k]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C02-03",
  "category_id": "C02",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 1,
  "xs": [
    0
  ],
  "k": 1,
  "expected": [
    0
  ],
  "actual": "[]"
}
````

終了: `eos`。生成時間: 0.142秒。

#### Boku1-nano 1M・3epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kが与えられます。k未満の値のみを残す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result = []
    for value in xs:
        result += [-value]
    output = []
    for value in result:
        if value < k:
            output += [value]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C02-03",
  "category_id": "C02",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 2,
  "xs": [
    1
  ],
  "k": 1,
  "expected": [],
  "actual": "[-1]"
}
````

終了: `eos`。生成時間: 0.093秒。

### dev-C02-04

**日本語指示:**

````text
整数リストxsと整数kが与えられます。k以下の値のみを残す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsと整数kを受け取り、k以下の値だけを残すsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c02-04)

#### Boku1-nano 5M・1epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kが与えられます。k以下の値のみを残す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = [value * value for value in xs]
    result = [value for value in result if value > 0]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C02-04",
  "category_id": "C02",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 1,
  "xs": [
    0
  ],
  "k": 1,
  "expected": [
    0
  ],
  "actual": "[]"
}
````

終了: `eos`。生成時間: 0.106秒。

#### Boku1-nano 1M・3epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kが与えられます。k以下の値のみを残す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result = []
    for value in xs:
        result += [-value]
    output = []
    for value in result:
        if value % 2 == 0:
            output += [value]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C02-04",
  "category_id": "C02",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 2,
  "xs": [
    1
  ],
  "k": 1,
  "expected": [
    1
  ],
  "actual": "[]"
}
````

終了: `eos`。生成時間: 0.103秒。

### dev-C02-05

**日本語指示:**

````text
整数リストxsと整数kが与えられます。kの倍数だけを選び出す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsと整数kを受け取り、kの倍数だけを残すsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c02-05)

#### Boku1-nano 5M・1epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kが与えられます。kの倍数だけを選び出す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = []
    for value in xs:
        result += [value * 3]
    result = [value for value in result if value > 0]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C02-05",
  "category_id": "C02",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 1,
  "xs": [
    0
  ],
  "k": 1,
  "expected": [
    0
  ],
  "actual": "[]"
}
````

終了: `eos`。生成時間: 0.115秒。

#### Boku1-nano 1M・3epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kが与えられます。kの倍数だけを選び出す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result = []
    for value in xs:
        result += [-value]
    output = []
    for value in result:
        if value % 2 == 0:
            output += [value]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C02-05",
  "category_id": "C02",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 2,
  "xs": [
    1
  ],
  "k": 1,
  "expected": [
    1
  ],
  "actual": "[]"
}
````

終了: `eos`。生成時間: 0.096秒。

### dev-C03-01

**日本語指示:**

````text
整数リストxsと整数kが与えられます。各要素にkを足す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsと整数kを受け取り、各要素にkを加えるsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c03-01)

#### Boku1-nano 5M・1epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kが与えられます。各要素にkを足す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = []
    for value in xs:
        result += [value + k]
    result = [value * 3 for value in result]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C03-01",
  "category_id": "C03",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 1,
  "xs": [
    0
  ],
  "k": 1,
  "expected": [
    1
  ],
  "actual": "[3]"
}
````

終了: `eos`。生成時間: 0.115秒。

#### Boku1-nano 1M・3epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kが与えられます。各要素にkを足す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result = []
    for value in xs:
        result += [-value]
    output = []
    for value in result:
        if value % 2 == 0:
            output += [value]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C03-01",
  "category_id": "C03",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 1,
  "xs": [
    0
  ],
  "k": 1,
  "expected": [
    1
  ],
  "actual": "[0]"
}
````

終了: `eos`。生成時間: 0.095秒。

### dev-C03-02

**日本語指示:**

````text
整数リストxsと整数kが与えられます。各項目からkを引く処理をするsolve(xs, k)を作成し、結果をリストで返してください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsと整数kを受け取り、各要素からkを引くsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c03-02)

#### Boku1-nano 5M・1epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kが与えられます。各項目からkを引く処理をするsolve(xs, k)を作成し、結果をリストで返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = []
    for value in xs:
        result += [value - k]
    result = [value * 3 for value in result]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C03-02",
  "category_id": "C03",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 1,
  "xs": [
    0
  ],
  "k": 1,
  "expected": [
    -1
  ],
  "actual": "[-3]"
}
````

終了: `eos`。生成時間: 0.115秒。

#### Boku1-nano 1M・3epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kが与えられます。各項目からkを引く処理をするsolve(xs, k)を作成し、結果をリストで返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result = []
    for value in xs:
        result += [-value]
    output = []
    for value in result:
        if value % 2 == 0:
            output += [value]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C03-02",
  "category_id": "C03",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 1,
  "xs": [
    0
  ],
  "k": 1,
  "expected": [
    -1
  ],
  "actual": "[0]"
}
````

終了: `eos`。生成時間: 0.094秒。

### dev-C03-03

**日本語指示:**

````text
整数リストxsと整数kを受け取り、すべての要素をk倍するsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsと整数kを受け取り、各要素にkを掛けるsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c03-03)

#### Boku1-nano 5M・1epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、すべての要素をk倍するsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = []
    for value in xs:
        result += [value * k]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C03-03",
  "category_id": "C03",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.107秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、すべての要素をk倍するsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = []
    for x in xs:
        result += [x * k]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C03-03",
  "category_id": "C03",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.058秒。

### dev-C03-04

**日本語指示:**

````text
整数リストxsが与えられます。値の符号を逆転する処理をするsolve(xs, k)を作成し、結果をリストで返してください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsから各要素の符号を反転するsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c03-04)

#### Boku1-nano 5M・1epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsが与えられます。値の符号を逆転する処理をするsolve(xs, k)を作成し、結果をリストで返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = []
    for value in xs:
        result += [value * 3]
    result = [value for value in result if value % 2 != 0]
    output = []
    for value in result:
        output += [value * 3]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C03-04",
  "category_id": "C03",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 1,
  "xs": [
    0
  ],
  "k": 1,
  "expected": [
    0
  ],
  "actual": "[]"
}
````

終了: `eos`。生成時間: 0.169秒。

#### Boku1-nano 1M・3epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsが与えられます。値の符号を逆転する処理をするsolve(xs, k)を作成し、結果をリストで返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output = []
    for value in xs:
        output += [-value]
    result = []
    for value in output:
        if value < k:
            result += [value]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C03-04",
  "category_id": "C03",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 5,
  "xs": [
    -5,
    -1,
    0,
    1,
    5
  ],
  "k": 2,
  "expected": [
    5,
    1,
    0,
    -1,
    -5
  ],
  "actual": "[1, 0, -1, -5]"
}
````

終了: `eos`。生成時間: 0.092秒。

### dev-C03-05

**日本語指示:**

````text
整数リストxsからすべての数を二乗するsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsから各要素を二乗するsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c03-05)

#### Boku1-nano 5M・1epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsからすべての数を二乗するsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = []
    for value in xs:
        result += [value * value]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C03-05",
  "category_id": "C03",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.088秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsからすべての数を二乗するsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = []
    for value in xs:
        result += [value ** 2]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C03-05",
  "category_id": "C03",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.066秒。

### dev-C04-01

**日本語指示:**

````text
整数リストxsから値を小さい順に並べるsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsから値を昇順に並べるsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c04-01)

#### Boku1-nano 5M・1epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsから値を小さい順に並べるsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output: list[int] = sorted(xs, reverse=False)
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C04-01",
  "category_id": "C04",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.080秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsから値を小さい順に並べるsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = sorted(xs, reverse=False)
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C04-01",
  "category_id": "C04",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.054秒。

### dev-C04-02

**日本語指示:**

````text
整数リストxsから値を大きいほうから小さいほうへ並べるsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsから値を降順に並べるsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c04-02)

#### Boku1-nano 5M・1epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsから値を大きいほうから小さいほうへ並べるsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output: list[int] = sorted(xs)[::-1]
    result: list[int] = []
    for value in output:
        if value == 0:
            result += [value]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C04-02",
  "category_id": "C04",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 2,
  "xs": [
    1
  ],
  "k": 1,
  "expected": [
    1
  ],
  "actual": "[]"
}
````

終了: `eos`。生成時間: 0.123秒。

#### Boku1-nano 1M・3epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsから値を大きいほうから小さいほうへ並べるsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = sorted(xs, reverse=True)
    output: list[int] = []
    for value in result:
        if value <= k:
            output += [value]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C04-02",
  "category_id": "C04",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 5,
  "xs": [
    -5,
    -1,
    0,
    1,
    5
  ],
  "k": 2,
  "expected": [
    5,
    1,
    0,
    -1,
    -5
  ],
  "actual": "[1, 0, -1, -5]"
}
````

終了: `eos`。生成時間: 0.090秒。

### dev-C04-03

**日本語指示:**

````text
整数リストxsから現在の並びをひっくりかえすsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsから現在の要素順を反転するsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c04-03)

#### Boku1-nano 5M・1epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsから現在の並びをひっくりかえすsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output: list[int] = list(reversed(xs))
    result: list[int] = []
    for value in output:
        if value == 0:
            result += [value]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C04-03",
  "category_id": "C04",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 2,
  "xs": [
    1
  ],
  "k": 1,
  "expected": [
    1
  ],
  "actual": "[]"
}
````

終了: `eos`。生成時間: 0.123秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsから現在の並びをひっくりかえすsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output: list[int] = xs[::-1]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C04-03",
  "category_id": "C04",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.049秒。

### dev-C04-04

**日本語指示:**

````text
整数リストxsから小さい順に並べるsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsから値を昇順に並べるsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c04-04)

#### Boku1-nano 5M・1epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsから小さい順に並べるsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output: list[int] = sorted(xs, reverse=False)
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C04-04",
  "category_id": "C04",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.080秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsから小さい順に並べるsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = sorted(xs, reverse=False)
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C04-04",
  "category_id": "C04",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.056秒。

### dev-C04-05

**日本語指示:**

````text
整数リストxsから順序を逆にするsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsから現在の要素順を反転するsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c04-05)

#### Boku1-nano 5M・1epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsから順序を逆にするsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = xs[::-1]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C04-05",
  "category_id": "C04",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.071秒。

#### Boku1-nano 1M・3epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsから順序を逆にするsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = list(reversed(xs))
    output: list[int] = []
    for value in result:
        if ]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C04-05",
  "category_id": "C04",
  "passed": false,
  "reason": "syntax_error",
  "error": "unmatched ']' (<unknown>, line 5)"
}
````

終了: `eos`。生成時間: 0.067秒。

### dev-C05-01

**日本語指示:**

````text
整数リストxsと整数kが与えられます。先頭k個を選ぶ処理をするsolve(xs, k)を作成し、結果をリストで返してください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsと整数kを受け取り、先頭からk個を取るsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c05-01)

#### Boku1-nano 5M・1epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kが与えられます。先頭k個を選ぶ処理をするsolve(xs, k)を作成し、結果をリストで返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = xs[0:k]
    output: list[int] = [value * 3 for value in result]
    result = []
    for value in output:
        if k < value:
            result += [value]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C05-01",
  "category_id": "C05",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 1,
  "xs": [
    0
  ],
  "k": 1,
  "expected": [
    0
  ],
  "actual": "[]"
}
````

終了: `eos`。生成時間: 0.140秒。

#### Boku1-nano 1M・3epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kが与えられます。先頭k個を選ぶ処理をするsolve(xs, k)を作成し、結果をリストで返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result = []
    for value in xs:
        result += [-value]
    output = result[0:k]
    result = []
    for x in output:
        if x % 2 == 0:
            result += [x]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C05-01",
  "category_id": "C05",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 2,
  "xs": [
    1
  ],
  "k": 1,
  "expected": [
    1
  ],
  "actual": "[]"
}
````

終了: `eos`。生成時間: 0.113秒。

### dev-C05-02

**日本語指示:**

````text
整数リストxsと整数kを受け取り、最後のk個を取るsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsと整数kを受け取り、末尾からk個を取るsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c05-02)

#### Boku1-nano 5M・1epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、最後のk個を取るsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = []
    for value in xs:
        result += [value - k]
    result = result[-k:]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C05-02",
  "category_id": "C05",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 1,
  "xs": [
    0
  ],
  "k": 1,
  "expected": [
    0
  ],
  "actual": "[-1]"
}
````

終了: `eos`。生成時間: 0.106秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、最後のk個を取るsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output: list[int] = xs[-k::]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C05-02",
  "category_id": "C05",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.048秒。

### dev-C05-03

**日本語指示:**

````text
整数リストxsから先頭の要素から始めて隔番で取り出すsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsから先頭から1個おきに取るsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c05-03)

#### Boku1-nano 5M・1epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsから先頭の要素から始めて隔番で取り出すsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = xs[0::2]
    output: list[int] = []
    for value in result:
        output += [value * 2]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C05-03",
  "category_id": "C05",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 2,
  "xs": [
    1
  ],
  "k": 1,
  "expected": [
    1
  ],
  "actual": "[2]"
}
````

終了: `eos`。生成時間: 0.123秒。

#### Boku1-nano 1M・3epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsから先頭の要素から始めて隔番で取り出すsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    return [value for value in sorted(xs, reverse=True)[0::2]
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C05-03",
  "category_id": "C05",
  "passed": false,
  "reason": "syntax_error",
  "error": "'[' was never closed (<unknown>, line 2)"
}
````

終了: `eos`。生成時間: 0.070秒。

### dev-C05-04

**日本語指示:**

````text
整数リストxsと整数kが与えられます。頭k個を抜き出す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsと整数kを受け取り、先頭からk個を取るsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c05-04)

#### Boku1-nano 5M・1epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kが与えられます。頭k個を抜き出す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = xs[0:k]
    result = [value * 3 for value in result]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C05-04",
  "category_id": "C05",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 2,
  "xs": [
    1
  ],
  "k": 1,
  "expected": [
    1
  ],
  "actual": "[3]"
}
````

終了: `eos`。生成時間: 0.094秒。

#### Boku1-nano 1M・3epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kが与えられます。頭k個を抜き出す処理をするsolve(xs, k)を作成し、結果をリストで返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result = []
    for value in xs:
        result += [-value]
    output = result[0:k]
    result = []
    for x in output:
        if x % 2 == 0:
            result += [x]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C05-04",
  "category_id": "C05",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 2,
  "xs": [
    1
  ],
  "k": 1,
  "expected": [
    1
  ],
  "actual": "[]"
}
````

終了: `eos`。生成時間: 0.099秒。

### dev-C05-05

**日本語指示:**

````text
整数リストxsと整数kが与えられます。最後k個を切り取る処理をするsolve(xs, k)を作成し、結果をリストで返してください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsと整数kを受け取り、末尾からk個を取るsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c05-05)

#### Boku1-nano 5M・1epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kが与えられます。最後k個を切り取る処理をするsolve(xs, k)を作成し、結果をリストで返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = xs[-k::]
    output: list[int] = []
    for value in result:
        output += [value * 3]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C05-05",
  "category_id": "C05",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 2,
  "xs": [
    1
  ],
  "k": 1,
  "expected": [
    1
  ],
  "actual": "[3]"
}
````

終了: `eos`。生成時間: 0.123秒。

#### Boku1-nano 1M・3epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kが与えられます。最後k個を切り取る処理をするsolve(xs, k)を作成し、結果をリストで返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result = []
    for value in xs:
        result += [-value]
    output = result[0:k]
    result = []
    for value in output:
        if value % 2 == 0:
            result += [value]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C05-05",
  "category_id": "C05",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 2,
  "xs": [
    1
  ],
  "k": 1,
  "expected": [
    1
  ],
  "actual": "[]"
}
````

終了: `eos`。生成時間: 0.103秒。

### dev-C06-01

**日本語指示:**

````text
整数リストxsから偶数を選んで残して、すべての値を2倍するsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsから偶数だけを残し、各要素を2倍するsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c06-01)

#### Boku1-nano 5M・1epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsから偶数を選んで残して、すべての値を2倍するsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = [value for value in xs if 0 == value % 2]
    output: list[int] = []
    for value in result:
        output += [value * 2]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C06-01",
  "category_id": "C06",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.132秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsから偶数を選んで残して、すべての値を2倍するsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output = [value for value in xs if value % 2 == 0]
    result = [x * 2 for x in output]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C06-01",
  "category_id": "C06",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.080秒。

### dev-C06-02

**日本語指示:**

````text
整数リストxsから負の値を残して、各要素の絶対値を取るsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsから負の値だけを残し、各要素の絶対値を取るsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c06-02)

#### Boku1-nano 5M・1epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsから負の値を残して、各要素の絶対値を取るsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = [value for value in xs if value < 0]
    output: list[int] = []
    for value in result:
        output += [abs(value)]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C06-02",
  "category_id": "C06",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.130秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsから負の値を残して、各要素の絶対値を取るsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output = []
    for x in xs:
        if 0 > x:
            output += [x]
    result = []
    for value in output:
        result += [abs(value)]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C06-02",
  "category_id": "C06",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.102秒。

### dev-C06-03

**日本語指示:**

````text
整数リストxsと整数kを受け取り、最後のk個をとって、現在の並びをひっくりかえすsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsと整数kを受け取り、末尾からk個を取り、現在の要素順を反転するsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c06-03)

#### Boku1-nano 5M・1epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、最後のk個をとって、現在の並びをひっくりかえすsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output: list[int] = xs[-k:]
    result: list[int] = output[::-1]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C06-03",
  "category_id": "C06",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.126秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、最後のk個をとって、現在の並びをひっくりかえすsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output: list[int] = xs[-k::]
    result: list[int] = list(reversed(output))
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C06-03",
  "category_id": "C06",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.071秒。

### dev-C06-04

**日本語指示:**

````text
整数リストxsと整数kを受け取り、すべての要素をk倍して、値を降順に整理するsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsと整数kを受け取り、各要素にkを掛け、値を降順に並べるsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c06-04)

#### Boku1-nano 5M・1epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、すべての要素をk倍して、値を降順に整理するsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = []
    for x in xs:
        result += [x * k]
    output: list[int] = sorted(result)[::-1]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C06-04",
  "category_id": "C06",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.120秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、すべての要素をk倍して、値を降順に整理するsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output = []
    for x in xs:
        output += [x * k]
    output = sorted(output)[::-1]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C06-04",
  "category_id": "C06",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.080秒。

### dev-C06-05

**日本語指示:**

````text
整数リストxsからすべての数を二乗して、先頭の要素から始めて隔番で取り出すsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsから各要素を二乗し、先頭から1個おきに取るsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c06-05)

#### Boku1-nano 5M・1epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsからすべての数を二乗して、先頭の要素から始めて隔番で取り出すsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = []
    for value in xs:
        result += [value ** 2]
    output: list[int] = result[0::2]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C06-05",
  "category_id": "C06",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.125秒。

#### Boku1-nano 1M・3epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsからすべての数を二乗して、先頭の要素から始めて隔番で取り出すsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output: list[int] = []
    for value in xs:
        output += [value ** 2]
    output = output[::2]
    output = output[0::2]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C06-05",
  "category_id": "C06",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 4,
  "xs": [
    0,
    0,
    0
  ],
  "k": 3,
  "expected": [
    0,
    0
  ],
  "actual": "[0]"
}
````

終了: `eos`。生成時間: 0.093秒。

### dev-C07-01

**日本語指示:**

````text
整数リストxsから奇数だけを残し、各要素を三倍して、値を小さい順に並べるsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsから奇数だけを残し、各要素を3倍し、値を昇順に並べるsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c07-01)

#### Boku1-nano 5M・1epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsから奇数だけを残し、各要素を三倍して、値を小さい順に並べるsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = [value for value in xs if 0 != value % 2]
    output: list[int] = [x * 3 for x in result]
    output = sorted(output, reverse=False)
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C07-01",
  "category_id": "C07",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.137秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsから奇数だけを残し、各要素を三倍して、値を小さい順に並べるsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result = [value for value in xs if 0 != value % 2]
    output = []
    for x in result:
        output += [x * 3]
    output = sorted(output)
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C07-01",
  "category_id": "C07",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.101秒。

### dev-C07-02

**日本語指示:**

````text
整数リストxsと整数kを受け取り、正の値を選び出して、各要素にkを足して、最後のk個を取るsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsと整数kを受け取り、正の値だけを残し、各要素にkを加え、末尾からk個を取るsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c07-02)

#### Boku1-nano 5M・1epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、正の値を選び出して、各要素にkを足して、最後のk個を取るsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    # 正の値だけを残す
    result = [value for value in xs if 0 < value]
    # 各要素にkを加える
    output = []
    for x in result:
        output += [x + k]
    # 末尾からk個を取る
    output = output[-k:]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C07-02",
  "category_id": "C07",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.193秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、正の値を選び出して、各要素にkを足して、最後のk個を取るsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    # 正の値だけを残す
    output: list[int] = [value for value in xs if value > 0]
    # 各要素にkを加える
    result: list[int] = []
    for x in output:
        result += [x + k]
    # 末尾からk個を取る
    output = result[-k::]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C07-02",
  "category_id": "C07",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.160秒。

### dev-C07-03

**日本語指示:**

````text
整数リストxsと整数kを受け取り、各要素の絶対値を取って、k以上の項目を残し、値を大きいほうから小さいほうへ並べるsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsと整数kを受け取り、各要素の絶対値を取り、k以上の値だけを残し、値を降順に並べるsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c07-03)

#### Boku1-nano 5M・1epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、各要素の絶対値を取って、k以上の項目を残し、値を大きいほうから小さいほうへ並べるsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output: list[int] = []
    for value in xs:
        output += [abs(value)]
    result: list[int] = [value for value in output if value >= k]
    output = sorted(result, reverse=True)
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C07-03",
  "category_id": "C07",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.141秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、各要素の絶対値を取って、k以上の項目を残し、値を大きいほうから小さいほうへ並べるsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    # 各要素の絶対値を取る
    result: list[int] = [abs(value) for value in xs]
    # k以上の値だけを残す
    output: list[int] = [x for x in result if k <= x]
    # 降順に並べる
    output = sorted(output)[::-1]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C07-03",
  "category_id": "C07",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.130秒。

### dev-C07-04

**日本語指示:**

````text
整数リストxsと整数kを受け取り、現在の並びをひっくりかえして、先頭k個を選んで、各項目からkを引くsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsと整数kを受け取り、現在の要素順を反転し、先頭からk個を取り、各要素からkを引くsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c07-04)

#### Boku1-nano 5M・1epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、現在の並びをひっくりかえして、先頭k個を選んで、各項目からkを引くsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output: list[int] = list(reversed(xs))
    result: list[int] = []
    for x in output:
        result += [x - k]
    result = result[:k]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C07-04",
  "category_id": "C07",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.122秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、現在の並びをひっくりかえして、先頭k個を選んで、各項目からkを引くsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    # 現在の要素順を反転する
    output: list[int] = list(reversed(xs))
    # 先頭からk個を取る
    result: list[int] = output[:k]
    # 各要素からkを引く
    output = [value - k for value in result]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C07-04",
  "category_id": "C07",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.121秒。

### dev-C07-05

**日本語指示:**

````text
整数リストxsと整数kを受け取り、先頭の要素から始めて隔番で取り出して、すべての値を2倍して、kを超える値を残すsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsと整数kを受け取り、先頭から1個おきに取り、各要素を2倍し、kより大きい値だけを残すsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c07-05)

#### Boku1-nano 5M・1epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、先頭の要素から始めて隔番で取り出して、すべての値を2倍して、kを超える値を残すsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = xs[0::2]
    output: list[int] = []
    for value in result:
        output += [value * 2]
    result = [x for x in output if x > k]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C07-05",
  "category_id": "C07",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.140秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、先頭の要素から始めて隔番で取り出して、すべての値を2倍して、kを超える値を残すsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output: list[int] = xs[::2]
    result: list[int] = [value * 2 for value in output]
    output = []
    for x in result:
        if x > k:
            output += [x]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C07-05",
  "category_id": "C07",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.094秒。

### dev-C08-01

**日本語指示:**

````text
整数リストxsからすべての値を2倍して、すべての値を2倍するsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsから各要素を2倍し、各要素を2倍するsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c08-01)

#### Boku1-nano 5M・1epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsからすべての値を2倍して、すべての値を2倍するsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = []
    for value in xs:
        result += [value * 2]
    output: list[int] = [x * 2 for x in result]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C08-01",
  "category_id": "C08",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.114秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsからすべての値を2倍して、すべての値を2倍するsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = []
    for value in xs:
        result += [value * 2]
    output: list[int] = [x * 2 for x in result]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C08-01",
  "category_id": "C08",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.081秒。

### dev-C08-02

**日本語指示:**

````text
整数リストxsと整数kを受け取り、各要素にkを足して、各要素にkを足して、各要素にkを足すsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsと整数kを受け取り、各要素にkを加え、各要素にkを加え、各要素にkを加えるsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c08-02)

#### Boku1-nano 5M・1epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、各要素にkを足して、各要素にkを足して、各要素にkを足すsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    # 各要素にkを加える
    result: list[int] = [value + k for value in xs]
    # 各要素にkを加える
    output = [value + k for value in result]
    # 各要素にkを加える
    result = [value + k for value in output]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C08-02",
  "category_id": "C08",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.185秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、各要素にkを足して、各要素にkを足して、各要素にkを足すsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    # 各要素にkを加える
    output: list[int] = []
    for value in xs:
        output += [value + k]
    # 各要素にkを加える
    result: list[int] = []
    for value in output:
        result += [value + k]
    # 各要素にkを加える
    output = [value + k for value in result]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C08-02",
  "category_id": "C08",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.142秒。

### dev-C08-03

**日本語指示:**

````text
整数リストxsと整数kを受け取り、各数値からkを引き、各数値からkを引くsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsと整数kを受け取り、各要素からkを引き、各要素からkを引くsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c08-03)

#### Boku1-nano 5M・1epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、各数値からkを引き、各数値からkを引くsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = [value - k for value in xs]
    output: list[int] = [value - k for value in result]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C08-03",
  "category_id": "C08",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.106秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、各数値からkを引き、各数値からkを引くsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result = [value - k for value in xs]
    output = []
    for x in result:
        output += [x - k]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C08-03",
  "category_id": "C08",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.087秒。

### dev-C08-04

**日本語指示:**

````text
整数リストxsから各要素を三倍して、各要素を三倍して、各要素を三倍するsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsから各要素を3倍し、各要素を3倍し、各要素を3倍するsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c08-04)

#### Boku1-nano 5M・1epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsから各要素を三倍して、各要素を三倍して、各要素を三倍するsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = [x * 3 for x in xs]
    result = [x * 3 for x in result]
    output: list[int] = [x * 3 for x in result]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C08-04",
  "category_id": "C08",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.124秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsから各要素を三倍して、各要素を三倍して、各要素を三倍するsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = []
    for value in xs:
        result += [value * 3]
    output: list[int] = []
    for value in result:
        output += [value * 3]
    result = []
    for x in output:
        result += [x * 3]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C08-04",
  "category_id": "C08",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.131秒。

### dev-C08-05

**日本語指示:**

````text
整数リストxsからその時点の先頭の要素から始めて隔番で取り出して、その時点の先頭の要素から始めて隔番で取り出すsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsから先頭から1個おきに取り、先頭から1個おきに取るsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c08-05)

#### Boku1-nano 5M・1epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsからその時点の先頭の要素から始めて隔番で取り出して、その時点の先頭の要素から始めて隔番で取り出すsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = xs[0::2]
    output: list[int] = []
    for value in result:
        output += [-value]
    result = output[0::2]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C08-05",
  "category_id": "C08",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 2,
  "xs": [
    1
  ],
  "k": 1,
  "expected": [
    1
  ],
  "actual": "[-1]"
}
````

終了: `eos`。生成時間: 0.134秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsからその時点の先頭の要素から始めて隔番で取り出して、その時点の先頭の要素から始めて隔番で取り出すsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output: list[int] = xs[0::2]
    output = output[0::2]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C08-05",
  "category_id": "C08",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.059秒。

### dev-C09-01

**日本語指示:**

````text
整数リストxsと整数kを受け取り、偶数を選んで残して、各要素にkを足すsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsと整数kを受け取り、偶数だけを残し、各要素にkを加えるsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c09-01)

#### Boku1-nano 5M・1epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、偶数を選んで残して、各要素にkを足すsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = [value for value in xs if 0 == value % 2]
    output: list[int] = []
    for x in result:
        output += [x + k]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C09-01",
  "category_id": "C09",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.141秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、偶数を選んで残して、各要素にkを足すsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output: list[int] = []
    for x in xs:
        if 0 == x % 2:
            output += [x]
    result: list[int] = [value + k for value in output]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C09-01",
  "category_id": "C09",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.092秒。

### dev-C09-02

**日本語指示:**

````text
整数リストxsと整数kを受け取り、すべての数を二乗して、kを超える値を残すsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsと整数kを受け取り、各要素を二乗し、kより大きい値だけを残すsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c09-02)

#### Boku1-nano 5M・1epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、すべての数を二乗して、kを超える値を残すsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = []
    for value in xs:
        result += [value * value]
    output: list[int] = []
    for value in result:
        if k < value:
            output += [value]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C09-02",
  "category_id": "C09",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.132秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、すべての数を二乗して、kを超える値を残すsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output: list[int] = []
    for x in xs:
        output += [x * x]
    result: list[int] = []
    for value in output:
        if value > k:
            result += [value]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C09-02",
  "category_id": "C09",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.102秒。

### dev-C09-03

**日本語指示:**

````text
整数リストxsと整数kを受け取り、先頭k個を選んで、値を小さい順に並べるsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsと整数kを受け取り、先頭からk個を取り、値を昇順に並べるsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c09-03)

#### Boku1-nano 5M・1epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、先頭k個を選んで、値を小さい順に並べるsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output: list[int] = xs[0:k]
    result: list[int] = sorted(output, reverse=False)
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C09-03",
  "category_id": "C09",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.105秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、先頭k個を選んで、値を小さい順に並べるsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result = xs[0:k]
    result = sorted(result, reverse=False)
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C09-03",
  "category_id": "C09",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.071秒。

### dev-C09-04

**日本語指示:**

````text
整数リストxsと整数kを受け取り、値を小さい順に並べて、最後のk個を取るsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsと整数kを受け取り、値を昇順に並べ、末尾からk個を取るsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c09-04)

#### Boku1-nano 5M・1epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、値を小さい順に並べて、最後のk個を取るsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output: list[int] = sorted(xs)
    result: list[int] = output[-k:]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C09-04",
  "category_id": "C09",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.098秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsと整数kを受け取り、値を小さい順に並べて、最後のk個を取るsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = sorted(xs, reverse=False)
    output: list[int] = result[-k::]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C09-04",
  "category_id": "C09",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.078秒。

### dev-C09-05

**日本語指示:**

````text
整数リストxsから値の符号を逆転して、正の値を選び出すsolve関数を書いてください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsから各要素の符号を反転し、正の値だけを残すsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c09-05)

#### Boku1-nano 5M・1epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsから値の符号を逆転して、正の値を選び出すsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = []
    for value in xs:
        result += [-value]
    output: list[int] = [x for x in result if 0 < x]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C09-05",
  "category_id": "C09",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.116秒。

#### Boku1-nano 1M・3epoch：合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsから値の符号を逆転して、正の値を選び出すsolve関数を書いてください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output: list[int] = []
    for x in xs:
        output += [-x]
    result: list[int] = []
    for value in output:
        if 0 < value:
            result += [value]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C09-05",
  "category_id": "C09",
  "passed": true,
  "reason": "pass",
  "tests_passed": 179
}
````

終了: `eos`。生成時間: 0.092秒。

### dev-C10-01

**日本語指示:**

````text
整数リストxsを処理するsolve(xs, k)を作ってください。値を2で割った余りが0になる要素だけを、出てきた順のまま選び出す処理を行い、結果のリストを返してください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsから偶数だけを残すsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c10-01)

#### Boku1-nano 5M・1epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsを処理するsolve(xs, k)を作ってください。値を2で割った余りが0になる要素だけを、出てきた順のまま選び出す処理を行い、結果のリストを返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = xs[::-1]
    output: list[int] = []
    for value in result:
        output += [abs(x)]
    output = sorted(result, reverse=True)
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C10-01",
  "category_id": "C10",
  "passed": false,
  "reason": "contract_or_allowed_syntax",
  "error": "unsupported_name:x"
}
````

終了: `eos`。生成時間: 0.141秒。

#### Boku1-nano 1M・3epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsを処理するsolve(xs, k)を作ってください。値を2で割った余りが0になる要素だけを、出てきた順のまま選び出す処理を行い、結果のリストを返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = xs[::-1]
    result = [x for x in result if x > k]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C10-01",
  "category_id": "C10",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 1,
  "xs": [
    0
  ],
  "k": 1,
  "expected": [
    0
  ],
  "actual": "[]"
}
````

終了: `eos`。生成時間: 0.070秒。

### dev-C10-02

**日本語指示:**

````text
整数リストxsを処理するsolve(xs, k)を作ってください。各要素を数直線上での0からの距離に置き換える処理を行い、結果のリストを返してください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsから各要素の絶対値を取るsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c10-02)

#### Boku1-nano 5M・1epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsを処理するsolve(xs, k)を作ってください。各要素を数直線上での0からの距離に置き換える処理を行い、結果のリストを返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = sorted(xs)[::-1]
    output: list[int] = []
    for x in result:
        output += [x ** 2]
    output = []
    for value in result:
        output += [abs(x)]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C10-02",
  "category_id": "C10",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 5,
  "xs": [
    -5,
    -1,
    0,
    1,
    5
  ],
  "k": 2,
  "expected": [
    5,
    1,
    0,
    1,
    5
  ],
  "actual": "[5, 5, 5, 5, 5]"
}
````

終了: `eos`。生成時間: 0.159秒。

#### Boku1-nano 1M・3epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsを処理するsolve(xs, k)を作ってください。各要素を数直線上での0からの距離に置き換える処理を行い、結果のリストを返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = xs[::-1]
    result = [x for x in result if x > k]
    result = result[0::2]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C10-02",
  "category_id": "C10",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 1,
  "xs": [
    0
  ],
  "k": 1,
  "expected": [
    0
  ],
  "actual": "[]"
}
````

終了: `eos`。生成時間: 0.087秒。

### dev-C10-03

**日本語指示:**

````text
整数リストxsを処理するsolve(xs, k)を作ってください。今の末尾を最初にして、要素を末尾側から一つずつたどった並びにする処理を行い、結果のリストを返してください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsから現在の要素順を反転するsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c10-03)

#### Boku1-nano 5M・1epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsを処理するsolve(xs, k)を作ってください。今の末尾を最初にして、要素を末尾側から一つずつたどった並びにする処理を行い、結果のリストを返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = sorted(xs, reverse=False)
    output = []
    for value in result:
        output += [value * 3]
    result = sorted(output, reverse=False)
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C10-03",
  "category_id": "C10",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 2,
  "xs": [
    1
  ],
  "k": 1,
  "expected": [
    1
  ],
  "actual": "[3]"
}
````

終了: `eos`。生成時間: 0.151秒。

#### Boku1-nano 1M・3epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsを処理するsolve(xs, k)を作ってください。今の末尾を最初にして、要素を末尾側から一つずつたどった並びにする処理を行い、結果のリストを返してください。
<|code|>
````

生出力:

````python

````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C10-03",
  "category_id": "C10",
  "passed": false,
  "reason": "contract_or_allowed_syntax",
  "error": "one_solve_function_required"
}
````

終了: `eos`。生成時間: 0.009秒。

### dev-C10-04

**日本語指示:**

````text
solve(xs, k)をお願いします。整数リストxsについて、左端から数えてk番目までにある要素を、今の順番で取り出す。要素がk個に満たなければ全部を取り出す。結果をリストで返してください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsと整数kを受け取り、先頭からk個を取るsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c10-04)

#### Boku1-nano 5M・1epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
solve(xs, k)をお願いします。整数リストxsについて、左端から数えてk番目までにある要素を、今の順番で取り出す。要素がk個に満たなければ全部を取り出す。結果をリストで返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = sorted(output, reverse=False)
    result = result[-k::]
    output: list[int] = []
    for value in result:
        output += [abs(x)]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C10-04",
  "category_id": "C10",
  "passed": false,
  "reason": "contract_or_allowed_syntax",
  "error": "unsupported_name:x"
}
````

終了: `eos`。生成時間: 0.151秒。

#### Boku1-nano 1M・3epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
solve(xs, k)をお願いします。整数リストxsについて、左端から数えてk番目までにある要素を、今の順番で取り出す。要素がk個に満たなければ全部を取り出す。結果をリストで返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    output = []
    for value in xs:
        output += [-value]
    result = output[-k:]
    output = []
    for value in result:
        output += [-value]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C10-04",
  "category_id": "C10",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 5,
  "xs": [
    -5,
    -1,
    0,
    1,
    5
  ],
  "k": 2,
  "expected": [
    -5,
    -1
  ],
  "actual": "[1, 5]"
}
````

終了: `eos`。生成時間: 0.100秒。

### dev-C10-05

**日本語指示:**

````text
整数リストxsを処理するsolve(xs, k)を作ってください。どの要素についても、その値から同じ整数kを差し引いた値に置き換える処理を行い、結果のリストを返してください。
````

**期待する処理（モデルに渡していない正解CNL）:**

````text
整数リストxsと整数kを受け取り、各要素からkを引くsolve関数を書いてください。
````

[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#dev-c10-05)

#### Boku1-nano 5M・1epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsを処理するsolve(xs, k)を作ってください。どの要素についても、その値から同じ整数kを差し引いた値に置き換える処理を行い、結果のリストを返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = sorted(xs, reverse=False)
    output: list[int] = []
    for value in result:
        output += [value * k]
    result = []
    for value in output:
        result += [value * k]
    return result
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C10-05",
  "category_id": "C10",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 1,
  "xs": [
    0
  ],
  "k": 1,
  "expected": [
    -1
  ],
  "actual": "[0]"
}
````

終了: `eos`。生成時間: 0.168秒。

#### Boku1-nano 1M・3epoch：不合格

実プロンプト:

````text
<|bos|><|task|>
整数リストxsを処理するsolve(xs, k)を作ってください。どの要素についても、その値から同じ整数kを差し引いた値に置き換える処理を行い、結果のリストを返してください。
<|code|>
````

生出力:

````python
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = xs[::-1]
    output: list[int] = []
    for value in result:
        output += [-value]
    return output
````

採点:

````json
{
  "model": "boku",
  "condition": "A",
  "question_id": "dev-C10-05",
  "category_id": "C10",
  "passed": false,
  "reason": "output_mismatch",
  "test_index": 1,
  "xs": [
    0
  ],
  "k": 1,
  "expected": [
    -1
  ],
  "actual": "[0]"
}
````

終了: `eos`。生成時間: 0.077秒。

## 5. 元データと再現

**Boku1-nano 5M・1epoch**

- [config.json](../../../data/benchmarks/browser_100/runs/dev50-20261005-5m-1epoch/config.json)
- [raw_inference.jsonl](../../../data/benchmarks/browser_100/runs/dev50-20261005-5m-1epoch/raw_inference.jsonl)
- [scored.jsonl](../../../data/benchmarks/browser_100/runs/dev50-20261005-5m-1epoch/scored.jsonl)
- [summary.json](../../../data/benchmarks/browser_100/runs/dev50-20261005-5m-1epoch/summary.json)
- [test_cases.json](../../../data/benchmarks/browser_100/runs/dev50-20261005-5m-1epoch/test_cases.json)
- [source_hashes.json](../../../data/benchmarks/browser_100/runs/dev50-20261005-5m-1epoch/source_hashes.json)

**Boku1-nano 1M・3epoch**

- [config.json](../../../data/benchmarks/browser_100/runs/dev50-20261005-1m-3epoch/config.json)
- [raw_inference.jsonl](../../../data/benchmarks/browser_100/runs/dev50-20261005-1m-3epoch/raw_inference.jsonl)
- [scored.jsonl](../../../data/benchmarks/browser_100/runs/dev50-20261005-1m-3epoch/scored.jsonl)
- [summary.json](../../../data/benchmarks/browser_100/runs/dev50-20261005-1m-3epoch/summary.json)
- [test_cases.json](../../../data/benchmarks/browser_100/runs/dev50-20261005-1m-3epoch/test_cases.json)
- [source_hashes.json](../../../data/benchmarks/browser_100/runs/dev50-20261005-1m-3epoch/source_hashes.json)

追加推論の再実行例（既存の測定を上書きしないよう、新しい出力先を指定）:

````bash
.venv/bin/python scripts/model/run_browser_100_benchmark.py --questions data/benchmarks/browser_100/dev50.jsonl --output data/benchmarks/browser_100/runs/NEW-RUN-ID --run-id NEW-RUN-ID --boku-model 5m-1epoch --models boku --conditions A
````

`--boku-model 1m-3epoch`で1M版を実行できる。サーバーが表示したURLをWebGPU対応ブラウザで開き「評価を開始」を押す。

保存済み結果からこの追記を再生成:

````bash
.venv/bin/python scripts/model/report_browser_additional_models.py
````

<!-- qwen3-4b-awq-mps-addition -->

## 追記：2026年10月6日 Qwen3-4B-AWQの条件A評価

| モデル | 合格 / 50問 | 正答率 | 実行方式 |
| --- | ---: | ---: | --- |
| Boku1-nano 15M・1epoch | 30/50 | 60% | ブラウザ・WebGPU |
| Boku1-nano 5M・1epoch | 28/50 | 56% | ブラウザ・WebGPU |
| Boku1-nano 1M・3epoch | 29/50 | 58% | ブラウザ・WebGPU |
| Qwen3-0.6B | 19/50 | 38% | ブラウザ・WebGPU |
| **Qwen3-4B-AWQ（FP16展開・MPS）** | **32/50** | **64%** | **このMacのPython・Apple GPU** |

追加分も条件Aの同じ50問・同じ179テスト入力・同じ採点器。Qwen3-0.6Bとsystem/userメッセージおよびテンプレート適用後の全文が一致する。greedy、T=0、thinking無効、最大512新規tokens、反復ペナルティ1、会話履歴なし。旧4モデルの数値は前回実測を再掲した。

**実行方式の違い:** 公式`Qwen/Qwen3-4B-AWQ`の4bit量子化済み重みをFP16へ展開してMPSで実行した。元の非量子化4BやMLX版への置換・再量子化はしていない。AWQのCUDAカーネルでの実行とは浮動小数点演算が異なり、出力の完全一致は保証しない。WebGPUの0.6Bとはモデルサイズだけでなく量子化・実行基盤も違うため、速度やサイズ単独の効果を断定する比較には使わない。

### 分類別の合格数（各5問）

| 分類 | 15M・1epoch | 5M・1epoch | 1M・3epoch | Qwen 0.6B | Qwen 4B-AWQ |
| --- | ---: | ---: | ---: | ---: | ---: |
| C01 基本的な抽出 | 4 | 3 | 3 | 4 | 5 |
| C02 kを使う条件 | 1 | 1 | 1 | 1 | 2 |
| C03 値の変換 | 2 | 2 | 2 | 5 | 4 |
| C04 順序の変更 | 5 | 3 | 3 | 0 | 5 |
| C05 切り出し | 1 | 0 | 1 | 2 | 2 |
| C06 2操作の合成 | 4 | 5 | 4 | 3 | 2 |
| C07 3操作の合成 | 4 | 5 | 5 | 0 | 4 |
| C08 同じ操作の反復 | 4 | 4 | 5 | 0 | 0 |
| C09 順序を取り違えやすい合成 | 5 | 5 | 5 | 1 | 4 |
| C10 未学習の言い回し | 0 | 0 | 0 | 3 | 4 |

追加モデルの不合格は18問。理由別: `output_mismatch` 14件、`runtime_error` 3件、`contract_or_allowed_syntax` 1件。

0.6Bの19問から4Bは32問へ増えた。基本抽出と順序変更は5/5、新しい言い回しは4/5。一方、同一操作の反復は0/5で、kの比較方向や取り出す部分の誤りも残った。Boku 15M（30問）との差は2問であり、この50問から一般的な優劣は断定しない。

**例:** 「kを足す」を3回要求しても`x + k`しか生成せず、`xs=[0], k=1`で期待`[3]`に対し`[1]`となった。「k以上を残す」では不要なソートを追加し、`xs=[53,-28,35,-66,-69,-14,-23], k=1`で期待`[53,35]`に対し`[35,53]`となった。

[追加50問の実プロンプト・生出力・採点・反例](dev50_20261006_qwen3_4b_awq.md)

