# 既存BPE：K/Vのコサイン類似度

[既存BPEの結果一覧](README.md)

単一promptのtoken位置間でKey同士、Value同士のコサイン類似度を表示する。類似度はattention weightでも因果的重要度でもない。

## 1M・1epoch

![1MのK/V類似度](../../attention_1epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_1epoch/figures/kv_cosine_similarity.svg)

## 5M・1epoch

![5MのK/V類似度](../../attention_1epoch/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch/figures/kv_cosine_similarity.svg)

## 15M・1epoch

![15MのK/V類似度](../../attention_1epoch/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/figures/kv_cosine_similarity.svg)
