# 単独操作の意味AST定義

## 概要

日本語の指示やPythonコードを生成する前に、問題が表す処理を意味ASTとして定義する。

現時点では操作を組み合わせず、対象となる24種類の操作を、それぞれ独立した意味ASTとして定義している。定義したデータは `data/semantic_asts/atomic_semantic_asts.jsonl` に、1操作につき1レコードで保存する。

## レコード形式

各レコードは、識別子である `spec_id` と、操作の意味を表す `semantic_ast` を持つ。

```json
{
  "spec_id": "atomic-000001",
  "semantic_ast": {
    "filter": ["even"]
  }
}
```

- `spec_id`: 各レコードを一意に識別するID
- `semantic_ast`: 処理内容を機械的に表した意味AST

## 抽出

`xs`の各要素を条件で判定し、条件を満たした要素だけを残す操作である。

| ID | 意味 | semantic_ast |
|---|---|---|
| `atomic-000001` | 偶数だけを残す | `{"filter":["even"]}` |
| `atomic-000002` | 奇数だけを残す | `{"filter":["odd"]}` |
| `atomic-000003` | `k`より大きい値だけを残す | `{"filter":["gt_k"]}` |
| `atomic-000004` | `k`以上の値だけを残す | `{"filter":["ge_k"]}` |
| `atomic-000005` | `k`より小さい値だけを残す | `{"filter":["lt_k"]}` |
| `atomic-000006` | `k`以下の値だけを残す | `{"filter":["le_k"]}` |
| `atomic-000007` | `k`の倍数だけを残す | `{"filter":["multiple_of_k"]}` |
| `atomic-000008` | 正の値だけを残す | `{"filter":["positive"]}` |
| `atomic-000009` | 負の値だけを残す | `{"filter":["negative"]}` |
| `atomic-000010` | ゼロだけを残す | `{"filter":["zero"]}` |

比較演算子の名前は、次の略称を使用する。

- `gt`: greater than（より大きい）
- `ge`: greater than or equal（以上）
- `lt`: less than（より小さい）
- `le`: less than or equal（以下）

## 変換

`xs`の各要素を、指定された規則で別の整数へ変換する操作である。

| ID | 意味 | semantic_ast |
|---|---|---|
| `atomic-000011` | 各要素に`k`を加える | `{"map":["add_k"]}` |
| `atomic-000012` | 各要素から`k`を引く | `{"map":["sub_k"]}` |
| `atomic-000013` | 各要素に`k`を掛ける | `{"map":["mul_k"]}` |
| `atomic-000014` | 各要素を2倍する | `{"map":["mul_const",2]}` |
| `atomic-000015` | 各要素を3倍する | `{"map":["mul_const",3]}` |
| `atomic-000016` | 各要素の符号を反転する | `{"map":["negate"]}` |
| `atomic-000017` | 各要素の絶対値を取る | `{"map":["abs"]}` |
| `atomic-000018` | 各要素を二乗する | `{"map":["square"]}` |

`mul_const`は定数倍を表す。その直後の数値が倍率であり、`["mul_const", 2]`は2倍、`["mul_const", 3]`は3倍を意味する。

## 並べ替え

リスト内の要素の順番を変更する操作である。

| ID | 意味 | semantic_ast |
|---|---|---|
| `atomic-000019` | 値を昇順に並べる | `{"order":"ascending"}` |
| `atomic-000020` | 値を降順に並べる | `{"order":"descending"}` |
| `atomic-000021` | 現在の要素順を反転する | `{"order":"reverse"}` |

`ascending`と`descending`は値の大小に基づいて並べ替える。`reverse`は値の大小とは関係なく、入力時点の並びを後ろから前へ反転する。

## 切り出し

リストから指定された位置の要素を取り出す操作である。

| ID | 意味 | semantic_ast |
|---|---|---|
| `atomic-000022` | 先頭から`k`個を取る | `{"slice":["take_first_k"]}` |
| `atomic-000023` | 末尾から`k`個を取る | `{"slice":["take_last_k"]}` |
| `atomic-000024` | 先頭から1個おきに取る | `{"slice":["every_other"]}` |

`every_other`は、先頭の要素を位置0としたとき、位置0、2、4、6、……の要素を取得することを意味する。

## 1〜3個の操作を組み合わせた意味AST

24個の単独操作から、1〜3個の操作を組み合わせた意味ASTを作成した。操作の順序は区別し、同じ単独操作は1つの意味AST内で重複して使用しない。

生成件数は次のとおりである。

| 操作数 | 計算 | 件数 |
|---|---:|---:|
| 1個 | `24` | 24 |
| 2個 | `24 × 23` | 552 |
| 3個 | `24 × 23 × 22` | 12,144 |
| 合計 |  | **12,720** |

順序を区別するため、次の二つは異なる意味ASTとして扱う。

```json
{"sequence":[{"filter":["even"]},{"map":["add_k"]}]}
```

```json
{"sequence":[{"map":["add_k"]},{"filter":["even"]}]}
```

組み合わせた意味ASTは、処理順を保持するために `sequence` 配列へ操作を順番に格納する。

```json
{
  "spec_id": "combined-000025",
  "semantic_ast": {
    "sequence": [
      {"filter": ["even"]},
      {"filter": ["odd"]}
    ]
  }
}
```

矛盾する組み合わせや冗長な組み合わせも、この段階では除外せずに含めている。

生成結果は `data/semantic_asts/combined_semantic_asts.jsonl` に、1つの意味ASTにつき1レコードで保存している。生成プログラムは `scripts/semantic_asts/generate_combined_semantic_asts.py` である。

プロジェクトのルートで次を実行すると、同じ組み合わせを再生成できる。

```bash
python3 scripts/semantic_asts/generate_combined_semantic_asts.py
```
