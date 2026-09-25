# 訓練用日本語指示とコードの結合前分布

基準日: 2026-09-25。対象は`split=train`の意味ASTだけである。

## 1. 192,900件になる理由

訓練用意味ASTは9,646件ある。2操作・3操作では各意味ASTにつき20件、単一操作では固有全文だけを最大20件作成した。内訳は次のとおりである。

```text
単一操作:       24 AST →     460指示
2操作:         434 AST × 20 =   8,680指示
3操作:       9,188 AST × 20 = 183,760指示
合計:        9,646 AST       = 192,900指示
```

## 2. 教師言い換えは追加ではなく置換

教師生成では96,460件の元指示を選び、96,390件で元文と異なる承認済み言い換えを得た。これらは`source_instruction_id`が指す元指示と一対一で置換する。

言い換えを得られなかった70件は元のルール生成指示を維持する。このため置換後の指示総数は192,900件のままであり、教師言い換えを加算した件数にはしない。

| 置換後の指示種別 | 件数 |
|---|---:|
| 教師言い換えへ置換 | 96,390 |
| ルール生成指示のまま維持 | 96,510 |
| 置換後合計 | 192,900 |

## 3. 操作数別の結合前分布

| 操作数 | 意味AST | 置換前指示 | 教師置換 | 元文維持 | 置換後指示 | コード | 指示−コード |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1操作 | 24 | 460 | 239 | 221 | 460 | 480 | -20 |
| 2操作 | 434 | 8,680 | 4,339 | 4,341 | 8,680 | 8,680 | 0 |
| 3操作 | 9,188 | 183,760 | 91,812 | 91,948 | 183,760 | 183,760 | 0 |

## 4. 1意味AST当たりの置換後指示数

| 置換後指示数 | 意味AST数 |
|---:|---:|
| 11 | 1 |
| 16 | 1 |
| 17 | 1 |
| 18 | 1 |
| 19 | 2 |
| 20 | 9,640 |

このうち20件未満の6意味ASTは次節にすべて示す。20件の9,640意味ASTを含む全件の対応は`data/instructions/pre_join_distribution_by_ast.jsonl`に保存する。

## 5. 20件未満の意味AST

20件未満なのは単一操作の6意味ASTだけである。終止形が同じ全文を別IDとして水増ししなかった結果であり、教師置換後も件数は増減しない。

| spec_id | 操作 | 置換後指示 | 教師置換 | 元文維持 | コード | 不足 |
|---|---|---:|---:|---:|---:|---:|
| `combined-000007` | `{"filter":["multiple_of_k"]}` | 16 | 10 | 6 | 20 | 4 |
| `combined-000008` | `{"filter":["positive"]}` | 19 | 10 | 9 | 20 | 1 |
| `combined-000009` | `{"filter":["negative"]}` | 18 | 10 | 8 | 20 | 2 |
| `combined-000010` | `{"filter":["zero"]}` | 11 | 10 | 1 | 20 | 9 |
| `combined-000016` | `{"map":["negate"]}` | 19 | 10 | 9 | 20 | 1 |
| `combined-000019` | `{"order":"ascending"}` | 17 | 10 | 7 | 20 | 3 |

## 6. 20件未満だった単一操作が全訓練指示に含まれる量

対象は置換後の訓練用192,900指示である。「含有指示」は対象操作を1回以上含む意味ASTに属する指示文を一文として数える。「操作出現」は同じ意味AST内に対象操作が複数回ある場合、その回数も数える。

| 単一操作spec_id | 操作 | 単一操作だけの指示 | 含有意味AST | 含有指示 | 教師置換 | 元文維持 | 操作出現 | 全訓練指示に占める含有率 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `combined-000007` | `{"filter":["multiple_of_k"]}` | 16 | 1,204 | 24,076 | 12,034 | 12,042 | 24,076 | 12.48% |
| `combined-000008` | `{"filter":["positive"]}` | 19 | 1,248 | 24,959 | 12,461 | 12,498 | 24,959 | 12.94% |
| `combined-000009` | `{"filter":["negative"]}` | 18 | 1,215 | 24,298 | 12,138 | 12,160 | 24,298 | 12.60% |
| `combined-000010` | `{"filter":["zero"]}` | 11 | 1,219 | 24,371 | 12,186 | 12,185 | 24,371 | 12.63% |
| `combined-000016` | `{"map":["negate"]}` | 19 | 1,211 | 24,219 | 12,110 | 12,109 | 24,219 | 12.56% |
| `combined-000019` | `{"order":"ascending"}` | 17 | 1,219 | 24,377 | 12,190 | 12,187 | 24,377 | 12.64% |

### 1・2・3操作別の内訳

| 操作 | 意味ASTの操作数 | 含有意味AST | 含有指示 | 教師置換 | 元文維持 | 操作出現 |
|---|---:|---:|---:|---:|---:|---:|
| `{"filter":["multiple_of_k"]}` | 1 | 1 | 16 | 10 | 6 | 16 |
| `{"filter":["multiple_of_k"]}` | 2 | 40 | 800 | 400 | 400 | 800 |
| `{"filter":["multiple_of_k"]}` | 3 | 1,163 | 23,260 | 11,624 | 11,636 | 23,260 |
| `{"filter":["positive"]}` | 1 | 1 | 19 | 10 | 9 | 19 |
| `{"filter":["positive"]}` | 2 | 37 | 740 | 370 | 370 | 740 |
| `{"filter":["positive"]}` | 3 | 1,210 | 24,200 | 12,081 | 12,119 | 24,200 |
| `{"filter":["negative"]}` | 1 | 1 | 18 | 10 | 8 | 18 |
| `{"filter":["negative"]}` | 2 | 38 | 760 | 380 | 380 | 760 |
| `{"filter":["negative"]}` | 3 | 1,176 | 23,520 | 11,748 | 11,772 | 23,520 |
| `{"filter":["zero"]}` | 1 | 1 | 11 | 10 | 1 | 11 |
| `{"filter":["zero"]}` | 2 | 36 | 720 | 360 | 360 | 720 |
| `{"filter":["zero"]}` | 3 | 1,182 | 23,640 | 11,816 | 11,824 | 23,640 |
| `{"map":["negate"]}` | 1 | 1 | 19 | 10 | 9 | 19 |
| `{"map":["negate"]}` | 2 | 34 | 680 | 340 | 340 | 680 |
| `{"map":["negate"]}` | 3 | 1,176 | 23,520 | 11,760 | 11,760 | 23,520 |
| `{"order":"ascending"}` | 1 | 1 | 17 | 10 | 7 | 17 |
| `{"order":"ascending"}` | 2 | 38 | 760 | 380 | 380 | 760 |
| `{"order":"ascending"}` | 3 | 1,180 | 23,600 | 11,800 | 11,800 | 23,600 |

## 7. 1意味AST当たりの教師置換成功数

各意味ASTから10件を教師言い換え対象に選んだ。元文と同一になった70件は置換せず、元文を維持するため、成功置換数には意味ASTごとの差がある。

| 教師置換成功数 | 意味AST数 |
|---:|---:|
| 7 | 2 |
| 8 | 6 |
| 9 | 52 |
| 10 | 9,586 |

### 教師置換成功が10件未満の意味AST

成功数7〜9件の60意味ASTを次にすべて示す。成功数10件の9,586意味ASTを含む全件の対応は`data/instructions/pre_join_distribution_by_ast.jsonl`で確認できる。

| spec_id | semantic_ast | 操作数 | 選抜 | 置換成功 | 失敗・元文維持 | 置換後指示 |
|---|---|---:|---:|---:|---:|---:|
| `combined-003199` | `{"sequence":[{"filter":["le_k"]},{"filter":["lt_k"]},{"filter":["multiple_of_k"]}]}` | 3 | 10 | 7 | 3 | 20 |
| `combined-003200` | `{"sequence":[{"filter":["le_k"]},{"filter":["lt_k"]},{"filter":["positive"]}]}` | 3 | 10 | 7 | 3 | 20 |
| `combined-001152` | `{"sequence":[{"filter":["odd"]},{"filter":["lt_k"]},{"filter":["le_k"]}]}` | 3 | 10 | 8 | 2 | 20 |
| `combined-001154` | `{"sequence":[{"filter":["odd"]},{"filter":["lt_k"]},{"filter":["positive"]}]}` | 3 | 10 | 8 | 2 | 20 |
| `combined-003134` | `{"sequence":[{"filter":["le_k"]},{"filter":["odd"]},{"filter":["positive"]}]}` | 3 | 10 | 8 | 2 | 20 |
| `combined-003153` | `{"sequence":[{"filter":["le_k"]},{"filter":["gt_k"]},{"filter":["ge_k"]}]}` | 3 | 10 | 8 | 2 | 20 |
| `combined-003207` | `{"sequence":[{"filter":["le_k"]},{"filter":["lt_k"]},{"map":["mul_const",3]}]}` | 3 | 10 | 8 | 2 | 20 |
| `combined-004713` | `{"sequence":[{"filter":["negative"]},{"filter":["lt_k"]},{"filter":["even"]}]}` | 3 | 10 | 8 | 2 | 20 |
| `combined-000006` | `{"sequence":[{"filter":["le_k"]}]}` | 1 | 10 | 9 | 1 | 20 |
| `combined-000120` | `{"sequence":[{"filter":["lt_k"]},{"filter":["ge_k"]}]}` | 2 | 10 | 9 | 1 | 20 |
| `combined-000605` | `{"sequence":[{"filter":["even"]},{"filter":["gt_k"]},{"filter":["negative"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-000626` | `{"sequence":[{"filter":["even"]},{"filter":["ge_k"]},{"filter":["positive"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-000651` | `{"sequence":[{"filter":["even"]},{"filter":["lt_k"]},{"map":["add_k"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-000662` | `{"sequence":[{"filter":["even"]},{"filter":["lt_k"]},{"slice":["take_first_k"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-000668` | `{"sequence":[{"filter":["even"]},{"filter":["le_k"]},{"filter":["lt_k"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-000938` | `{"sequence":[{"filter":["even"]},{"map":["square"]},{"map":["add_k"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-001136` | `{"sequence":[{"filter":["odd"]},{"filter":["ge_k"]},{"map":["sub_k"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-001155` | `{"sequence":[{"filter":["odd"]},{"filter":["lt_k"]},{"filter":["negative"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-001169` | `{"sequence":[{"filter":["odd"]},{"filter":["lt_k"]},{"slice":["take_last_k"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-001177` | `{"sequence":[{"filter":["odd"]},{"filter":["le_k"]},{"filter":["negative"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-001218` | `{"sequence":[{"filter":["odd"]},{"filter":["positive"]},{"filter":["lt_k"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-001234` | `{"sequence":[{"filter":["odd"]},{"filter":["positive"]},{"slice":["take_first_k"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-002163` | `{"sequence":[{"filter":["ge_k"]},{"filter":["lt_k"]},{"filter":["gt_k"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-002169` | `{"sequence":[{"filter":["ge_k"]},{"filter":["lt_k"]},{"map":["add_k"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-002179` | `{"sequence":[{"filter":["ge_k"]},{"filter":["lt_k"]},{"order":"reverse"}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-002616` | `{"sequence":[{"filter":["lt_k"]},{"filter":["even"]},{"map":["square"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-002755` | `{"sequence":[{"filter":["lt_k"]},{"filter":["negative"]},{"filter":["even"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-003044` | `{"sequence":[{"filter":["lt_k"]},{"slice":["take_first_k"]},{"filter":["ge_k"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-003082` | `{"sequence":[{"filter":["lt_k"]},{"slice":["take_last_k"]},{"order":"reverse"}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-003108` | `{"sequence":[{"filter":["le_k"]},{"filter":["even"]},{"filter":["gt_k"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-003112` | `{"sequence":[{"filter":["le_k"]},{"filter":["even"]},{"filter":["positive"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-003195` | `{"sequence":[{"filter":["le_k"]},{"filter":["lt_k"]},{"filter":["even"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-003209` | `{"sequence":[{"filter":["le_k"]},{"filter":["lt_k"]},{"map":["abs"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-003210` | `{"sequence":[{"filter":["le_k"]},{"filter":["lt_k"]},{"map":["square"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-003239` | `{"sequence":[{"filter":["le_k"]},{"filter":["positive"]},{"filter":["even"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-003250` | `{"sequence":[{"filter":["le_k"]},{"filter":["positive"]},{"map":["mul_const",2]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-003261` | `{"sequence":[{"filter":["le_k"]},{"filter":["negative"]},{"filter":["even"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-003280` | `{"sequence":[{"filter":["le_k"]},{"filter":["negative"]},{"slice":["take_first_k"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-003407` | `{"sequence":[{"filter":["le_k"]},{"map":["mul_const",3]},{"map":["abs"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-003472` | `{"sequence":[{"filter":["le_k"]},{"map":["square"]},{"map":["mul_const",3]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-003551` | `{"sequence":[{"filter":["le_k"]},{"slice":["take_first_k"]},{"filter":["lt_k"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-003682` | `{"sequence":[{"filter":["multiple_of_k"]},{"filter":["ge_k"]},{"filter":["lt_k"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-004300` | `{"sequence":[{"filter":["positive"]},{"filter":["zero"]},{"filter":["le_k"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-004415` | `{"sequence":[{"filter":["positive"]},{"map":["mul_const",3]},{"map":["sub_k"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-004697` | `{"sequence":[{"filter":["negative"]},{"filter":["ge_k"]},{"filter":["positive"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-004719` | `{"sequence":[{"filter":["negative"]},{"filter":["lt_k"]},{"filter":["positive"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-004803` | `{"sequence":[{"filter":["negative"]},{"filter":["zero"]},{"filter":["gt_k"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-005226` | `{"sequence":[{"filter":["zero"]},{"filter":["lt_k"]},{"filter":["negative"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-005246` | `{"sequence":[{"filter":["zero"]},{"filter":["le_k"]},{"filter":["multiple_of_k"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-006718` | `{"sequence":[{"map":["mul_k"]},{"filter":["ge_k"]},{"filter":["lt_k"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-006928` | `{"sequence":[{"map":["mul_k"]},{"map":["mul_const",2]},{"map":["square"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-007013` | `{"sequence":[{"map":["mul_k"]},{"map":["square"]},{"map":["mul_const",2]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-010307` | `{"sequence":[{"order":"descending"},{"filter":["le_k"]},{"filter":["positive"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-010545` | `{"sequence":[{"order":"descending"},{"map":["abs"]},{"filter":["gt_k"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-010555` | `{"sequence":[{"order":"descending"},{"map":["abs"]},{"map":["mul_k"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-010788` | `{"sequence":[{"order":"reverse"},{"filter":["lt_k"]},{"filter":["ge_k"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-010803` | `{"sequence":[{"order":"reverse"},{"filter":["lt_k"]},{"order":"descending"}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-010811` | `{"sequence":[{"order":"reverse"},{"filter":["le_k"]},{"filter":["lt_k"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-010850` | `{"sequence":[{"order":"reverse"},{"filter":["multiple_of_k"]},{"slice":["every_other"]}]}` | 3 | 10 | 9 | 1 | 20 |
| `combined-010854` | `{"sequence":[{"order":"reverse"},{"filter":["positive"]},{"filter":["ge_k"]}]}` | 3 | 10 | 9 | 1 | 20 |

## 8. 結合方針への結論

検証済み訓練コードは192,920件で、全9,646意味ASTに20件ずつある。置換後指示は192,900件なので、指示が20件少ない。差はすべて単一操作6意味ASTにある。

最終結合では全直積を作らない。同じ`spec_id`かつ同じ意味ASTの内部で、置換後指示とコードを決定的に一対一対応させる。20件の余剰コードは、追加の固有日本語指示を作らない限り最終訓練レコードへ採用しない。
