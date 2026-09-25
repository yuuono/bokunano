# 教師言い換え一括承認結果

## 1. 承認方法

2026年9月24日、利用者の明示指示により、候補JSONLに含まれる96,390件を全件承認した。

今回の承認は、各候補を元文と一件ずつ比較した人手承認ではない。監査上区別できるよう、各レコードに次の情報を追加した。

- `candidate_review_status=pending`：候補時点の状態
- `review_status=approved`：今回の承認後の状態
- `approved_by=ono_yusuke`：承認者
- `approved_at=2026-09-24T20:51:52+09:00`：承認日時
- `approval_mode=blanket_all_candidates`：全候補一括承認であることを示す区分

教師生成96,460件のうち、元文と同一だった70件は候補作成時に除外済みであり、今回の承認対象には含まれない。

## 2. 実行方法

```bash
uv run --python 3.12.12 python \
  scripts/instruction_generation/prepare_approved_teacher_paraphrases.py \
  --candidate-jsonl data/instructions/teacher_paraphrase_candidates.jsonl \
  --output-jsonl data/instructions/approved_teacher_paraphrases.jsonl \
  --archive data/archives/approved_teacher_paraphrases_2026-09-24.zip \
  --stats data/instructions/approved_teacher_paraphrases_stats.json \
  --reviewer ono_yusuke \
  --approved-at 2026-09-24T20:51:52+09:00 \
  --expected-count 96390 \
  --approve-all
```

`--approve-all`は誤操作防止の必須フラグである。既存成果物を意図的に置き換える場合だけ`--overwrite`も指定する。

## 3. 検証結果

| 検査項目 | 結果 |
|---|---:|
| 入力候補 | 96,390件 |
| 承認済み出力 | 96,390件 |
| 非承認 | 0件 |
| 候補ID重複 | 0件 |
| 元指示ID重複 | 0件 |
| `dictionary=train`以外 | 0件 |
| 候補から失われた項目 | 0件 |

全レコードについて候補JSONLの全項目を保持し、承認情報だけを追加した。承認済みJSONLとZIP内のJSONLのSHA-256も一致することを確認した。

## 4. 成果物

| 成果物 | 件数またはサイズ | SHA-256 | Git管理 |
|---|---:|---|---|
| `data/instructions/approved_teacher_paraphrases.jsonl` | 96,390件、156,908,862 bytes | `b20b136627504d52168e977cd52ce2ebf3d55fb7406d36754ad678305313e4e1` | 対象外 |
| `data/archives/approved_teacher_paraphrases_2026-09-24.zip` | 19,866,131 bytes | `1f5d0b5fb68478414b51798374d84cd10943bdfef605895c4140695b1d955d49` | 対象 |
| `data/instructions/approved_teacher_paraphrases_stats.json` | 785 bytes | `8921d23aedfdd84e9cc257d1b1f6d1d798f6b52c0b61487bb308cc2e1af4ddfa` | 対象 |

ZIPには`approved_teacher_paraphrases.jsonl`だけを格納している。ZIP内JSONLの非圧縮時SHA-256はローカルの承認済みJSONLと同一である。

## 5. 次工程

承認済み言い換え96,390件は追加せず、`source_instruction_id`が指すルール生成指示と一対一で置き換える。言い換えを取得できなかった70件は元文を維持するため、置換後の訓練用指示総数は192,900件から変わらない。置換後の分布とコードとの差は[`pre_join_distribution_report.md`](pre_join_distribution_report.md)に記録した。
