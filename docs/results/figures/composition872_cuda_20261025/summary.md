# Boku-nano：旧872問のCUDAバッチ評価

生成日時: 2026-10-25T18:17:24.235432+09:00。固有モデル数: 18。

旧872問・9カテゴリ・179検査入力を固定し、保存済みCUDA float32のgreedy生成を集計した。履歴・修復なし、context 256。
モデル容量・訓練epoch・tokenizerが異なるため、総合順位だけでloopやtokenizerの因果効果は判断しない。
短いBPEは別群として表示する。［設定復元］は、元の学習manifestが保存されていない既存重みに評価用設定を復元したことを示す。

## 総合結果

| モデル | 群 | パラメータ数 | epoch | 合格 / 872 | 正解率 |
|---|---|---:|---:|---:|---:|
| boku-1m-3epoch (1M・3 epoch) | 通常モデル・標準BPE | 1,016,704 | 3 | 751/872 | 86.1239% |
| ablation-heads4-dim64 (8層・幅256 / 9.44M・1 epoch) | 構造比較・標準BPE | 9,441,536 | 1 | 749/872 | 85.8945% |
| ablation-layers6 (6層・幅384 / 12.19M・1 epoch) | 構造比較・標準BPE | 12,194,688 | 1 | 743/872 | 85.2064% |
| boku-15m-1epoch (15M・1 epoch) | 通常モデル・標準BPE | 15,735,168 | 1 | 728/872 | 83.4862% |
| boku-5m-short-1epoch (5M・1 epoch［短いBPE］) | 通常モデル・短いBPE | 5,065,472 | 1 | 725/872 | 83.1422% |
| boku-1m-short-3epoch (1M・3 epoch［短いBPE］) | 通常モデル・短いBPE | 1,016,704 | 3 | 724/872 | 83.0275% |
| boku-15m-short-1epoch (15M・1 epoch［短いBPE］) | 通常モデル・短いBPE | 15,735,168 | 1 | 721/872 | 82.6835% |
| ablation-layers4 (4層・幅384 / 8.65M・1 epoch) | 構造比較・標準BPE | 8,654,208 | 1 | 708/872 | 81.1927% |
| boku-15m-3epoch (15M・3 epoch) | 通常モデル・標準BPE | 15,735,168 | 3 | 687/872 | 78.7844% |
| boku-5m-1epoch (5M・1 epoch) | 通常モデル・標準BPE | 5,065,472 | 1 | 676/872 | 77.5229% |
| ablation-layers2 (2層・幅384 / 5.11M・1 epoch) | 構造比較・標準BPE | 5,113,728 | 1 | 667/872 | 76.4908% |
| boku-15m-10epoch (15M・10 epoch) | 通常モデル・標準BPE | 15,735,168 | 10 | 612/872 | 70.1835% |
| loop-lt1-3epoch (LT1  0.426M・3 epoch［設定復元］) | 小型Looped・標準BPE | 426,368 | 3 | 243/872 | 27.8670% |
| loop-f128-3epoch (F128  0.377M・3 epoch［設定復元］) | 小型Looped・標準BPE | 377,216 | 3 | 147/872 | 16.8578% |
| boku-1m-1epoch (1M・1 epoch) | 通常モデル・標準BPE | 1,016,704 | 1 | 33/872 | 3.7844% |
| boku-1m-short-1epoch (1M・1 epoch［短いBPE］) | 通常モデル・短いBPE | 1,016,704 | 1 | 15/872 | 1.7202% |
| loop-w96-3epoch (W96  0.289M・3 epoch［設定復元］) | 小型Looped・標準BPE | 289,056 | 3 | 14/872 | 1.6055% |
| loop-w64-3epoch (W64  0.172M・3 epoch［設定復元］) | 小型Looped・標準BPE | 172,224 | 3 | 2/872 | 0.2294% |

## カテゴリ別の合格数と正解率

| モデル | 1操作への転移 | 未学習2操作 | 3→2操作への転移 | 同一操作×2 | 未学習3操作 | 同一操作×3 | 一般4操作 | ABAB型4操作 | 同一操作×4 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| boku-15m-1epoch | 88/96 (91.67%) | 98/100 (98.00%) | 88/88 (100.00%) | 94/96 (97.92%) | 96/100 (96.00%) | 94/96 (97.92%) | 29/100 (29.00%) | 70/100 (70.00%) | 71/96 (73.96%) |
| boku-15m-3epoch | 96/96 (100.00%) | 98/100 (98.00%) | 88/88 (100.00%) | 95/96 (98.96%) | 100/100 (100.00%) | 91/96 (94.79%) | 2/100 (2.00%) | 56/100 (56.00%) | 61/96 (63.54%) |
| boku-15m-10epoch | 95/96 (98.96%) | 100/100 (100.00%) | 87/88 (98.86%) | 79/96 (82.29%) | 99/100 (99.00%) | 70/96 (72.92%) | 0/100 (0.00%) | 48/100 (48.00%) | 34/96 (35.42%) |
| boku-5m-1epoch | 81/96 (84.38%) | 94/100 (94.00%) | 85/88 (96.59%) | 89/96 (92.71%) | 95/100 (95.00%) | 91/96 (94.79%) | 7/100 (7.00%) | 62/100 (62.00%) | 72/96 (75.00%) |
| boku-1m-1epoch | 12/96 (12.50%) | 0/100 (0.00%) | 6/88 (6.82%) | 6/96 (6.25%) | 0/100 (0.00%) | 4/96 (4.17%) | 0/100 (0.00%) | 2/100 (2.00%) | 3/96 (3.12%) |
| boku-1m-3epoch | 82/96 (85.42%) | 99/100 (99.00%) | 88/88 (100.00%) | 96/96 (100.00%) | 100/100 (100.00%) | 95/96 (98.96%) | 43/100 (43.00%) | 78/100 (78.00%) | 70/96 (72.92%) |
| boku-15m-short-1epoch | 96/96 (100.00%) | 100/100 (100.00%) | 87/88 (98.86%) | 94/96 (97.92%) | 99/100 (99.00%) | 91/96 (94.79%) | 22/100 (22.00%) | 74/100 (74.00%) | 58/96 (60.42%) |
| boku-5m-short-1epoch | 93/96 (96.88%) | 100/100 (100.00%) | 86/88 (97.73%) | 96/96 (100.00%) | 96/100 (96.00%) | 95/96 (98.96%) | 14/100 (14.00%) | 73/100 (73.00%) | 72/96 (75.00%) |
| boku-1m-short-1epoch | 6/96 (6.25%) | 0/100 (0.00%) | 1/88 (1.14%) | 1/96 (1.04%) | 0/100 (0.00%) | 3/96 (3.12%) | 0/100 (0.00%) | 1/100 (1.00%) | 3/96 (3.12%) |
| boku-1m-short-3epoch | 94/96 (97.92%) | 100/100 (100.00%) | 88/88 (100.00%) | 96/96 (100.00%) | 100/100 (100.00%) | 95/96 (98.96%) | 15/100 (15.00%) | 73/100 (73.00%) | 63/96 (65.62%) |
| ablation-layers6 | 86/96 (89.58%) | 100/100 (100.00%) | 88/88 (100.00%) | 93/96 (96.88%) | 99/100 (99.00%) | 96/96 (100.00%) | 26/100 (26.00%) | 75/100 (75.00%) | 80/96 (83.33%) |
| ablation-heads4-dim64 | 87/96 (90.62%) | 97/100 (97.00%) | 88/88 (100.00%) | 94/96 (97.92%) | 99/100 (99.00%) | 95/96 (98.96%) | 33/100 (33.00%) | 77/100 (77.00%) | 79/96 (82.29%) |
| ablation-layers4 | 82/96 (85.42%) | 100/100 (100.00%) | 88/88 (100.00%) | 94/96 (97.92%) | 100/100 (100.00%) | 92/96 (95.83%) | 24/100 (24.00%) | 67/100 (67.00%) | 61/96 (63.54%) |
| ablation-layers2 | 80/96 (83.33%) | 96/100 (96.00%) | 84/88 (95.45%) | 96/96 (100.00%) | 96/100 (96.00%) | 95/96 (98.96%) | 5/100 (5.00%) | 54/100 (54.00%) | 61/96 (63.54%) |
| loop-lt1-3epoch | 36/96 (37.50%) | 33/100 (33.00%) | 31/88 (35.23%) | 52/96 (54.17%) | 18/100 (18.00%) | 33/96 (34.38%) | 0/100 (0.00%) | 19/100 (19.00%) | 21/96 (21.88%) |
| loop-f128-3epoch | 24/96 (25.00%) | 21/100 (21.00%) | 20/88 (22.73%) | 33/96 (34.38%) | 7/100 (7.00%) | 20/96 (20.83%) | 0/100 (0.00%) | 12/100 (12.00%) | 10/96 (10.42%) |
| loop-w96-3epoch | 4/96 (4.17%) | 0/100 (0.00%) | 0/88 (0.00%) | 4/96 (4.17%) | 0/100 (0.00%) | 4/96 (4.17%) | 0/100 (0.00%) | 0/100 (0.00%) | 2/96 (2.08%) |
| loop-w64-3epoch | 0/96 (0.00%) | 0/100 (0.00%) | 0/88 (0.00%) | 1/96 (1.04%) | 0/100 (0.00%) | 1/96 (1.04%) | 0/100 (0.00%) | 0/100 (0.00%) | 0/96 (0.00%) |

## 図

- [category_heatmap: PNG](category_heatmap.png) / [SVG](category_heatmap.svg) / [PDF](category_heatmap.pdf)
- [overall_pass_rate: PNG](overall_pass_rate.png) / [SVG](overall_pass_rate.svg) / [PDF](overall_pass_rate.pdf)
- [categories_standard: PNG](categories_standard.png) / [SVG](categories_standard.svg) / [PDF](categories_standard.pdf)
- [categories_short: PNG](categories_short.png) / [SVG](categories_short.svg) / [PDF](categories_short.pdf)
- [categories_ablation: PNG](categories_ablation.png) / [SVG](categories_ablation.svg) / [PDF](categories_ablation.pdf)
- [categories_looped: PNG](categories_looped.png) / [SVG](categories_looped.svg) / [PDF](categories_looped.pdf)

## 検証と再現性

各runのcompleted状態、問題・採点器hash、raw/scored/summaryの保存hash、872問のID・AST・カテゴリ、問題別合否からの再集計を検証した。
同一重み・構造・tokenizerの重複評価は問題別合否が一致する場合だけ統合した。異なる評価時点のrunner hashは保存し、現行ファイルとの一致は要求しない。
全モデルの設定・runパス・入力成果物hash・評価当時のsource hash・問題別合否・失敗理由は[values.json](values.json)に保存している。

| 固定入力 | SHA-256 |
|---|---|
| questions.jsonl | `aa119fa2a9e8507136ad14a54b9d3d2e9043fd81af9e48251ef7f5c49c20f97f` |
| test_cases.json | `0090a38d255848a813876ce3b64a8029603aa14e4181b453a89801b41ac67fc2` |
| protocol.json | `6af76f37503d99590e88307c107f8529aebac79f6c3593eb0016ab4ae766c22d` |
| 標準BPE | `6840a392e8fcae1083be06842774fa912a1797217c7033944ba2d87f1c227293` |
| 短いBPE | `f09f3d7eccbca2ab1224c662064b71e572d64147147b8b559ebdb428eb035dbf` |

| run | 完了日時 | comparison.json SHA-256 |
|---|---|---|
| `data/evaluations/composition872_cuda_20261025_baselines` | 2026-10-25T09:06:56.983685+00:00 | `ea3f0b294082eca1046e1c6b27da0f9725a30a6d9729a65558cec4ba5e61f81e` |
| `data/evaluations/composition872_cuda_20261025_standard_extra` | 2026-10-25T09:10:10.634044+00:00 | `86830892309083311d9eff79305c935325707783c4a5abd2984e0baf5e0f1695` |
| `data/evaluations/composition872_cuda_20261025_short_bpe` | 2026-10-25T09:12:48.211899+00:00 | `3169985e3207efa3afae2298386237bd621afde1a5507bb5e452b739beb6a26e` |
| `data/evaluations/composition872_cuda_20261025_small_loops` | 2026-10-25T09:14:01.817159+00:00 | `a16cfc6d828afd371cfa24fb88600c28c47a82cd83090bedf7b2c4f278782a57` |

| モデル | 重みSHA-256 | run |
|---|---|---|
| boku-15m-1epoch | `1a0002e1b50aeae59805d8087fbaa16be1b6e2716d78a085230f2cc35edbf68f` | `data/evaluations/composition872_cuda_20261025_baselines` |
| boku-15m-3epoch | `5623f066cc47ef58790e56d5a62fe9a258d502569995a7aff6c65558c622cf0e` | `data/evaluations/composition872_cuda_20261025_standard_extra` |
| boku-15m-10epoch | `6852e36364c4f87a44646ebf01262f661bbbadc112c5d6e8daed2d045461aa7b` | `data/evaluations/composition872_cuda_20261025_standard_extra` |
| boku-5m-1epoch | `027fe1b64c4495dd39322f0ade7824e085b7315543c840b031742e42f4a4c0c6` | `data/evaluations/composition872_cuda_20261025_baselines` |
| boku-1m-1epoch | `c4774c30963d00fee31f52ffc2201f85713cc941832b0c412161ce46541c2b0a` | `data/evaluations/composition872_cuda_20261025_standard_extra` |
| boku-1m-3epoch | `e9eafad8c5195b501414c4456b04918258cc1a3a6ef799d5d77f3ea69cd17533` | `data/evaluations/composition872_cuda_20261025_baselines` |
| boku-15m-short-1epoch | `c019688997247f4bc10198703364d88584ff63539d1e6a739764ab372bd1ed83` | `data/evaluations/composition872_cuda_20261025_short_bpe` |
| boku-5m-short-1epoch | `0c2ad06d34004ffeae122409b6aa355d08e41b39e7303d3fd0cca8a4984eb5f9` | `data/evaluations/composition872_cuda_20261025_short_bpe` |
| boku-1m-short-1epoch | `1e9bd1911fd405c2e5e839b38cf5744ea7a287d1e7595f747845eadcce302576` | `data/evaluations/composition872_cuda_20261025_short_bpe` |
| boku-1m-short-3epoch | `216cc2ce080131455705af5a6589653d090f4d5ee42d031cf97cc15d796a4d7d` | `data/evaluations/composition872_cuda_20261025_short_bpe` |
| ablation-layers6 | `e155006401527bc911b876381b8c23169b594b9837f00422cd196ec782bc2ccf` | `data/evaluations/composition872_cuda_20261025_standard_extra` |
| ablation-heads4-dim64 | `c02213422216b1bf6bb9cc6ca61f9afa153d6309e4402a1f6402e4f802a752ee` | `data/evaluations/composition872_cuda_20261025_standard_extra` |
| ablation-layers4 | `2d734ce0fdde2e8e4091791261f752c2b52c90a48f602fd133b4ea0a610cb29a` | `data/evaluations/composition872_cuda_20261025_standard_extra` |
| ablation-layers2 | `82731d22985b5f8ce0b3c02e1cc1705b3ad12b765c11b75400cf7b13a5c1c3da` | `data/evaluations/composition872_cuda_20261025_standard_extra` |
| loop-lt1-3epoch | `34266e64bcc100975f804f6d7b80c3061227911c381afd0f85d4f17bec36f704` | `data/evaluations/composition872_cuda_20261025_small_loops` |
| loop-f128-3epoch | `c8a7a3a0f7761a7a2ceceab408c70f5f0ba375821a9a4aaff60671c7dfbdd485` | `data/evaluations/composition872_cuda_20261025_small_loops` |
| loop-w96-3epoch | `a8723af569667ef9b5b1bbbaa46d4102b95513e04be416c4abe3b79e4b2b52ed` | `data/evaluations/composition872_cuda_20261025_small_loops` |
| loop-w64-3epoch | `0f0c290cf8875e6a0d2949732684b306a40012de939a1a49fed6eaf84a87b193` | `data/evaluations/composition872_cuda_20261025_small_loops` |

### 解釈上の範囲

- 正解率は固定問題に対する実行評価。訓練データの成績や通常の84,550件評価とは別の指標。
- 時間はrun_metricsに記録された推論区間の測定値で、採点・重み読込・訓練時間を含まない。
- 単一checkpointの比較であり、複数seedの平均・信頼区間ではない。
