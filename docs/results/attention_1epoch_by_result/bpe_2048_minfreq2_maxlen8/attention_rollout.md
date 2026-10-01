# 短いpiece版BPE：attention rollout

[短いpiece版BPEの結果一覧](README.md)

残差を含むhead平均attentionを層間で掛け合わせた参照経路の近似である。causal decoderでは冒頭tokenへ偏りやすく、因果的重要度とはみなさない。

## 1M・1epoch

![1Mのattention rollout](../../attention_1epoch/boku_nano_1m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_rollout.svg)

## 5M・1epoch

![5Mのattention rollout](../../attention_1epoch/boku_nano_5m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_rollout.svg)

## 15M・1epoch

![15Mのattention rollout](../../attention_1epoch/boku_nano_15m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_rollout.svg)
