# 短いpiece版BPE：因果的ablation

[短いpiece版BPEの結果一覧](README.md)

head出力またはBOS・日本語指示位置のValueを無効化し、教師強制NLLと24操作の機能合格数の変化を示す。ΔNLLは無効化後NLLから基準NLLを引いた値である。

## 1M・1epoch

![1Mの因果的ablation](../../attention_1epoch/boku_nano_1m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_causal_ablation.svg)

## 5M・1epoch

![5Mの因果的ablation](../../attention_1epoch/boku_nano_5m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_causal_ablation.svg)

## 15M・1epoch

![15Mの因果的ablation](../../attention_1epoch/boku_nano_15m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_causal_ablation.svg)
