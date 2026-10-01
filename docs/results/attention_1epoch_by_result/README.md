# 1epochモデルのattention解析：結果種類別一覧

1M・5M・15Mの各1epochモデルについて、既存BPEと短いpiece版BPEの計6モデルを同じ図の種類ごとに比較するための入口である。各ページでは、SVGファイルへのリンクだけでなく、6モデルの図をMarkdown本文へ直接埋め込んでいる。

対象は学習時準拠文型 `single-operation-training-aligned-v1` による解析結果である。旧「整数リストxsに対して、」文型の結果とは混在させていない。

| 結果の種類 | 何を見る図か |
|---|---|
| [head別の記述的役割](attention_head_roles.md) | BOS、日本語指示、直前token、直近4 token、induction-like、entropyの層・head別集計 |
| [BOS sinkとValueノルム](attention_sink_contribution.md) | BOSへの生attentionと、Valueを考慮したベクトル寄与の比較 |
| [因果的ablation](attention_causal_ablation.md) | headまたは位置の無効化によるNLLと機能合格数の変化 |
| [attention rollout](attention_rollout.md) | 残差を含めて層をまたいだ参照経路の近似 |
| [生成step×参照token位置](attention_by_layer_head.md) | 単一promptに対する層・head別attentionヒートマップ |
| [領域別attention](attention_regions.md) | 制御token、日本語指示、生成済みコードへのattention比率 |
| [K/Vのコサイン類似度](kv_cosine_similarity.md) | token位置間のKey・Value表現の類似度 |
| [token利用状況](token_utilization.md) | 繰り返し参照されたtokenと参照の少ないtoken |

## 読み分け

- 24操作を集計した図は、head別の記述的役割、BOS sink、因果的ablation、attention rolloutである。
- 単一promptを生成stepごとに追った図は、生成step×参照token位置、領域別attention、K/V類似度、token利用状況である。
- attention weightは参照分布の観測値であり、そのまま出力の根拠や因果的重要度を表さない。因果性はablationと実行結果を合わせて判断する。
- 既存BPEと短いpiece版BPEではtoken分割が異なるため、token位置やtoken単位NLLを単純に横並び比較しない。

[総合比較レポートへ戻る](../boku_nano_1epoch_attention_comparison.md)
