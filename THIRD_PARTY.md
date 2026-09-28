# Third-party software and model provenance

この文書は、Boku1-nanoのデータ作成、学習、変換、ブラウザ実行に使用した主要な第三者成果物を記録する。ライセンス名は各配布元が示す情報であり、教師生成物を含む全成果物について第三者の権利が存在しないことを保証するものではない。

## 教師モデル

| 項目 | 内容 |
| --- | --- |
| モデル | `Qwen/Qwen3-4B-AWQ` |
| 用途 | 日本語の単独操作表現候補と訓練指示の言い換え候補の生成 |
| revision | `74d4bd2bd4bff9cafc9345221320bffb08b406a3` |
| ライセンス | Apache License 2.0 |
| 固定モデルページ | https://huggingface.co/Qwen/Qwen3-4B-AWQ/tree/74d4bd2bd4bff9cafc9345221320bffb08b406a3 |
| 保存したLICENSE | [`third_party/qwen3-4b-awq/LICENSE`](third_party/qwen3-4b-awq/LICENSE) |
| 取得記録 | [`third_party/qwen3-4b-awq/SOURCE.json`](third_party/qwen3-4b-awq/SOURCE.json) |

Qwen3は日本語表現の候補作成だけに使用した。Qwen3へコード生成を依頼しておらず、Qwen3の重み、tokenizer、logit、埋め込み、内部状態をBoku1-nanoへ移植していない。

教師プロンプトは`prompts/japanese_instruction_generation/`、モデルrevisionと生成条件は`config/qwen_*.json`、採用表現ごとのmodel、revision、seed、sampling、prompt hashは`data/instruction_dictionaries/release/japanese_atomic_expression_provenance.jsonl`へ保存している。

## ブラウザCNL翻訳モデル

| 項目 | 内容 |
| --- | --- |
| 配布モデル | `onnx-community/Qwen3-0.6B-ONNX` |
| upstream | `Qwen/Qwen3-0.6B` |
| 用途 | 自由な日本語から許可済みCNLへのブラウザ内翻訳 |
| 配布revision | `da1453100cf3ff33ef56d17983fc7a8648706db6` |
| upstream revision | `c1899de289a04d12100db370d81485cdf75e47ca` |
| 量子化成果物 | `onnx/model_q4f16.onnx`、569,789,750 bytes |
| 成果物SHA-256 | `9e33a5911974174761d0dfdcc0bec975d9c45af0eae5e9eb647b8ba9442a8f91` |
| upstreamライセンス | Apache License 2.0 |
| 固定配布ページ | https://huggingface.co/onnx-community/Qwen3-0.6B-ONNX/tree/da1453100cf3ff33ef56d17983fc7a8648706db6 |
| 保存したLICENSE | [`third_party/qwen3-0.6b-onnx/LICENSE`](third_party/qwen3-0.6b-onnx/LICENSE) |
| 取得記録 | [`third_party/qwen3-0.6b-onnx/SOURCE.json`](third_party/qwen3-0.6b-onnx/SOURCE.json) |

このQwenはデモ実行時にだけ使い、Boku1-nanoの再学習や重み更新には使わない。CNLを生成するのはQwenであり、JavaScriptは24操作・最大3操作の許可リストと文法を検査するだけである。ONNX成果物はリポジトリへ再配布せず、ブラウザが固定revisionから取得してキャッシュする。

## ブラウザ推論ランタイム

| 成果物 | Version | 用途 | ライセンス |
| --- | ---: | --- | --- |
| Microsoft ONNX Runtime Web | 1.30.0 | Boku1-nanoのGitHub Pages上のONNX推論 | MIT |
| Hugging Face Transformers.js | 4.3.0 | Qwen3-0.6B ONNXのブラウザ内推論 | Apache-2.0 |

ONNX Runtime Webの配布用JavaScript・WASMは`web/vendor/`へ保存し、ライセンス本文は[`web/vendor/onnxruntime-web.LICENSE`](web/vendor/onnxruntime-web.LICENSE)へ同梱している。Transformers.jsはversionを固定してjsDelivrから実行時に読み込み、ライセンス本文と取得元は[`third_party/transformers-js/`](third_party/transformers-js/)へ保存している。

## 主要なビルド・学習依存関係

これらはリポジトリへライブラリ本体を再配布せず、`pyproject.toml`と`uv.lock`でversionと配布hashを固定する。

| Software | 主な用途 | upstream license |
| --- | --- | --- |
| PyTorch | モデル実装・学習 | BSD-3-Clause |
| Hugging Face Transformers | Qwen3教師推論 | Apache-2.0 |
| Hugging Face Tokenizers | BPE学習・推論 | Apache-2.0 |
| safetensors | 重み保存 | Apache-2.0 |
| ONNX / ONNX Runtime | ONNX変換・検証 | Apache-2.0 / MIT |
| NumPy | 数値処理 | BSD-3-Clause |
| PyYAML | 設定読込 | MIT |

## 合成コードの由来

訓練・評価用の`reference_code`は、意味AST、自作テンプレート、`python_code_generator.py`、`structural_variant_generator.py`から決定的に生成した。Web検索、GitHub検索、オンラインコード例、Qwen3によるコード生成を入力にしていない。

長い一致の検査は[`scripts/validation/check_long_code_matches.py`](scripts/validation/check_long_code_matches.py)で再実行でき、結果は[`data/provenance/long_code_match_report.json`](data/provenance/long_code_match_report.json)へ保存する。この検査は明示した比較コーパスに対するものであり、インターネット上の全コードとの非一致を保証しない。
