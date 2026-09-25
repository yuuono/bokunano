# 教師言い換え置換反映済み訓練指示の作成結果

## 1. 実行方針

2026年9月25日に、承認済み教師言い換えをルール生成訓練指示へ一対一で置換反映した。

元のルール生成指示JSONLと承認済み教師言い換えJSONLは変更しない。読み取り専用入力として使用し、第三の置換反映済みJSONLを作成する。教師言い換えは追加しないため、置換後の総数と意味ASTごとの件数は元の訓練指示から変えない。

## 2. 実行方法

```bash
uv run --python 3.12.12 python \
  scripts/instruction_generation/build_replacement_resolved_train_instructions.py \
  --rule-instructions data/instructions/rule_generated_instructions.jsonl \
  --approved-paraphrases data/instructions/approved_teacher_paraphrases.jsonl \
  --paraphrase-generation-stats data/instructions/teacher_paraphrase_generation_stats.json \
  --output-jsonl data/instructions/replacement_resolved_train_instructions.jsonl \
  --archive data/archives/replacement_resolved_train_instructions_2026-09-25.zip \
  --stats data/instructions/replacement_resolved_train_instruction_stats.json \
  --expected-output-count 192900 \
  --expected-replacement-count 96390
```

## 3. 置換結果

| 区分 | 件数 |
|---|---:|
| 置換前の訓練用ルール生成指示 | 192,900 |
| 教師言い換えへ置換 | 96,390 |
| ルール生成指示を維持 | 96,510 |
| 置換後の訓練指示 | 192,900 |

ルール生成指示を維持した96,510件の内訳は次のとおりである。

| 維持理由 | 件数 | `retention_reason` |
|---|---:|---|
| 教師生成対象に選ばれなかった | 96,440 | `not_selected_for_teacher_paraphrase` |
| 元文と異なる教師候補を取得できなかった | 70 | `teacher_paraphrase_unavailable` |

操作数別件数は、1操作460件、2操作8,680件、3操作183,760件で、置換前から変化していない。意味AST数は9,646件で、意味AST当たり指示数の分布も11件が1 AST、16件が1 AST、17件が1 AST、18件が1 AST、19件が2 AST、20件が9,640 ASTのままである。

## 4. 元データと来歴の保持

置換成功レコードでは、元のルール生成レコードへ承認済み教師レコードの全項目を重ね、次を同時に保存した。

- 教師指示IDと教師言い換え本文
- `source_instruction_id`、`source_instruction_ja`、`source_text_hash`
- `spec_id`と意味AST
- 元の表現ID、文テンプレートID、辞書版、ルール生成seed・version
- 教師モデル、revision、prompt hash、sampling、生成日時
- 承認者、承認日時、承認方式
- `replacement_status=teacher_replaced`
- `replacement_mode=replace_source_instruction_one_to_one`

元文維持レコードでは、元の指示IDと本文を変更せず、`replacement_status=rule_retained`と維持理由を追加した。

入力ファイルが変更されていないことを、処理前後のSHA-256で確認した。

| 入力 | 処理前SHA-256 | 処理後SHA-256 | 結果 |
|---|---|---|---|
| `rule_generated_instructions.jsonl` | `419f26ed8797296975c801fab0adb2a944dcedd584470ed756f1c0bf1055a0a8` | `419f26ed8797296975c801fab0adb2a944dcedd584470ed756f1c0bf1055a0a8` | 一致 |
| `approved_teacher_paraphrases.jsonl` | `b20b136627504d52168e977cd52ce2ebf3d55fb7406d36754ad678305313e4e1` | `b20b136627504d52168e977cd52ce2ebf3d55fb7406d36754ad678305313e4e1` | 一致 |
| `teacher_paraphrase_generation_stats.json` | `6ea43dbeb2fb0fcd339348012e2acdc5b3ac76c7d9c34528f7c409f6b88d167a` | `6ea43dbeb2fb0fcd339348012e2acdc5b3ac76c7d9c34528f7c409f6b88d167a` | 一致 |

## 5. 成果物

| 成果物 | 件数またはサイズ | SHA-256 | Git管理 |
|---|---:|---|---|
| `data/instructions/replacement_resolved_train_instructions.jsonl` | 192,900件、346,826,926 bytes | `a33ec7d4cf9a7e14581113dbbf85266ce8c55796db9e947ebf2f9f7959cef73b` | 対象外 |
| `data/archives/replacement_resolved_train_instructions_2026-09-25.zip` | 55,133,135 bytes | `7a90b24796e7ef2ad9d9510168e734df7556b18faa092a00f81466f96a9818c2` | 対象 |
| `data/instructions/replacement_resolved_train_instruction_stats.json` | 2,404 bytes | `cefc780ca605913dc26aaa5e945258b6a722e898effb863ec0d5a61774aa2c93` | 対象 |

ZIPには`replacement_resolved_train_instructions.jsonl`だけを格納する。ZIP内JSONLとローカルJSONLの内容は同一である。

## 6. 検証結果

- 出力指示ID重複: 0件
- 置換元指示ID重複: 0件
- 未使用の承認済み教師候補: 0件
- 未確認の教師生成失敗ID: 0件
- `dictionary=train`以外: 0件
- `split=train`かつ`test_suite=null`以外: 0件
- 置換前後の`spec_id`別件数差: 0件
- 本文と`text_hash`の不一致: 0件
- 元データの変更: 0件

## 7. 次工程

置換反映済み192,900指示を、同じ`spec_id`と正規化意味ASTを持つ検証済み訓練コードへ決定的に一対一対応させる。指示数が20件未満の単一操作6意味ASTでは、余るコード20件を不採用記録へ残す。最終訓練レコードには、指示来歴、コード来歴、両者のハッシュ、`record_id`、`family_id`を保存する。
