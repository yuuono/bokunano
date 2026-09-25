# 反復汎化テストの方針

## 目的

同一操作が隣接する意味ASTを、独立したテスト集合として評価する。

このテスト集合では、訓練で単独には学習した操作を、同じ操作が連続する形でも適用できるかを確認する。異なる操作同士の未知の組み合わせを評価する組合せ汎化テストとは目的が異なるため、別の`test_suite`として管理する。

```json
{
  "test_suite": "repetition"
}
```

この生成ファイルでは、`test_suite: "repetition"`自体がテスト用であることを表すため、`split: "test"`は重複して保存しない。

## 対象とする意味AST

24個の単独操作を`A`、`B`として表す。同一操作が隣接する、次の形式だけを対象とする。

### 2操作

```text
A → A
```

`A`は24種類あるため、対象は24件である。

```text
24件
```

### 3操作

異なる操作`A`と`B`を使う場合は、同じ操作`A`が隣接する次の2形式を対象とする。

```text
A → A → B
B → A → A
```

繰り返す操作`A`は24種類、異なる操作`B`は残り23種類、配置は2通りなので1,104件になる。

```text
24 × 23 × 2 = 1,104件
```

同じ操作を3回繰り返す形式も対象とする。

```text
A → A → A
```

これは24件である。したがって、3操作の対象は合計1,128件になる。

```text
1,104 + 24 = 1,128件
```

## 合計件数

| 操作数 | 対象形式 | 件数 |
|---|---|---:|
| 2個 | `A → A` | 24 |
| 3個 | `A → A → B`、`B → A → A`、`A → A → A` | 1,128 |
| 合計 |  | **1,152** |

## 対象外

同じ操作が2回含まれていても、隣接していない次の形式は、このテスト集合には含めない。

```text
A → B → A
```

この形式は24種類の`A`と、`A`以外の23種類の`B`から552件作れるが、`repetition`の対象外とする。

```text
24 × 23 = 552件
```

## 他のデータ集合との関係

`repetition`に属する1,152件は、訓練・検証・通常テスト・言い換えテスト・組合せ汎化テストには入れない。

既存の12,720件は、同じ単独操作を1つの意味AST内で繰り返さない。そのため、今回対象とする1,152件は既存の12,720件には含まれない。1,152件は独立したテストデータとして`data/semantic_asts/repetition_semantic_asts.jsonl`に保存する。

矛盾・冗長な意味ASTも除外しない。例えば、偶数だけを残す抽出の反復や、現在順を反転する並べ替えの反復も、このテスト集合へ含める。

## 意味ASTの生成

`scripts/semantic_asts/generate_repetition_semantic_asts.py`が、`data/semantic_asts/atomic_semantic_asts.jsonl`の24操作から方針どおりに1,152件を生成する。

```text
入力: data/semantic_asts/atomic_semantic_asts.jsonl
出力: data/semantic_asts/repetition_semantic_asts.jsonl
```

各レコードは次の形式とする。

```json
{
  "spec_id": "repetition-000001",
  "semantic_ast": {
    "sequence": [
      {"filter": ["even"]},
      {"filter": ["even"]}
    ]
  },
  "test_suite": "repetition"
}
```

`spec_id`は`repetition-000001`から`repetition-001152`までの連番とする。生成コードは、合計件数、形式別件数、`spec_id`、意味ASTの重複、対象外形式の混入を保存前に検証する。

## Pythonコード候補の生成結果

2026年9月20日に、2操作24件と3操作1,128件の各意味ASTから、検証済み固有コードを20件ずつ生成した。合計は23,040件であり、すべて参照インタプリタと一致した。詳細は[検証・通常テスト・反復汎化のPythonコード候補生成結果](../results/evaluation_python_code_generation_results.md)に記録する。

現在も未実施なのは次の処理である。

- 最終テストレコードの作成

日本語指示は2026年9月24日に、訓練用表現辞書だけを使って各意味AST最大20件生成した。反復汎化では日本語表現を新しい評価軸にせず、同じ操作を隣接して適用する意味構造だけを評価する。生成件数は2操作480件、3操作22,560件、合計23,040件である。実行入力はrepetition専用hidden集合64件を使用する。詳細は[`rule_generated_instruction_results.md`](../results/rule_generated_instruction_results.md)と[評価入力の生成・分離方針](evaluation_input_policy.md)に記録する。
