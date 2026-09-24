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

## 5. 現在の状態と次工程

生成された96,390件はすべて`review_status=pending`であり、まだ訓練データへ採用していない。次工程では`teacher_paraphrase_review.csv`を使い、意味AST、元文、言い換え文を比較して意味、定数、比較境界、操作順が同じ候補だけを人手承認する。

承認済み候補を作成するときは、元指示ID、意味AST、モデルrevision、sampling設定、seed、prompt hashを候補JSONLから失わず引き継ぐ。未承認候補を含む現時点ではZIPを作成せず、承認済みデータだけを最終成果物として別途アーカイブする。
