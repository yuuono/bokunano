# 学習済みモデル別の統一報告書

保存済みの全10モデルについて、モデル設定、トークナイザー、学習量、20 stepごとのloss、固定5テスト、段階別評価、attention解析状況、再現情報を同じ書式でまとめた。

モデル間の比較ではpass@1を主指標とする。異なるトークナイザー間ではtoken分割単位が違うため、lossの絶対値だけを直接比較しない。

| モデル | パラメータ | 学習系列token | 最終Validation loss | 固定5テスト | attention |
|---|---:|---:|---:|---:|---|
| [1M・既存BPE・1エポック](boku_nano_1m_bpe_2048_minfreq5_maxlen24_1epoch.md) | 1,016,704 | 6,939,466 | 1.378111 | 1,467 / 84,550（1.7351%） | 実施済み |
| [1M・既存BPE・3エポック](boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch.md) | 1,016,704 | 20,818,398 | 0.436444 | 84,171 / 84,550（99.5517%） | 実施済み |
| [1M・短いpiece版BPE・1エポック](boku_nano_1m_bpe_2048_minfreq2_maxlen8_1epoch.md) | 1,016,704 | 17,281,995 | 0.524322 | 4,572 / 84,550（5.4075%） | 実施済み |
| [1M・短いpiece版BPE・3エポック](boku_nano_1m_bpe_2048_minfreq2_maxlen8_3epoch.md) | 1,016,704 | 51,845,985 | 0.153865 | 83,890 / 84,550（99.2194%） | 実施済み |
| [5M・既存BPE・1エポック](boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch.md) | 5,065,472 | 6,939,466 | 0.485457 | 81,557 / 84,550（96.4601%） | 実施済み |
| [5M・短いpiece版BPE・1エポック](boku_nano_5m_bpe_2048_minfreq2_maxlen8_1epoch.md) | 5,065,472 | 17,281,995 | 0.163488 | 82,353 / 84,550（97.4015%） | 実施済み |
| [15M・既存BPE・1エポック](boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch.md) | 15,735,168 | 6,939,466 | 0.410625 | 84,180 / 84,550（99.5624%） | 実施済み |
| [15M・既存BPE・3エポック](boku_nano_15m_bpe_2048_minfreq5_maxlen24_3epoch.md) | 15,735,168 | 20,818,398 | 0.393880 | 84,434 / 84,550（99.8628%） | 実施済み |
| [15M・既存BPE・10エポック](boku_nano_15m_bpe_2048_minfreq5_maxlen24_10epoch.md) | 15,735,168 | 69,394,660 | 0.408651 | 83,058 / 84,550（98.2354%） | 未実施 |
| [15M・短いpiece版BPE・1エポック](boku_nano_15m_bpe_2048_minfreq2_maxlen8_1epoch.md) | 15,735,168 | 17,281,995 | 0.149202 | 84,305 / 84,550（99.7102%） | 実施済み |

## 関連資料

- [全モデルの20 stepごとのloss図](../training_loss_every_20_steps.md)
- [学習済みモデル一覧とハッシュ](../trained_model_inventory.md)
- [モデル評価方針](../../policies/boku_nano_model_evaluation_policy.md)
- [ドキュメント全体の入口](../../README.md)
