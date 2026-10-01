# 15M・既存BPE・10エポック：学習・評価報告

## 結論

15,735,168パラメータのDecoder-only Transformerを、既存BPE（語彙数2,048、`min_frequency=5`、`max_token_length=24`）でランダム初期値から10エポック学習した。固定5テストでは83,058 / 84,550件に合格し、pass@1は98.2354%、最終validation lossは0.408651だった。

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
| エポック | 10 |
| optimizer step | 3,770 |
| 1エポックの系列token | 6,939,466 |
| 全エポックの系列token | 69,394,660 |
| 1エポックのloss対象token | 3,746,067 |
| 全エポックのloss対象token | 37,460,670 |
| 学習時間 | 190.719秒 |
| モデルSHA-256 | `6852e36364c4f87a44646ebf01262f661bbbadc112c5d6e8daed2d045461aa7b` |

| Epoch | 終了step | train記録step | 最終train loss | Validation loss | Validation perplexity |
|---:|---:|---:|---:|---:|---:|
| 1 | 377 | 360 | 0.435268 | 0.426711 | 1.532210 |
| 2 | 754 | 740 | 0.409853 | 0.405369 | 1.499855 |
| 3 | 1,131 | 1,120 | 0.404248 | 0.400551 | 1.492646 |
| 4 | 1,508 | 1,500 | 0.400485 | 0.397954 | 1.488776 |
| 5 | 1,885 | 1,880 | 0.396777 | 0.396466 | 1.486561 |
| 6 | 2,262 | 2,260 | 0.394883 | 0.395044 | 1.484449 |
| 7 | 2,639 | 2,620 | 0.389388 | 0.395264 | 1.484776 |
| 8 | 3,016 | 3,000 | 0.383641 | 0.397339 | 1.487860 |
| 9 | 3,393 | 3,380 | 0.376495 | 0.401870 | 1.494617 |
| 10 | 3,770 | 3,770 | 0.368791 | 0.408651 | 1.504787 |

train lossは原則として直近20 optimizer stepの区間平均であり、validation lossは各epoch終了時に固定validation 24,040件全体で計算した値である。縦軸は初期と収束後を同じ図で読めるよう対数目盛にしている。

![15M・既存BPE・10エポックの20 stepごとのloss](../figures/training_loss_20step/boku_nano_15m_bpe_2048_minfreq5_maxlen24_10epoch.svg)

## 固定5テストの評価

`greedy`生成、最大160 token、bfloat16で評価した。参照コードとの文字列一致ではなく、構文、安全AST、`solve(xs, k)`、入力非変更、各問のhidden testをすべて満たした場合を合格とした。

| テスト | 合格 | 不合格 | pass@1 |
|---|---:|---:|---:|
| 通常テスト | 23,980 / 24,040 | 60 | 99.7504% |
| 組合せ汎化テスト | 13,334 / 13,400 | 66 | 99.5075% |
| 日本語言い換えテスト | 21 / 30 | 9 | 70.0000% |
| 同一操作反復テスト | 21,743 / 23,040 | 1,297 | 94.3707% |
| 境界値テスト | 23,980 / 24,040 | 60 | 99.7504% |
| **合計・参考値** | **83,058 / 84,550** | **1,492** | **98.2354%** |

| 段階別指標 | 件数 | 率 |
|---|---:|---:|
| Syntax-valid | 84,301 / 84,550 | 99.7055% |
| Safe-AST | 84,301 / 84,550 | 99.7055% |
| Signature-valid | 84,301 / 84,550 | 99.7055% |
| Executable | 84,285 / 84,550 | 99.6866% |
| pass@1 | 83,058 / 84,550 | 98.2354% |
| 組合せ汎化率 | 13,334 / 13,400 | 99.5075% |

### 不合格の分類

| 分類 | 件数 |
|---|---:|
| hidden testで意味不一致 | 1,227 |
| 構文・安全AST・signatureの静的不合格 | 249 |
| 実行時例外またはtimeout | 16 |
| timeout（上段との重複内数） | 1 |

## attention解析

このモデル単体のattention詳細解析は未実施である。学習・実行評価の数値とは区別して記録する。

## 成果物と再現情報

- [モデル本体](../../../data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_10epoch/model.safetensors)
- [モデル設定](../../../data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_10epoch/model_config.json)
- [学習設定](../../../data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_10epoch/training_config.yaml)
- [学習manifest](../../../data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_10epoch/training_manifest.json)
- [学習metrics](../../../data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_10epoch/training_metrics.jsonl)
- 評価生データ: `data/evaluations/boku_nano_bpe_2048_10epoch/`（Git管理対象外）

```bash
scripts/model/run_boku_nano_experiment_nohup.sh \
  --model-size 15m --epochs 10 \
  --tokenizer bpe_2048_minfreq5_maxlen24

uv run --group model-training --python 3.12.12 python \
  scripts/model/evaluate_boku_nano.py \
  --config config/boku_nano_evaluation.yaml \
  --model-directory data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_10epoch \
  --output-directory data/evaluations/boku_nano_bpe_2048_10epoch
```
