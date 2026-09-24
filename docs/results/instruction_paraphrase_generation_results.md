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
    ↓ approvedだけを来歴付きで統合（次工程）
承認済み言い換え
  approved_teacher_paraphrases.jsonl
```

`raw_responses.jsonl`の`raw_response`は、末尾引用符を補正した10,404件についても変更していない。補正結果は候補作成時だけ使用し、生データ側には`parse_repaired=true`を追加して区別している。また、レビューCSVを編集しても候補JSONLへ自動反映されない。承認結果をJSONLへ統合する専用処理が別途必要である。

## 5. 現在の状態と次工程

生成された96,390件はすべて`review_status=pending`であり、まだ訓練データへ採用していない。次工程では`teacher_paraphrase_review.csv`を使い、意味AST、元文、言い換え文を比較して意味、定数、比較境界、操作順が同じ候補だけを人手承認する。

承認済み候補を作成するときは、元指示ID、意味AST、モデルrevision、sampling設定、seed、prompt hashを候補JSONLから失わず引き継ぐ。未承認候補を含む現時点ではZIPを作成せず、承認済みデータだけを最終成果物として別途アーカイブする。

次に行う作業は、次の順番とする。

1. `teacher_paraphrase_review.csv`の各行について、意味、定数、比較境界、操作順が元文と一致するか確認する。
2. 採用する行へ`review_status=approved`、採用しない行へ`review_status=unused`を記入する。修正文を採用する場合は`edited_instruction_ja`へ記入し、`reviewer`と`reviewed_at`も埋める。
3. レビューCSVの`approved`だけを候補JSONLへ突き合わせ、全来歴を保持した`data/instructions/approved_teacher_paraphrases.jsonl`を作る。
4. 承認済み言い換えを意味ASTで検証済みコードへ対応付け、`test_only`表現が混ざっていないことを検査する。
5. 最終採用データだけをZIPへまとめ、件数、SHA-256、結合結果を別の結果MDへ記録する。

現時点では、3の「レビューCSVから承認済みJSONLを作る専用スクリプト」はまだ実装されていない。したがって、直近の実装課題はこの統合スクリプトを作ることであり、直近の人手作業はレビューCSVの判定方針と一回に確認する範囲を決めることである。
