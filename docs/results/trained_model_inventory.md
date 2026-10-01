# 学習済みBoku Nanoモデル一覧

## 一覧の基準

model.safetensorsとstatus=completedのtraining_manifest.jsonが実在するモデルだけを「学習済み」として掲載する。設定や起動スクリプトだけのモデルは含めない。

2026年10月1日時点で、学習済みモデルは8個である。パラメータ規模は正確に1,016,704、5,065,472、15,735,168の3種類である。

## ディレクトリ命名規則

学習済みモデルのディレクトリ名を次の形式に統一した。

`boku_nano_<規模>_bpe_2048_minfreq<最小頻度>_maxlen<最大piece長>_<epoch数>epoch`

例えば[boku_nano_5m_bpe_2048_minfreq2_maxlen8_1epoch](../../data/models/boku_nano_5m_bpe_2048_minfreq2_maxlen8_1epoch/training_manifest.json)は、5M級、BPE語彙2,048、最小頻度2、最大piece長8、1エポックのモデルを表す。規模は読みやすい`1m`・`5m`・`15m`で表し、正確なパラメータ数はmanifestと一覧表に記録する。`minfreq5_maxlen24`が従来の既存BPE、`minfreq2_maxlen8`が短いpiece用BPEであり、ディレクトリ名だけでモデル規模とトークナイザーを判別できる。

## 学習済みモデル

| モデル | 正確なパラメータ数 | 構造 | トークナイザー | epoch | 学習系列token | 固定5テスト | ONNX |
|---|---:|---|---|---:|---:|---:|---|
| 1M・既存BPE・1ep | 1,016,704 | d=128、3層、4 head、FFN 256 | min 5 / max 24 | 1 | 6,939,466 | 1,467 / 84,550（1.7351%） | 済 |
| 1M・短いpiece・1ep | 1,016,704 | d=128、3層、4 head、FFN 256 | min 2 / max 8 | 1 | 17,281,995 | 4,572 / 84,550（5.4075%） | 済 |
| 5M・既存BPE・1ep | 5,065,472 | d=256、5層、4 head、FFN 704 | min 5 / max 24 | 1 | 6,939,466 | 81,557 / 84,550（96.4601%） | 済 |
| 5M・短いpiece・1ep | 5,065,472 | d=256、5層、4 head、FFN 704 | min 2 / max 8 | 1 | 17,281,995 | 82,353 / 84,550（97.4015%） | 済 |
| 15M・既存BPE・1ep | 15,735,168 | d=384、8層、6 head、FFN 1,024 | min 5 / max 24 | 1 | 6,939,466 | 84,180 / 84,550（99.5624%） | 済 |
| 15M・短いpiece・1ep | 15,735,168 | d=384、8層、6 head、FFN 1,024 | min 2 / max 8 | 1 | 17,281,995 | 84,305 / 84,550（99.7102%） | 済 |
| 15M・既存BPE・3ep | 15,735,168 | d=384、8層、6 head、FFN 1,024 | min 5 / max 24 | 3 | 20,818,398 | 84,434 / 84,550（99.8628%） | 済 |
| 15M・既存BPE・10ep | 15,735,168 | d=384、8層、6 head、FFN 1,024 | min 5 / max 24 | 10 | 69,394,660 | 83,058 / 84,550（98.2354%） | 済 |

固定5テストは通常、組合せ汎化、日本語言い換え、同一操作の反復、境界値の合計である。

## 成果物とハッシュ

### 1M・既存BPE・1エポック

- 正確なパラメータ数: 1,016,704
- [保存済み学習設定](../../data/models/boku_nano_1m_bpe_2048_minfreq5_maxlen24_1epoch/training_config.yaml)
- [training manifest](../../data/models/boku_nano_1m_bpe_2048_minfreq5_maxlen24_1epoch/training_manifest.json)
- モデルSHA-256: c4774c30963d00fee31f52ffc2201f85713cc941832b0c412161ce46541c2b0a
- [ONNX](../../data/models/boku_nano_1m_bpe_2048_minfreq5_maxlen24_1epoch/model.onnx)
- [ONNX検証manifest](../../data/models/boku_nano_1m_bpe_2048_minfreq5_maxlen24_1epoch/onnx_manifest.json)
- ONNX SHA-256: 6e968399cb0515dd0b7dc0bfd76ac21875497e0ea26e2482a09a0faa6a18532f

### 1M・短いpiece・1エポック

- 正確なパラメータ数: 1,016,704
- [保存済み学習設定](../../data/models/boku_nano_1m_bpe_2048_minfreq2_maxlen8_1epoch/training_config.yaml)
- [training manifest](../../data/models/boku_nano_1m_bpe_2048_minfreq2_maxlen8_1epoch/training_manifest.json)
- モデルSHA-256: 1e9bd1911fd405c2e5e839b38cf5744ea7a287d1e7595f747845eadcce302576
- [ONNX](../../data/models/boku_nano_1m_bpe_2048_minfreq2_maxlen8_1epoch/model.onnx)
- [ONNX検証manifest](../../data/models/boku_nano_1m_bpe_2048_minfreq2_maxlen8_1epoch/onnx_manifest.json)
- ONNX SHA-256: e87fd4087b0d635f6721bdf8444e20491bda0d45f9f357fef70e12f2c759c6dc

### 5M・既存BPE・1エポック

- 正確なパラメータ数: 5,065,472
- [保存済み学習設定](../../data/models/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch/training_config.yaml)
- [training manifest](../../data/models/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch/training_manifest.json)
- モデルSHA-256: 027fe1b64c4495dd39322f0ade7824e085b7315543c840b031742e42f4a4c0c6
- [ONNX](../../data/models/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch/model.onnx)
- [ONNX検証manifest](../../data/models/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch/onnx_manifest.json)
- ONNX SHA-256: 5e71bc0ef680408eab5fb5c0f3ff450e492d7edf0230bde7ef830fd92c54f1a7

### 5M・短いpiece・1エポック

- 正確なパラメータ数: 5,065,472
- [保存済み学習設定](../../data/models/boku_nano_5m_bpe_2048_minfreq2_maxlen8_1epoch/training_config.yaml)
- [training manifest](../../data/models/boku_nano_5m_bpe_2048_minfreq2_maxlen8_1epoch/training_manifest.json)
- モデルSHA-256: 0c2ad06d34004ffeae122409b6aa355d08e41b39e7303d3fd0cca8a4984eb5f9
- [ONNX](../../data/models/boku_nano_5m_bpe_2048_minfreq2_maxlen8_1epoch/model.onnx)
- [ONNX検証manifest](../../data/models/boku_nano_5m_bpe_2048_minfreq2_maxlen8_1epoch/onnx_manifest.json)
- ONNX SHA-256: fb2684e13da0735488aa41f4e095956e9b66a1b72ceb955d279f475cbb10bfe0

### 15M・既存BPE・1エポック

- 正確なパラメータ数: 15,735,168
- [保存済み学習設定](../../data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/training_config.yaml)
- [training manifest](../../data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/training_manifest.json)
- モデルSHA-256: 1a0002e1b50aeae59805d8087fbaa16be1b6e2716d78a085230f2cc35edbf68f
- [ONNX](../../data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/model.onnx)
- [ONNX検証manifest](../../data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/onnx_manifest.json)
- ONNX SHA-256: 7b49bea89c85aa03f688b4b7c3c1bc587972067c2798e1ea72775cb999e28c55

### 15M・短いpiece・1エポック

- 正確なパラメータ数: 15,735,168
- [保存済み学習設定](../../data/models/boku_nano_15m_bpe_2048_minfreq2_maxlen8_1epoch/training_config.yaml)
- [training manifest](../../data/models/boku_nano_15m_bpe_2048_minfreq2_maxlen8_1epoch/training_manifest.json)
- モデルSHA-256: c019688997247f4bc10198703364d88584ff63539d1e6a739764ab372bd1ed83
- [ONNX](../../data/models/boku_nano_15m_bpe_2048_minfreq2_maxlen8_1epoch/model.onnx)
- [ONNX検証manifest](../../data/models/boku_nano_15m_bpe_2048_minfreq2_maxlen8_1epoch/onnx_manifest.json)
- ONNX SHA-256: 7282ad214e9d56e8427ff0b785f1d5d5e80700dd9b3e88e3c87718901f00277c

### 15M・既存BPE・3エポック

- 正確なパラメータ数: 15,735,168
- [保存済み学習設定](../../data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_3epoch/training_config.yaml)
- [training manifest](../../data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_3epoch/training_manifest.json)
- モデルSHA-256: 5623f066cc47ef58790e56d5a62fe9a258d502569995a7aff6c65558c622cf0e
- [Web用ONNX](../../web/models/boku-nano-3epoch.onnx)
- ONNX SHA-256: 1145db9ff1520e8fb3ad2eca7184b20f19390e90ee84f075a5105963d9a408b3

### 15M・既存BPE・10エポック

- 正確なパラメータ数: 15,735,168
- [保存済み学習設定](../../data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_10epoch/training_config.yaml)
- [training manifest](../../data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_10epoch/training_manifest.json)
- モデルSHA-256: 6852e36364c4f87a44646ebf01262f661bbbadc112c5d6e8daed2d045461aa7b
- [Web用ONNX](../../web/models/boku-nano-10epoch.onnx)
- ONNX SHA-256: 59df1f0dae8e4111f5b444d388c95f88273361ae293cc5154eda7150289eab11

8モデルすべてをGitHub Pagesの選択対象として`web/models/`にも配置し、モデルと2種類のBPEの対応を[Webモデルmanifest](../../web/model-manifest.json)に固定している。各1エポックモデルの`onnx_manifest.json`には、ONNX形式検査、2プロンプトのlogits誤差、PyTorch版と一致したgreedy生成token列、ONNX SHA-256、ファイルサイズを保存している。

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
- [1M・5M・15Mのattention解析総合比較](boku_nano_1epoch_attention_comparison.md)
- [attention解析図の結果種類別一覧](attention_1epoch_by_result/README.md)
- [15M・3エポックの学習結果](boku_nano_three_epoch_training_results.md)
- [3エポック評価結果](boku_nano_3epoch_evaluation_results.md)
- [短いpiece版15M・1エポック評価結果](boku_nano_bpe_2048_minfreq2_maxlen8_1epoch_evaluation_results.md)
- [Chinchilla則によるモデル規模設計](../policies/boku_nano_chinchilla_scaling.md)
