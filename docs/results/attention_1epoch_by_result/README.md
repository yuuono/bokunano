# 1epochモデルのattention解析：トークナイザー別一覧

1M・5M・15Mの各1epochモデルを、トークナイザーごとに分けて比較する入口である。各トークナイザーの配下に8種類のMarkdownがあり、同じトークナイザーで学習した3モデルの図を本文へ直接表示する。

| トークナイザー | 設定 | 結果一覧 |
|---|---|---|
| 既存BPE | 語彙2,048、最小頻度5、最大piece長24 | [1M・5M・15Mの8種類の図](bpe_2048_minfreq5_maxlen24/README.md) |
| 短いpiece版BPE | 語彙2,048、最小頻度2、最大piece長8 | [1M・5M・15Mの8種類の図](bpe_2048_minfreq2_maxlen8/README.md) |

対象は学習時準拠文型 `single-operation-training-aligned-v1` による解析結果である。旧「整数リストxsに対して、」文型の結果とは混在させていない。

## 読み分け

- 24操作を集計した図は、head別の記述的役割、BOS sink、因果的ablation、attention rolloutである。
- 単一promptを生成stepごとに追った図は、生成step×参照token位置、領域別attention、K/V類似度、token利用状況である。
- attention weightは参照分布の観測値であり、そのまま出力の根拠や因果的重要度を表さない。因果性はablationと実行結果を合わせて判断する。
- 既存BPEと短いpiece版BPEではtoken分割が異なるため、token位置やtoken単位NLLを直接比較しない。

[総合比較レポートへ戻る](../boku_nano_1epoch_attention_comparison.md)
