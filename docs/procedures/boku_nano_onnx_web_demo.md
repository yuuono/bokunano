# Boku1-nano ONNX Webデモ手順書

## 目的

GitHub Pages上のブラウザだけで、自由な日本語からPythonコードまでを次の順で処理する。

1. Qwen3-0.6Bが自由な日本語をControlled Natural Language（CNL）へ翻訳する。
2. JavaScriptがCNLを24種類・最大3操作の規則に照らして検査する。
3. ユーザーがCNLと操作順を確認する。
4. 3エポックまたは10エポックのBoku1-nanoが、検査済みCNLからコードを生成する。

内部の意味ASTはブラウザ経路に設けない。JavaScriptは自由文の意味解釈やCNL生成を行わず、Qwenの出力を検査するだけである。入力例は自由文欄へ文章を設定するだけで、CNLやコードを固定で返す分岐を持たない。

詳細方針は[`browser_cnl_normalization_policy.md`](../policies/browser_cnl_normalization_policy.md)を参照する。

## 構成

- `web/cnl.js`: 24操作、CNL文法、検査器、Qwen用few-shot prompt
- `web/qwen-worker.js`: Qwenの読込、最大2回のCNL生成、モデル解放
- `web/qwen-manifest.json`: Qwenモデル、revision、成果物hash、Transformers.js version
- `web/demo.js`: UI状態管理、CNL検査、Boku1-nano ONNX推論
- `scripts/model/export_boku_nano_onnx.py`: 学生モデル2種のONNX変換とPyTorch比較
- `scripts/model/test_boku_nano_web.py`: FirefoxによるCNL検査と学生モデルのスモークテスト
- `.github/workflows/pages.yml`: `main`更新時のPages公開

| 表示名 | 学習済み重み | ONNX |
| --- | --- | --- |
| 3エポックモデル | `data/models/boku_nano_bpe_2048/model.safetensors` | `web/models/boku-nano-3epoch.onnx` |
| 10エポックモデル | `data/models/boku_nano_bpe_2048_10epoch/model.safetensors` | `web/models/boku-nano-10epoch.onnx` |

Qwen3-0.6B q4f16は569,789,750 bytesである。Pages成果物へ複製せず、初回翻訳時に固定したHugging Face revisionから取得してブラウザキャッシュへ保存する。Boku1-nanoは各約60.4 MiBで、選択モデルを初回生成時にPagesから取得する。

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

デスクトップ版ChromeまたはEdgeで`http://127.0.0.1:8000/`を開く。Qwen翻訳にはWebGPUが必要である。Boku1-nanoはWebGPUを優先し、初期化できない場合だけWASMを使用する。自由文とCNLは外部APIへ送信しないが、モデルとJavaScriptの取得通信は発生する。

## 操作手順

1. 自由な日本語を入力し、`QwenでCNLに翻訳`を押す。
2. 初回は約543 MiBのQwenを取得するため、進捗表示が完了するまで待つ。
3. 表示されたCNLと操作順が意図どおりか確認する。
4. 誤りがあれば自由文を変えて再翻訳するか、CNL欄を直接修正して`CNLを再検査`を押す。
5. 検査合格後、3エポックまたは10エポックを選び、`このCNLでコードを生成`を押す。

Qwenが`対応できません。`を返した場合、または2回の生成がどちらも検査に失敗した場合、学生モデルの生成ボタンは有効にならない。

## 自動ブラウザ試験

```bash
uv run --group onnx-export python scripts/model/test_boku_nano_web.py \
  --geckodriver /snap/bin/geckodriver
```

この試験は次を確認する。

- CNL定義が24操作である。
- 正しい2操作・3操作CNLを受理する。
- 4操作と許可外操作を拒否する。
- ブラウザ版BPEとPython版BPEのtoken ID列が一致する。
- 3エポック・10エポック両モデルが、検査済み2操作・3操作CNLから`solve`関数を生成する。

2026年9月28日のFirefox headless試験では、CNL検査とBPE一致が合格し、次の4ケースでコード生成を確認した。速度は実行機によって変わる。

| モデル | 操作数 | backend | 入力token | 生成token | 速度 | 結果 |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| 3エポック | 2 | WASM | 13 | 11 | 21.7 tokens/s | 絶対値化、降順ソートを生成 |
| 3エポック | 3 | WASM | 17 | 19 | 52.6 tokens/s | 3倍、符号反転、k未満抽出を生成 |
| 10エポック | 2 | WASM | 13 | 13 | 32.7 tokens/s | 絶対値化、降順ソートを生成 |
| 10エポック | 3 | WASM | 17 | 24 | 49.1 tokens/s | 3倍、符号反転、k未満抽出を生成 |

Firefox headlessではWebGPU Qwenを起動せず、CNLを直接入力して検査器からBoku1-nanoまでを確認した。この実行環境にはChrome系ブラウザがないため、Qwenの実推論は未確認であり、次のChrome手動試験で確認する。

## Qwen翻訳の初回検証

追加学習なしの成立性は、既存の24操作で表現できる自由文を使って確認する。最低限、1操作・2操作・3操作を含む入力群について次を記録する。

- 自由文
- 期待CNL
- Qwen出力
- 文法検査の成否
- 操作種別と操作順の完全一致
- 1回目または再生成のどちらで合格したか
- 初回モデル読込時間、キャッシュ後読込時間、生成時間
- Boku1-nanoのコードとhidden test結果

操作数1・2・3の評価件数は同数を前提にせず、各区分の件数を明記した上で区分別の成功率を報告する。0.6Bの採否はCNL構文合格率だけでなく、期待した操作列の完全一致率と端末上の速度で判断する。

## Chrome手動確認

1. DevToolsのConsoleとNetworkを開く。
2. WebGPUが有効なChromeまたはEdgeでページを開く。
3. 入力例と独自の言い換えをそれぞれ翻訳する。
4. NetworkでQwenが固定revision、Transformers.jsが4.3.0から取得されることを確認する。
5. CNL、操作順、所要時間を記録する。
6. 不正なCNLへ編集し、学生モデルへ渡らないことを確認する。
7. 正しいCNLへ直し、3・10エポックの両方でコード生成する。

## GitHub Pages公開

1. リポジトリのSettingsからPagesを開く。
2. SourceにGitHub Actionsを選ぶ。
3. `main`へpushするか、`GitHub PagesへONNXデモを公開` workflowを手動実行する。
4. workflowが`web/`全体をPages artifactとして公開する。

## 制約

- QwenのCNL文法合格は、自由文の意味を正しく翻訳した保証ではない。
- Qwen翻訳はWebGPUを必須とし、WASMへ自動切替しない。
- CNLは許可された24種類の操作を1～3個だけ含められる。
- Boku1-nanoの最大系列長は入力と生成を合わせて256 tokenである。
- Boku1-nanoの生成方式は評価条件と同じgreedy decodingである。
- Boku1-nanoにはKV cacheがなく、生成tokenごとに現在の系列全体を再計算する。
- 画面はコードを表示するだけで、生成コードを自動実行しない。
- Qwenの処理終了後にWorkerを閉じてモデルを解放してから、Boku1-nanoを読み込む。
