# 15M・既存BPE・1エポック：学習・評価報告

## 結論

15,735,168パラメータのDecoder-only Transformerを、既存BPE（語彙数2,048、`min_frequency=5`、`max_token_length=24`）でランダム初期値から1エポック学習した。固定5テストでは84,180 / 84,550件に合格し、pass@1は99.5624%、最終validation lossは0.410625だった。

## モデルとトークナイザー

| 項目 | 値 |
|---|---:|
| 総パラメータ数 | 15,735,168 |
| 語彙数 | 2,048 |
| hidden size | 384 |
| 層数 | 8 |
| Attention head数 | 6 |
| 1 head当たりの次元数 | 64 |
| FFN size | 1,024 |
| 最大系列長 | 256 |
| 位置表現 | RoPE |
| 正規化 / 活性化 | RMSNorm / SwiGLU |
| 入出力embedding共有 | なし |
| tokenizer最小頻度 / 最大piece長 | 5 / 24 |
| tokenizer SHA-256 | `6840a392e8fcae1083be06842774fa912a1797217c7033944ba2d87f1c227293` |
| seed | 20260925 |
| dtype / device | bfloat16 / cuda |
| micro / effective batch size | 512 / 512 |

## 学習結果

| 項目 | 結果 |
|---|---:|
| エポック | 1 |
| optimizer step | 377 |
| 1エポックの系列token | 6,939,466 |
| 全エポックの系列token | 6,939,466 |
| 1エポックのloss対象token | 3,746,067 |
| 全エポックのloss対象token | 3,746,067 |
| 学習時間 | 48.287秒 |
| モデルSHA-256 | `1a0002e1b50aeae59805d8087fbaa16be1b6e2716d78a085230f2cc35edbf68f` |

| Epoch | 終了step | train記録step | 最終train loss | Validation loss | Validation perplexity |
|---:|---:|---:|---:|---:|---:|
| 1 | 377 | 377 | 0.415411 | 0.410625 | 1.507761 |

train lossは原則として直近20 optimizer stepの区間平均であり、validation lossは各epoch終了時に固定validation 24,040件全体で計算した値である。縦軸は初期と収束後を同じ図で読めるよう対数目盛にしている。

![15M・既存BPE・1エポックの20 stepごとのloss](../figures/training_loss_20step/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch.svg)

## 固定5テストの評価

`greedy`生成、最大160 token、bfloat16で評価した。参照コードとの文字列一致ではなく、構文、安全AST、`solve(xs, k)`、入力非変更、各問のhidden testをすべて満たした場合を合格とした。

| テスト | 合格 | 不合格 | pass@1 |
|---|---:|---:|---:|
| 通常テスト | 24,003 / 24,040 | 37 | 99.8461% |
| 組合せ汎化テスト | 13,188 / 13,400 | 212 | 98.4179% |
| 日本語言い換えテスト | 15 / 30 | 15 | 50.0000% |
| 同一操作反復テスト | 22,971 / 23,040 | 69 | 99.7005% |
| 境界値テスト | 24,003 / 24,040 | 37 | 99.8461% |
| **合計・参考値** | **84,180 / 84,550** | **370** | **99.5624%** |

| 段階別指標 | 件数 | 率 |
|---|---:|---:|
| Syntax-valid | 84,534 / 84,550 | 99.9811% |
| Safe-AST | 84,534 / 84,550 | 99.9811% |
| Signature-valid | 84,534 / 84,550 | 99.9811% |
| Executable | 84,532 / 84,550 | 99.9787% |
| pass@1 | 84,180 / 84,550 | 99.5624% |
| 組合せ汎化率 | 13,188 / 13,400 | 98.4179% |

### 不合格の分類

| 分類 | 件数 |
|---|---:|
| hidden testで意味不一致 | 352 |
| 構文・安全AST・signatureの静的不合格 | 16 |
| 実行時例外またはtimeout | 2 |
| timeout（上段との重複内数） | 0 |

## attention解析

このモデルは24単独操作診断と生成step解析まで実施済みである。正式な固定5テストとはpromptと目的が異なるため、attention診断の合格数を正式pass@1と同一視しない。

![head別の記述的役割](../attention_1epoch/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_head_roles.svg)

![因果的ablation](../attention_1epoch/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_causal_ablation.svg)

![生成step×参照token位置](../attention_1epoch/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_by_layer_head.svg)

- [24操作解析JSON](../attention_1epoch/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/analysis.json)
- [生成step解析JSON](../attention_1epoch/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/detail_analysis.json)

## 成果物と再現情報

- [モデル本体](../../../data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/model.safetensors)
- [モデル設定](../../../data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/model_config.json)
- [学習設定](../../../data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/training_config.yaml)
- [学習manifest](../../../data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/training_manifest.json)
- [学習metrics](../../../data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/training_metrics.jsonl)
- 評価生データ: `data/evaluations/boku_nano_bpe_2048_1epoch/`（Git管理対象外）

```bash
scripts/model/run_boku_nano_experiment_nohup.sh \
  --model-size 15m --epochs 1 \
  --tokenizer bpe_2048_minfreq5_maxlen24

uv run --group model-training --python 3.12.12 python \
  scripts/model/evaluate_boku_nano.py \
  --config config/boku_nano_bpe_2048_1epoch_evaluation.yaml \
  --model-directory data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch \
  --output-directory data/evaluations/boku_nano_bpe_2048_1epoch
```
