# 学習済みBoku Nanoモデル一覧

## 一覧の基準

model.safetensorsとstatus=completedのtraining_manifest.jsonが実在するモデルだけを「学習済み」として掲載する。設定や起動スクリプトだけのモデルは含めない。

2026年10月1日時点で、学習済みモデルは8個である。パラメータ規模は正確に1,016,704、5,065,472、15,735,168の3種類である。

## 学習済みモデル

| モデル | 正確なパラメータ数 | 構造 | トークナイザー | epoch | 学習系列token | 固定5テスト |
|---|---:|---|---|---:|---:|---:|
| 1M・既存BPE・1ep | 1,016,704 | d=128、3層、4 head、FFN 256 | min 5 / max 24 | 1 | 6,939,466 | 1,467 / 84,550（1.7351%） |
| 1M・短いpiece・1ep | 1,016,704 | d=128、3層、4 head、FFN 256 | min 2 / max 8 | 1 | 17,281,995 | 4,572 / 84,550（5.4075%） |
| 5M・既存BPE・1ep | 5,065,472 | d=256、5層、4 head、FFN 704 | min 5 / max 24 | 1 | 6,939,466 | 81,557 / 84,550（96.4601%） |
| 5M・短いpiece・1ep | 5,065,472 | d=256、5層、4 head、FFN 704 | min 2 / max 8 | 1 | 17,281,995 | 82,353 / 84,550（97.4015%） |
| 15M・既存BPE・1ep | 15,735,168 | d=384、8層、6 head、FFN 1,024 | min 5 / max 24 | 1 | 6,939,466 | 84,180 / 84,550（99.5624%） |
| 15M・短いpiece・1ep | 15,735,168 | d=384、8層、6 head、FFN 1,024 | min 2 / max 8 | 1 | 17,281,995 | 84,305 / 84,550（99.7102%） |
| 15M・既存BPE・3ep | 15,735,168 | d=384、8層、6 head、FFN 1,024 | min 5 / max 24 | 3 | 20,818,398 | 84,434 / 84,550（99.8628%） |
| 15M・既存BPE・10ep | 15,735,168 | d=384、8層、6 head、FFN 1,024 | min 5 / max 24 | 10 | 69,394,660 | 83,058 / 84,550（98.2354%） |

固定5テストは通常、組合せ汎化、日本語言い換え、同一操作の反復、境界値の合計である。

## 成果物とハッシュ

### 1M・既存BPE・1エポック

- 正確なパラメータ数: 1,016,704
- [保存済み学習設定](../../data/models/boku_nano_1m_bpe_2048_1epoch/training_config.yaml)
- [training manifest](../../data/models/boku_nano_1m_bpe_2048_1epoch/training_manifest.json)
- モデルSHA-256: c4774c30963d00fee31f52ffc2201f85713cc941832b0c412161ce46541c2b0a

### 1M・短いpiece・1エポック

- 正確なパラメータ数: 1,016,704
- [保存済み学習設定](../../data/models/boku_nano_1m_bpe_2048_minfreq2_maxlen8_1epoch/training_config.yaml)
- [training manifest](../../data/models/boku_nano_1m_bpe_2048_minfreq2_maxlen8_1epoch/training_manifest.json)
- モデルSHA-256: 1e9bd1911fd405c2e5e839b38cf5744ea7a287d1e7595f747845eadcce302576

### 5M・既存BPE・1エポック

- 正確なパラメータ数: 5,065,472
- [保存済み学習設定](../../data/models/boku_nano_5m_bpe_2048_1epoch/training_config.yaml)
- [training manifest](../../data/models/boku_nano_5m_bpe_2048_1epoch/training_manifest.json)
- モデルSHA-256: 027fe1b64c4495dd39322f0ade7824e085b7315543c840b031742e42f4a4c0c6

### 5M・短いpiece・1エポック

- 正確なパラメータ数: 5,065,472
- [保存済み学習設定](../../data/models/boku_nano_5m_bpe_2048_minfreq2_maxlen8_1epoch/training_config.yaml)
- [training manifest](../../data/models/boku_nano_5m_bpe_2048_minfreq2_maxlen8_1epoch/training_manifest.json)
- モデルSHA-256: 0c2ad06d34004ffeae122409b6aa355d08e41b39e7303d3fd0cca8a4984eb5f9

### 15M・既存BPE・1エポック

- 正確なパラメータ数: 15,735,168
- [保存済み学習設定](../../data/models/boku_nano_bpe_2048_1epoch/training_config.yaml)
- [training manifest](../../data/models/boku_nano_bpe_2048_1epoch/training_manifest.json)
- モデルSHA-256: 1a0002e1b50aeae59805d8087fbaa16be1b6e2716d78a085230f2cc35edbf68f

### 15M・短いpiece・1エポック

- 正確なパラメータ数: 15,735,168
- [保存済み学習設定](../../data/models/boku_nano_bpe_2048_minfreq2_maxlen8_1epoch/training_config.yaml)
- [training manifest](../../data/models/boku_nano_bpe_2048_minfreq2_maxlen8_1epoch/training_manifest.json)
- モデルSHA-256: c019688997247f4bc10198703364d88584ff63539d1e6a739764ab372bd1ed83

### 15M・既存BPE・3エポック

- 正確なパラメータ数: 15,735,168
- [保存済み学習設定](../../data/models/boku_nano_bpe_2048/training_config.yaml)
- [training manifest](../../data/models/boku_nano_bpe_2048/training_manifest.json)
- モデルSHA-256: 5623f066cc47ef58790e56d5a62fe9a258d502569995a7aff6c65558c622cf0e

### 15M・既存BPE・10エポック

- 正確なパラメータ数: 15,735,168
- [保存済み学習設定](../../data/models/boku_nano_bpe_2048_10epoch/training_config.yaml)
- [training manifest](../../data/models/boku_nano_bpe_2048_10epoch/training_manifest.json)
- モデルSHA-256: 6852e36364c4f87a44646ebf01262f661bbbadc112c5d6e8daed2d045461aa7b

## 規模別の構造

| 規模名 | 正確なパラメータ数 | hidden size | 層数 | head数 | head次元 | FFN size |
|---|---:|---:|---:|---:|---:|---:|
| 1M級 | 1,016,704 | 128 | 3 | 4 | 32 | 256 |
| 5M級 | 5,065,472 | 256 | 5 | 4 | 64 | 704 |
| 15M級 | 15,735,168 | 384 | 8 | 6 | 64 | 1,024 |

3規模とも語彙数2,048、context length 256、RoPE、RMSNorm、dropout 0.0、入出力embedding非共有である。

## まだ学習していない構成

35M級は設計値だけで、学習済みモデルはない。

## 関連資料

- [1Mモデル2種の評価結果](boku_nano_1m_evaluation_results.md)
- [5M・1エポックのトークナイザー比較](boku_nano_5m_1epoch_tokenizer_comparison.md)
- [15M・1エポックのトークナイザー比較](boku_nano_15m_1epoch_tokenizer_comparison.md)
- [15M・3エポックの学習結果](boku_nano_three_epoch_training_results.md)
- [3エポック評価結果](boku_nano_3epoch_evaluation_results.md)
- [短いpiece版15M・1エポック評価結果](boku_nano_bpe_2048_minfreq2_maxlen8_1epoch_evaluation_results.md)
- [Chinchilla則によるモデル規模設計](../policies/boku_nano_chinchilla_scaling.md)
