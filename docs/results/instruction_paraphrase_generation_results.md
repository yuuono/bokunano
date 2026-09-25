# 教師モデルによる全文言い換え生成結果

## 1. 実行概要

2026年9月24日に、ルール生成済み日本語指示の一部をQwen3で全文言い換えした。対象は`split=train`かつ`dictionary=train`だけであり、言い換えテスト用の`test_only`表現および評価用指示は含めていない。

```bash
uv run --group instruction-generation --python 3.12.12 python \
  scripts/instruction_generation/generate_instruction_paraphrase_candidates.py \
  --config config/qwen_instruction_paraphrase_generation.json \
  --overwrite
```

選抜元はルール生成指示277,420件である。固定seed、`spec_id`、`instruction_id`から得たSHA-256順位を使い、訓練用9,646意味ASTの各ASTから10件ずつ選んだ。

```text
9,646意味AST × 10元文 = 96,460元文
```

検証の結果、全9,646意味ASTの選抜数は例外なく10件であり、選抜した96,460 IDの順番と生応答96,460件の元指示IDの順番は完全一致した。

## 2. 生成条件

| 項目 | 値 |
|---|---:|
| model | `Qwen/Qwen3-4B-AWQ` |
| requested / resolved revision | `74d4bd2bd4bff9cafc9345221320bffb08b406a3` |
| quantization | AWQ 4-bit |
| thinking | `false` |
| temperature | 0.9 |
| top_p | 0.8 |
| top_k | 20 |
| repetition_penalty | 1.05 |
| max_new_tokens | 256 |
| generator_seed | 20260920 |
| batch_size | 96 |
| generator_version | 2 |
| config SHA-256 | `95ad971654c7fff3f7276ff95e552bae62d3f156341a8155ef26885ee2fb08c1` |

実行開始は2026年9月24日15:05:38 JST、終了は17:37:57 JSTであり、所要時間は9,138.493秒（2時間32分18.493秒）だった。

使用したpromptのSHA-256は次のとおりである。

| prompt | SHA-256 |
|---|---|
| `prompts/japanese_instruction_generation/paraphrase_system.txt` | `62227d1af50d644250a0c7494444eef834a092b2d72259db3dab573277a0924f` |
| `prompts/japanese_instruction_generation/paraphrase_user.txt` | `cd549eb7529db8262c8dd4ab210431c8f7885667ca196779752cc6a16a7011aa` |

## 3. 件数結果

| 区分 | 件数 |
|---|---:|
| 選抜した元指示 | 96,460 |
| 保存した生応答 | 96,460 |
| 厳密JSONのまま解析できた応答 | 86,056 |
| 既知の末尾引用符だけを補正した応答 | 10,404 |
| 補正後も解析できなかった応答 | 0 |
| 元文と異なる候補 | 96,390 |
| 元文と同一のため除外 | 70 |
| `<think>`またはコードフェンス混入 | 0 |
| 候補IDの重複 | 0 |
| 候補が対応する元指示IDの重複 | 0 |
| 候補本文の異なり数 | 95,222 |

10,404件の補正は、所定schemaで始まり、最後の閉じ二重引用符だけが単一引用符になった`']}`末尾へ限定した。生応答は変更せず保存し、該当レコードへ`parse_repaired=true`を記録している。それ以外を推測で修復した事例はない。

除外した70件はすべて、解析後の言い換え本文が元文と完全一致したケースである。JSON解析失敗、thinking混入、コードフェンス混入による除外はなかった。

## 4. 出力と検証値

| ファイル | レコード数 | バイト数 | SHA-256 |
|---|---:|---:|---|
| `data/instructions/teacher_paraphrase_candidates.jsonl` | 96,390 | 142,739,532 | `49067416be23e92a15886ff9a8840c1203f9ba91f4ba231fc7933d2c0001be35` |
| `data/instructions/teacher_paraphrase_raw_responses.jsonl` | 96,460 | 225,113,160 | `dd78de1b1e8f19f8587fcbcadc383da6dd7b25eba77db9b0438aa7da96214cbe` |
| `data/instructions/teacher_paraphrase_review.csv` | 96,390データ行 | 60,232,014 | `bfa05bac67221ad3f110da6d0247a1bfa3f5274510e6aacb78b09f7663dc6a3c` |
| `data/instructions/teacher_paraphrase_generation_stats.json` | 1集計 | 15,499 | `6ea43dbeb2fb0fcd339348012e2acdc5b3ac76c7d9c34528f7c409f6b88d167a` |

候補JSONL、生応答JSONL、確認CSVは人手承認前の作業物であり、GitHubへ公開する最終訓練データではない。そのためローカルに保持し、Gitでは追跡しない。再現条件と70件の除外IDを含む集計JSON、および本結果MDはGitで管理する。

### 4.1 どれが生データか

「元データ」と「モデルの生データ」を区別する。各ファイルの役割は次のとおりである。

| ファイル | 区分 | 内容 | 人が編集するか |
|---|---|---|---|
| `data/instructions/rule_generated_instructions.jsonl` | 言い換え元データ | ルールベースで作成した277,420指示。ここから96,460件を選抜した | 編集しない |
| `data/instructions/teacher_paraphrase_raw_responses.jsonl` | **モデル生データ** | Qwenへ渡したsystem/user prompt、Qwenが返した未変更の`raw_response`、seed、prompt hash、解析状態 | 編集しない |
| `data/instructions/teacher_paraphrase_candidates.jsonl` | 解析・検査済み候補 | 生応答をJSON解析し、元文一致、thinking、コードフェンスを除外した96,390候補。元文、意味AST、モデル来歴も保持する | 直接編集しない |
| `data/instructions/teacher_paraphrase_review.csv` | 人手レビュー用表示 | 候補JSONLから、意味AST、元文、言い換え文、判定欄を表形式へ展開したもの | **このCSVだけをレビュー時に編集する** |
| `data/instructions/teacher_paraphrase_generation_stats.json` | 集計データ | 実行条件、件数、70件の除外IDと理由 | 編集しない |
| `data/instructions/approved_teacher_paraphrases.jsonl` | 承認済みデータ | 利用者の明示指示で全96,390候補を一括承認し、承認情報を追加したもの | 編集しない |
| `docs/results/instruction_paraphrase_generation_results.md` | 結果報告 | 実行条件、検証結果、ファイルの役割を人が読める形でまとめたもの | 結果確定時だけ更新する |

データの流れは次のとおりである。

```text
言い換え元データ
  rule_generated_instructions.jsonl
    ↓ 固定seedで各意味ASTから10件選抜
モデル生データ
  teacher_paraphrase_raw_responses.jsonl
    ↓ JSON解析・既知末尾補正・形式検査
解析済み候補
  teacher_paraphrase_candidates.jsonl
    ↓ 人手確認用の列へ展開
レビュー作業ファイル
  teacher_paraphrase_review.csv
    ↓ 今回は利用者指示により全候補を一括承認
承認済み言い換え
  approved_teacher_paraphrases.jsonl
```

`raw_responses.jsonl`の`raw_response`は、末尾引用符を補正した10,404件についても変更していない。補正結果は候補作成時だけ使用し、生データ側には`parse_repaired=true`を追加して区別している。承認済みJSONLの作成でも、生応答と候補JSONLは変更していない。

## 5. 現在の状態と次工程

2026年9月24日、利用者の明示指示により候補96,390件を全件承認した。これは各候補を元文と個別比較した人手承認ではないため、承認済みレコードには`approval_mode=blanket_all_candidates`を記録して区別している。候補化の時点で元文と同一として除外した70件は承認対象に含めていない。

承認済みJSONLには、元指示ID、意味AST、モデルrevision、sampling設定、seed、prompt hashなど候補JSONLの全項目をそのまま引き継いだ。そのうえで、承認前の`pending`を`candidate_review_status`へ退避し、`review_status=approved`、承認者、承認日時、承認方式を追加した。件数、検証内容、SHA-256は[`instruction_paraphrase_approval_results.md`](instruction_paraphrase_approval_results.md)に記録している。

次工程では、承認済み言い換え96,390件を追加せず、各`source_instruction_id`が指すルール生成指示と一対一で置き換える。置換後も訓練用指示は192,900件である。その後、同じ`spec_id`と意味ASTを持つ検証済みコードへ一対一で対応付ける。結合前の件数分布は[`pre_join_distribution_report.md`](pre_join_distribution_report.md)に記録した。
