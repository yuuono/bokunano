# 短いpiece版BPE：生成step×参照token位置

[短いpiece版BPEの結果一覧](README.md)

単一promptについて、横軸を参照token位置、縦軸を生成stepとして層・head別に表示する。赤線はpromptと生成コードの境界である。

## 1M・1epoch

![1Mの生成step別attention](../../attention_1epoch/boku_nano_1m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_by_layer_head.svg)

## 5M・1epoch

![5Mの生成step別attention](../../attention_1epoch/boku_nano_5m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_by_layer_head.svg)

## 15M・1epoch

![15Mの生成step別attention](../../attention_1epoch/boku_nano_15m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_by_layer_head.svg)
