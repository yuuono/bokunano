# 既存BPE：token利用状況

[既存BPEの結果一覧](README.md)

単一promptで繰り返し上位参照されたtokenと、参照可能だったが平均attentionが小さいtokenを要約する。低い平均値だけを削除根拠にはしない。

## 1M・1epoch

![1Mのtoken利用状況](../../attention_1epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_1epoch/figures/token_utilization.svg)

## 5M・1epoch

![5Mのtoken利用状況](../../attention_1epoch/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch/figures/token_utilization.svg)

## 15M・1epoch

![15Mのtoken利用状況](../../attention_1epoch/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/figures/token_utilization.svg)
