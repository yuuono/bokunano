# 評価入力6集合の生成結果

## 実行日

2026年9月25日

## 目的

最終評価レコードから参照するvalidation・hidden・boundary入力を確定し、訓練コード候補の検証に使用した41入力から分離して生成した。normal、compositional、paraphrase、repetitionには互いに異なるhidden入力を割り当て、boundaryには共通境界ケースと抽出AST固有ケースを作った。

## 実行コマンド

```bash
UV_CACHE_DIR=/tmp/bokunano-uv-cache \
uv run --python 3.12.12 python \
  scripts/validation/generate_evaluation_input_sets.py \
  --config config/evaluation_input_generation.json
```

再現性確認では同じコマンドへ`--overwrite`を追加して再生成した。

## 生成結果

| 集合 | 意味AST数 | 入力数 | 参照実行数 | `input_set` | seed |
|---|---:|---:|---:|---|---:|
| validation | 1,202 | 64 | 76,928 | `build` | 2026092601 |
| normal | 1,202 | 64 | 76,928 | `hidden` | 2026092602 |
| compositional | 670 | 64 | 42,880 | `hidden` | 2026092603 |
| paraphrase | 24 | 64 | 1,536 | `hidden` | 2026092604 |
| repetition | 1,152 | 64 | 73,728 | `hidden` | 2026092605 |
| boundary共通 | 1,202 | 30 | 36,060 | `boundary` | 固定ケース |
| boundary抽出AST固有 | 964 | 各1 | 964 | `boundary` | SHA-256順位探索 |
| 合計 |  |  | **309,024** |  |  |

5個のランダム集合は各64件、合計320件である。訓練コード検証に使った41件との完全一致は0件、5集合相互の完全一致も0件だった。

ランダム集合は、0と符号混在、`k`との等値・近傍、倍数と非倍数、重複、値域両端、偶奇、昇順、降順の8層を各8件含む。

## boundary

normalの1,202意味ASTすべてへ共通境界30件を実行した。空リスト、1要素、長さ20、`k=1`・`k=10`、長さと`k`の前後、全要素同値、正数のみ、負数のみ、値域両端、昇順・降順・回文・重複・倍数・非倍数を含む。

normal 1,202 ASTのうちfilterを含むものは976 ASTだった。

| 区分 | AST数 |
|---|---:|
| 最初のfilterで全要素不合格となる固有ケースを生成 | 964 |
| 全有効singletonを探索しても全不合格へ到達不能 | 12 |
| filter含有AST合計 | 976 |

964件では、最初のfilter直前が非空で、そのfilter適用直後とAST全体の最終出力が空になることを確認した。

### 全要素不合格へ到達不能な12 AST

| `spec_id` | 操作列 | 理由 |
|---|---|---|
| `combined-009513` | square → negate → `lt_k` | filter直前が常に0以下で`k`未満 |
| `combined-009514` | square → negate → `le_k` | filter直前が常に0以下で`k`以下 |
| `combined-006799` | mul_k → `multiple_of_k` → reverse | `k`倍後は必ず`k`の倍数 |
| `combined-006781` | mul_k → `multiple_of_k` → even | `k`倍後は必ず`k`の倍数 |
| `combined-006783` | mul_k → `multiple_of_k` → `gt_k` | `k`倍後は必ず`k`の倍数 |
| `combined-007007` | mul_k → square → `multiple_of_k` | `k`倍して二乗した値は必ず`k`の倍数 |
| `combined-009955` | ascending → mul_k → `multiple_of_k` | `k`倍後は必ず`k`の倍数 |
| `combined-006784` | mul_k → `multiple_of_k` → `ge_k` | `k`倍後は必ず`k`の倍数 |
| `combined-006796` | mul_k → `multiple_of_k` → square | `k`倍後は必ず`k`の倍数 |
| `combined-008900` | abs → add_k → positive | filter直前が常に`k`以上の正数 |
| `combined-008896` | abs → add_k → `ge_k` | filter直前が常に`k`以上 |
| `combined-007175` | mul_const 2 → even → take_last_k | 2倍後は必ず偶数 |

これらは不正な入力を作らず、`xs`の全singleton整数-100〜100と`k=1〜10`の2,010組を探索した条件と理由を`boundary_inputs.json`の`unreachable_filter_asts`へ保存した。

## 検証

- 全入力が`xs`長0〜20、値-100〜100、`k=1〜10`を満たした。
- 309,024回すべての参照実行が例外なく完了した。
- 全参照出力が整数リストだった。
- 全実行で入力`xs`が変更されなかった。
- ランダム評価入力320件と訓練コード検証入力41件の完全一致は0件だった。
- ランダム評価5集合間の完全一致は0件だった。
- filter含有976 ASTが、固有ケース964件または到達不能記録12件のどちらかへ漏れなく分類された。
- 設定、既存build入力、5種類の意味AST入力は処理前後のSHA-256が一致した。
- `ruff check`が成功し、全48単体テストが成功した。
- `--overwrite`による再生成後も6 manifestのSHA-256が一致した。

## 成果物

| ファイル | サイズ | SHA-256 |
|---|---:|---|
| `data/evaluation_inputs/validation_inputs.json` | 18,970 bytes | `a515fd4c96f7fbc4558699b08ccdcff4524d5bfa854f7cb7f10cb61ef387c623` |
| `data/evaluation_inputs/normal_hidden_inputs.json` | 18,279 bytes | `303b4d412910bb663a0faa2320ef2bec4f28cbeb6a464d370ddd5370fc6cda73` |
| `data/evaluation_inputs/compositional_hidden_inputs.json` | 18,584 bytes | `b208f78d8d99011a5ce158e9ee4275fb763a2a68db28ec5f3eaef9cc0af9a951` |
| `data/evaluation_inputs/paraphrase_hidden_inputs.json` | 18,129 bytes | `2880b2b834bc157261543b66c4f334acfeb8a3e96ca4aadbce40b265c1943c83` |
| `data/evaluation_inputs/repetition_hidden_inputs.json` | 18,519 bytes | `60510519431c68cbafa4ec591293e865a335db4dad7fc271f4a2cafb5d77ab33` |
| `data/evaluation_inputs/boundary_inputs.json` | 425,196 bytes | `8def08f589f58b03cf87c9eaea9d7fdcfec71d90d0de9508058a93bb89fa9a39` |
| `data/evaluation_inputs/evaluation_input_stats.json` | 8,793 bytes | `0c3be92ff2096dc8f1607861ad4769ea9f0f2ae115eb08a6b01baaf23c5cdd01` |

## 次工程

次は、評価用日本語指示と検証済みコードを同じ`spec_id`・正規化意味ASTで結合し、本成果物の`test_set_id`を最終評価レコードの`tests`へ設定する。boundaryはnormalの指示・コード・`family_id`を再利用し、`test_suite`と`input_set`とテスト参照だけを変更する。
