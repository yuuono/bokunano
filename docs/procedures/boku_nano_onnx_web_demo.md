# Boku1-nano ONNX Webデモ手順書

## 目的

3エポックモデルと10エポックモデルをONNXへ変換し、GitHub Pages上のブラウザだけで日本語指示から、単一操作および2・3操作を組み合わせたPythonコードを生成する。

入力例は単一操作、2操作、3操作に分けて選択できる。選択時は入力欄へ文章を設定するだけであり、固定コードを返す条件分岐は持たない。自由入力と入力例は、いずれも同じBPEトークナイザ、ONNX Runtime、選択中のモデルを通る。

## 構成

- `scripts/model/export_boku_nano_onnx.py`: 両モデルの変換とPyTorch比較
- `scripts/model/test_boku_nano_web.py`: Firefoxによるブラウザ・スモークテスト
- `web/`: GitHub Pagesへ配置する静的サイト
- `.github/workflows/pages.yml`: main更新時のPages公開

| 表示名 | 学習済み重み | ONNX |
| --- | --- | --- |
| 3エポックモデル | `data/models/boku_nano_bpe_2048/model.safetensors` | `web/models/boku-nano-3epoch.onnx` |
| 10エポックモデル | `data/models/boku_nano_bpe_2048_10epoch/model.safetensors` | `web/models/boku-nano-10epoch.onnx` |

## ONNXの再生成

```bash
uv sync --group onnx-export
uv run --group onnx-export python scripts/model/export_boku_nano_onnx.py
```

変換時に、ONNX形式検査、2プロンプトのlogits比較、greedy生成token列の完全一致、単一ファイルサイズ、各成果物のSHA-256記録を自動実行する。

## ローカル表示

```bash
uv run --group onnx-export python -m http.server 8000 --directory web
```

ブラウザで`http://127.0.0.1:8000/`を開く。WebGPUを利用できる場合はWebGPU、初期化できない場合はWASMを使用する。推論入力は外部APIへ送信しない。

## 実ブラウザ試験

```bash
uv run --group onnx-export python scripts/model/test_boku_nano_web.py \
  --geckodriver /snap/bin/geckodriver
```

ブラウザ版BPEとPython版BPEのtoken ID列の一致、および3エポック・10エポック両モデルが2操作と3操作を含む`solve`関数を生成することを確認する。

2026年9月28日のFirefox headless試験結果は次のとおり。速度は実行機によって変わる。

| モデル | 操作数 | バックエンド | 生成token数 | 速度 | 結果 |
| --- | ---: | --- | ---: | ---: | --- |
| 3エポック | 2 | WASM | 11 | 20.4 tokens/s | 絶対値化、降順ソートを生成 |
| 3エポック | 3 | WASM | 16 | 53.7 tokens/s | 3倍、符号反転、k未満抽出を生成 |
| 10エポック | 2 | WASM | 10 | 26.8 tokens/s | 絶対値化、降順ソートを生成 |
| 10エポック | 3 | WASM | 27 | 48.1 tokens/s | 3倍、符号反転、k未満抽出を生成 |

## GitHub Pages公開

1. リポジトリのSettingsからPagesを開く。
2. SourceにGitHub Actionsを選ぶ。
3. `main`へpushするか、`GitHub PagesへONNXデモを公開` workflowを手動実行する。
4. workflowが`web/`全体をPages artifactとして公開する。

モデルは各約60.4 MiBである。初回選択時に対象モデルだけを取得し、同じページ内では読み込んだセッションを再利用する。

## 制約

- 最大系列長は入力と生成を合わせて256 tokenである。
- 生成方式は評価条件と同じgreedy decodingである。
- KV cacheを実装していないため、生成tokenごとに現在の系列全体を再計算する。
- 画面はコードを表示するだけで、生成コードを自動実行しない。
- WebGPU経路は対応するChromeまたはEdgeで追加確認する。Firefox試験ではWASMフォールバックを確認済みである。
