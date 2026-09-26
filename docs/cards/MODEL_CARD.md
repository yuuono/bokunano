# Boku1-nano Model Card

## モデル概要

Boku1-nanoは、日本語指示から限定的なPython関数を生成する、ランダム初期値から学習したDecoder-only Transformerである。

| 項目 | 値 |
| --- | ---: |
| parameter数 | 15,735,168 |
| 語彙数 | 2,048 |
| 層数 | 8 |
| hidden size | 384 |
| Attention head数 | 6 |
| FFN size | 1,024 |
| 最大系列長 | 256 |
| 位置表現 | RoPE |
| 正規化 | RMSNorm |
| 活性化 | SwiGLU |
| weight tying | なし |

## 公開variant

| Variant | epoch | 重みSHA-256 | 1 epochの系列token数 |
| --- | ---: | --- | ---: |
| `boku_nano_bpe_2048` | 3 | `5623f066cc47ef58790e56d5a62fe9a258d502569995a7aff6c65558c622cf0e` | 6,939,466 |
| `boku_nano_bpe_2048_10epoch` | 10 | `6852e36364c4f87a44646ebf01262f661bbbadc112c5d6e8daed2d045461aa7b` | 6,939,466 |

tokenizerは`data/tokenizers/bpe_2048/tokenizer.json`、SHA-256は`6840a392e8fcae1083be06842774fa912a1797217c7033944ba2d87f1c227293`である。モデルごとの正確な学習条件、software version、データhashは各`training_manifest.json`に保存している。

## 学習データと教師モデルとの関係

モデル重みとtokenizerは既存モデルから移植せず、訓練データからランダム初期値で作成した。Qwen3はオフラインの日本語表現候補作成にだけ使用した。

- Qwen3の重み、埋め込み、tokenizer、logit、内部状態は使用していない。
- 学習中およびBoku1-nano推論時にQwen3を呼び出さない。
- 教師モデルは`Qwen/Qwen3-4B-AWQ` revision `74d4bd2bd4bff9cafc9345221320bffb08b406a3`である。
- Qwen3へ正解コード生成を依頼していない。

データの詳細は`docs/cards/DATASET_CARD.md`、第三者成果物は`THIRD_PARTY.md`を参照する。

## 想定用途

- 整数リスト`xs`と整数`k`を受け取る`solve(xs, k)`関数の生成
- 24種類の抽出、変換、並べ替え、切り出し操作と1〜3操作の組合せ
- 小規模言語モデルのフルスクラッチ学習・評価の再現実験

一般的なPython開発、セキュリティ関連コード、外部I/O、任意ライブラリ利用、自然言語一般には使用しない。

## 評価

評価は文字列一致ではなく、syntax、Safe-AST、signature、隔離実行、hidden testを重視する。3エポック版の詳細結果、学習前比較、pass@1、pass@5、失敗分析は`docs/results/`に保存している。ONNX版はPyTorch版とのlogits比較とgreedy生成token列の一致を確認している。

## 制約とリスク

- 対象領域外では不正確または実行不能なコードを生成し得る。
- 生成コードは信頼せず、実行前に静的検査と隔離実行を行う必要がある。
- 3エポック版の正式評価では84,550件中116件が不合格だった。
- 教師モデルのライセンスは、教師生成文や学生モデルを含む全成果物について第三者権利が存在しないことを保証しない。

## ライセンスと来歴

Qwen3の公式LICENSEは`third_party/qwen3-4b-awq/LICENSE`へ保存している。Qwen3はApache License 2.0で公開されているが、このModel CardはBoku1-nanoの重みやデータセットへ自動的に同じライセンスを付与するものではない。リポジトリ全体またはBoku1-nano成果物のライセンスを別途定める場合は、第三者成果物の条件と教師生成物の権利確認を分けて行う。
