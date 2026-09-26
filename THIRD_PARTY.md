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

## ブラウザ推論ランタイム

| 成果物 | Version | 用途 | ライセンス |
| --- | ---: | --- | --- |
| Microsoft ONNX Runtime Web | 1.30.0 | GitHub Pages上のONNX推論 | MIT |

配布用JavaScript・WASMは`web/vendor/`へ保存し、ライセンス本文は[`web/vendor/onnxruntime-web.LICENSE`](web/vendor/onnxruntime-web.LICENSE)へ同梱している。

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
