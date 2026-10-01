# 既存BPE：1epochモデルのattention解析一覧

語彙数2,048、`min_frequency=5`、`max_token_length=24`の同一トークナイザーで学習した1M・5M・15Mモデルだけを比較する。各ページは3モデルの図を本文へ直接表示する。

| 結果の種類 | 報告書 |
|---|---|
| head別の記述的役割 | [図を見る](attention_head_roles.md) |
| BOS sinkとValueノルム | [図を見る](attention_sink_contribution.md) |
| 因果的ablation | [図を見る](attention_causal_ablation.md) |
| attention rollout | [図を見る](attention_rollout.md) |
| 生成step×参照token位置 | [図を見る](attention_by_layer_head.md) |
| 領域別attention | [図を見る](attention_regions.md) |
| K/Vのコサイン類似度 | [図を見る](kv_cosine_similarity.md) |
| token利用状況 | [図を見る](token_utilization.md) |

[トークナイザー選択へ戻る](../README.md)
