# 短いpiece版BPE：head別の記述的役割

[短いpiece版BPEの結果一覧](README.md)

24単独操作の全生成stepについて、BOS、日本語指示、直前token、直近4 token、induction-like、正規化entropyを層・head別に集計した。Valueではなくattention weightの要約である。

## 1M・1epoch

![1Mのhead別役割](../../attention_1epoch/boku_nano_1m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_head_roles.svg)

## 5M・1epoch

![5Mのhead別役割](../../attention_1epoch/boku_nano_5m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_head_roles.svg)

## 15M・1epoch

![15Mのhead別役割](../../attention_1epoch/boku_nano_15m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_head_roles.svg)
