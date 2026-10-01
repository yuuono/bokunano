# 既存BPE：領域別attention

[既存BPEの結果一覧](README.md)

単一promptのattentionを制御token、日本語指示、生成済みコードへ分けて全層・全headで平均した。領域token数が異なるため、総量だけで重要性を判断しない。

## 1M・1epoch

![1Mの領域別attention](../../attention_1epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_regions.svg)

## 5M・1epoch

![5Mの領域別attention](../../attention_1epoch/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_regions.svg)

## 15M・1epoch

![15Mの領域別attention](../../attention_1epoch/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_regions.svg)
