# 1M・既存BPE・3エポック：学習・評価報告

## 結論

1,016,704パラメータのDecoder-only Transformerを、既存BPE（語彙数2,048、`min_frequency=5`、`max_token_length=24`）でランダム初期値から3エポック学習した。固定5テストでは84,171 / 84,550件に合格し、pass@1は99.5517%、最終validation lossは0.436444だった。

## モデルとトークナイザー

| 項目 | 値 |
|---|---:|
| 総パラメータ数 | 1,016,704 |
| 語彙数 | 2,048 |
| hidden size | 128 |
| 層数 | 3 |
| Attention head数 | 4 |
| 1 head当たりの次元数 | 32 |
| FFN size | 256 |
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
| エポック | 3 |
| optimizer step | 1,131 |
| 1エポックの系列token | 6,939,466 |
| 全エポックの系列token | 20,818,398 |
| 1エポックのloss対象token | 3,746,067 |
| 全エポックのloss対象token | 11,238,201 |
| 学習時間 | 43.024秒 |
| モデルSHA-256 | `e9eafad8c5195b501414c4456b04918258cc1a3a6ef799d5d77f3ea69cd17533` |

| Epoch | 終了step | train記録step | 最終train loss | Validation loss | Validation perplexity |
|---:|---:|---:|---:|---:|---:|
| 1 | 377 | 360 | 0.951613 | 0.873668 | 2.395683 |
| 2 | 754 | 740 | 0.480474 | 0.469092 | 1.598542 |
| 3 | 1,131 | 1,131 | 0.439302 | 0.436444 | 1.547196 |

train lossは原則として直近20 optimizer stepの区間平均であり、validation lossは各epoch終了時に固定validation 24,040件全体で計算した値である。縦軸は初期と収束後を同じ図で読めるよう対数目盛にしている。

![1M・既存BPE・3エポックの20 stepごとのloss](../figures/training_loss_20step/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch.svg)

## 固定5テストの評価

`greedy`生成、最大160 token、bfloat16で評価した。参照コードとの文字列一致ではなく、構文、安全AST、`solve(xs, k)`、入力非変更、各問のhidden testをすべて満たした場合を合格とした。

| テスト | 合格 | 不合格 | pass@1 |
|---|---:|---:|---:|
| 通常テスト | 23,950 / 24,040 | 90 | 99.6256% |
| 組合せ汎化テスト | 13,311 / 13,400 | 89 | 99.3358% |
| 日本語言い換えテスト | 15 / 30 | 15 | 50.0000% |
| 同一操作反復テスト | 22,945 / 23,040 | 95 | 99.5877% |
| 境界値テスト | 23,950 / 24,040 | 90 | 99.6256% |
| **合計・参考値** | **84,171 / 84,550** | **379** | **99.5517%** |

| 段階別指標 | 件数 | 率 |
|---|---:|---:|
| Syntax-valid | 84,539 / 84,550 | 99.9870% |
| Safe-AST | 84,539 / 84,550 | 99.9870% |
| Signature-valid | 84,539 / 84,550 | 99.9870% |
| Executable | 84,534 / 84,550 | 99.9811% |
| pass@1 | 84,171 / 84,550 | 99.5517% |
| 組合せ汎化率 | 13,311 / 13,400 | 99.3358% |

### 不合格の分類

| 分類 | 件数 |
|---|---:|
| hidden testで意味不一致 | 363 |
| 構文・安全AST・signatureの静的不合格 | 11 |
| 実行時例外またはtimeout | 5 |
| timeout（上段との重複内数） | 0 |

## attention解析

このモデルは24単独操作診断と生成step解析まで実施済みである。正式な固定5テストとはpromptと目的が異なるため、attention診断の合格数を正式pass@1と同一視しない。

![head別の記述的役割](../attention_3epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/figures/attention_head_roles.svg)

![因果的ablation](../attention_3epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/figures/attention_causal_ablation.svg)

![生成step×参照token位置](../attention_3epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/figures/attention_by_layer_head.svg)

- [24操作解析JSON](../attention_3epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/analysis.json)
- [生成step解析JSON](../attention_3epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/detail_analysis.json)

## 成果物と再現情報

- [モデル本体](../../../data/models/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/model.safetensors)
- [モデル設定](../../../data/models/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/model_config.json)
- [学習設定](../../../data/models/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/training_config.yaml)
- [学習manifest](../../../data/models/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/training_manifest.json)
- [学習metrics](../../../data/models/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/training_metrics.jsonl)
- 評価生データ: `data/evaluations/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/`（Git管理対象外）

```bash
scripts/model/run_boku_nano_experiment_nohup.sh \
  --model-size 1m --epochs 3 \
  --tokenizer bpe_2048_minfreq5_maxlen24

uv run --group model-training --python 3.12.12 python \
  scripts/model/evaluate_boku_nano.py \
  --config config/boku_nano_1m_bpe_2048_1epoch_evaluation.yaml \
  --model-directory data/models/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch \
  --output-directory data/evaluations/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch
```
